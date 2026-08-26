"""LOGIC · open_engine -- the composition root; the only builder of an Engine.

Exactly one place constructs concrete dependencies and wires them together (P19). It reads the two
manifests, the thresholds and the prompt templates, registers both axes, and returns one Engine.
An engine can also be built with no filesystem anywhere, which is what makes a web handler and an
in-process caller the same caller.

**Two builders, one of which reads.** ``composed_engine`` takes two ``Manifest`` objects, a template
string and an encoder, and touches nothing outside its arguments; ``open_engine`` is the same call
with the reading in front of it. Splitting them is what makes *no filesystem anywhere* a signature
rather than a promise -- a caller who has the declarations already, in a request body or a fixture,
cannot accidentally reach a disk through this module.

**This is the only module that names a concrete axis** (Requirement 38). ``MODALITIES`` and
``PROFILES`` map a manifest's name to the class that answers to it, and each class takes its
manifest plus the one thing it cannot open: a model for the modality, a template for the profile.
The symmetry is the point -- an axis is a declaration and the edge resolving what the declaration
names.

**The registry holds what this run resolved, not everything installed.** An ``Engine`` is what a run
resolved to, so both slots are filled from the pair that was asked for. Registering the whole of
``MODALITIES`` would put implementations no manifest was read for into a run's own registry, and
Requirement 39 is about a registry being instance state precisely so that cannot happen quietly.

**Nothing is loaded that a run may never use.** The static embedder is a download and
``duplicate_check`` is its only caller, so ``static_model`` is cached and called on the first vector
rather than at composition: a run of ``label_check`` alone makes no network call, and neither does
``make check``. The question store is the other way round -- ``create_engine`` opens no connection,
so attaching the pool here costs nothing and P19 says the pool is reached for in one place.

**Requirement 28 is not checked here yet.** The cross-border precondition is about a panel, and a
panel has no adapter until T49 -- there is no endpoint declared anywhere for this to read. T49's own
acceptance criteria own it, and this is the module it lands in (§8: the break is recorded where the
next reader hits it).
"""

from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dataforce.engine import Engine, Registry
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities import Modality
from dataforce.modalities.text2text import Encoder, Text2Text, embedding_model
from dataforce.ports import JuryPanel, PersonalDataVerifier, QuestionStore
from dataforce.profiles import Profile
from dataforce.profiles.tool_decision import ToolDecision

from .policy import (
    CONFIG,
    MODALITIES,
    PARAMS,
    PROFILES,
    YAML,
    read_manifest,
    read_question_template,
    read_thresholds,
)
from .store.repository import SqlQuestionStore
from .store.session import sessions_to, store_engine

# A type, not a load: the model itself is fetched inside `static_model`, and importing it here
# would put two seconds on every subcommand that never embeds anything.
if TYPE_CHECKING:
    from model2vec import StaticModel

# Which class answers to a manifest's name, per axis. Both take their manifest and the one thing
# the axis cannot open for itself, which is the whole of what a composition root supplies.
BUILT_MODALITIES: Mapping[str, Callable[[Manifest, Encoder], Modality]] = {
    "text2text": Text2Text
}
BUILT_PROFILES: Mapping[str, Callable[[Manifest, str], Profile]] = {
    "tool_decision": ToolDecision
}


def implementation_named[Implementation](
    axis: str, built: Mapping[str, Implementation], name: str
) -> Implementation:
    """The class that answers to that name, or a `ConfigError` naming the ones that do.

    A manifest is a declaration and something still has to answer to it, so a `config/<axis>/x.yaml`
    with no class behind it is a configuration fault and not an empty run.
    """
    if name not in built:
        known = ", ".join(sorted(built)) or "none"
        raise ConfigError(
            f"{CONFIG}/{axis}/{name}{YAML} is a declaration nothing here implements; "
            f"built: {known}"
        )
    return built[name]


def paired_modality(profile: Manifest, named: str | None) -> str:
    """Which modality this run composes that profile with: the one it declares, and no other.

    Naming none takes the profile at its word, which is what makes `open_engine(profile=…)` the
    ordinary call -- the pair is a fact about the profile, and repeating it at every call site is a
    second place for it to be wrong. Naming a different one is not a preference to be honoured: a
    profile reads content one modality produced, so the run would be asking a question about parts
    nothing in it can read.

    Called twice on the reading path -- once to know which manifest to open, and once by the builder
    below -- because a check only the reader makes is a check a request body full of declarations
    would walk straight past.
    """
    declared = profile.modality
    if not declared:
        raise ConfigError(
            f"{CONFIG}/{PROFILES}/{profile.name}{YAML} names no modality; a profile "
            "declares the pair it composes with, and there is nothing here to take at its word"
        )
    if named is not None and named != declared:
        raise ConfigError(
            f"this run names modality {named!r} and {profile.name!r} composes with "
            f"{declared!r}; a profile answers about content one modality read"
        )
    return declared


@lru_cache(maxsize=None)
def static_model(model_name: str) -> "StaticModel":
    """The static embedder that name resolves to, fetched once per process.

    Imported inside the function and cached outside it, for two different reasons. The import costs
    seconds and `edge/cli.py` pays it on every subcommand, including the ones that print help. The
    cache is because two engines over one corpus should be two engines and one model.

    `force_download=False` is the library's non-default and this project's requirement: a static
    embedding is a pure function of its input (Requirement 23), so re-fetching the weights every run
    buys nothing and makes a run depend on a registry being up.
    """
    from model2vec import StaticModel

    return StaticModel.from_pretrained(model_name, force_download=False)


def static_encoder(model_name: str) -> Encoder:
    """One document into one vector, from the model that name resolves to when the first is asked.

    A closure and not a loaded model: the modality's signature is *hand me an encoder* precisely so
    the file behind it is the edge's business, and most runs never embed anything.
    """

    def encode(document: str) -> list[float]:
        return [
            float(value) for value in static_model(model_name).encode([document])[0]
        ]

    return encode


def composed_engine(
    *,
    modality: Manifest,
    profile: Manifest,
    encode: Encoder,
    question: str,
    thresholds: Mapping[str, Any] = {},
    policy_digests: Mapping[str, str] = {},
    personal_data_verifier: PersonalDataVerifier | None = None,
    jury_panel: JuryPanel | None = None,
    question_store: QuestionStore | None = None,
) -> Engine:
    """One engine out of two declarations, with no filesystem anywhere.

    The two empty defaults are honest rather than convenient: an engine with no thresholds is one
    whose every threshold reader refuses (`pipeline/params.py`), and an engine with no policy
    digests was not built out of policy files, which is exactly what a caller handing manifests
    over is saying. Both are wrong to guess and cheap to state.

    Every port defaults to absent, including the store: *no filesystem anywhere* has to cover a
    backing service too, or the phrase means one layer of the world and not the world.
    """
    pair = paired_modality(profile, modality.name)
    registry = Registry()
    registry.register_modality(
        modality.name,
        implementation_named(MODALITIES, BUILT_MODALITIES, modality.name)(
            modality, encode
        ),
    )
    registry.register_profile(
        profile.name,
        implementation_named(PROFILES, BUILT_PROFILES, profile.name)(profile, question),
    )
    return Engine(
        modality=registry.modality(pair),
        profile=registry.profile(profile.name),
        registry=registry,
        thresholds=thresholds,
        policy_digests=policy_digests,
        personal_data_verifier=personal_data_verifier,
        jury_panel=jury_panel,
        question_store=question_store,
    )


def open_engine(
    profile: str,
    modality: str | None = None,
    *,
    config_root: Path = Path(CONFIG),
    params: Path = Path(PARAMS),
    personal_data_verifier: PersonalDataVerifier | None = None,
    jury_panel: JuryPanel | None = None,
    question_store: QuestionStore | None = None,
) -> Engine:
    """The engine one run resolves to, read out of the files that declare it.

    The profile is read first, because it is what says which modality to read: a run that named
    both would still be resolved by the profile's own declaration, so asking the file is the same
    answer with one fewer way to disagree.

    The two model ports arrive from above and are `None` until T49 builds an adapter for either.
    The store does not: `SqlQuestionStore` exists and a connection pool is a concrete dependency,
    so this is where it is constructed (P19) and `composed_engine` is where a caller says *not
    that one*.
    """
    declared_profile = read_manifest(config_root, PROFILES, profile)
    declared_modality = read_manifest(
        config_root, MODALITIES, paired_modality(declared_profile.declares, modality)
    )
    declared_thresholds = read_thresholds(params)
    declared_question = read_question_template(config_root, declared_profile.declares)
    files = (
        declared_modality,
        declared_profile,
        declared_thresholds,
        declared_question,
    )
    return composed_engine(
        modality=declared_modality.declares,
        profile=declared_profile.declares,
        encode=static_encoder(embedding_model(declared_modality.declares)),
        question=declared_question.declares,
        thresholds=declared_thresholds.declares,
        policy_digests={file.path: file.digest for file in files},
        personal_data_verifier=personal_data_verifier,
        jury_panel=jury_panel,
        question_store=question_store or SqlQuestionStore(sessions_to(store_engine())),
    )
