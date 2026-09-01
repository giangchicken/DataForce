"""LOGIC · open_engine -- the composition root; the only builder of an Engine.

Exactly one place constructs concrete dependencies and wires them together. It reads the two
manifests, the thresholds and the prompt templates, registers both axes, and returns one Engine.
An engine can also be built with no filesystem anywhere, which is what makes a web handler and an
in-process caller the same caller.

**Two builders, one of which reads.** ``composed_engine`` takes two ``Manifest`` objects, a template
string and an encoder, and touches nothing outside its arguments; ``open_engine`` is the same call
with the reading in front of it. Splitting them is what makes *no filesystem anywhere* a signature
rather than a promise -- a caller who has the declarations already, in a request body or a fixture,
cannot accidentally reach a disk through this module.

**This is the only module that names a concrete axis** (Requirement 38). ``BUILT_MODALITIES`` and
``BUILT_PROFILES`` map a manifest's name to the class that answers to it, and the edge supplies the
two things neither class can open for itself: an encoder for the concept, a template for the module.

**One object fills both slots, because a profile is a subclass of its modality** (§ *The two axes*).
``ToolDecision`` *is* a ``Text2Text``, so a run resolves to one instance answering both protocols
and the registry registers it twice -- under its modality name in one namespace and its profile name
in the other. Two slots and one object: the namespaces stay separate because a name is only unique
within the ``config/<axis>/`` directory it was read from, and a concept with three modules in it
still needs one entry per module.

**The pair is still checked against the manifests and not against the hierarchy.**
``paired_modality`` compares the two declarations, which is what a request body full of them has to
pass; the hierarchy says the same thing one level up and is proved where it costs nothing --
``mypy --strict`` on the ``TYPE_CHECKING`` block in ``profiles/tool_decision/profile.py``, and a test
over the two maps below. A runtime ``issubclass`` here would be a third statement of one fact,
checked at the one moment both other statements have already been read.

**The registry holds what this run resolved, not everything installed.** An ``Engine`` is what a run
resolved to, so both slots are filled from the pair that was asked for. Registering the whole of
``MODALITIES`` would put implementations no manifest was read for into a run's own registry, and
Requirement 39 is about a registry being instance state precisely so that cannot happen quietly.

**The embedder is read at composition, and that is the opposite of what stood here.** It used to be
a download, so nothing was loaded until the first vector and a run of ``label_check`` alone paid
nothing. It is an endpoint this deployment already serves, so there is nothing to load and the only
thing left to get wrong is the file saying where it is -- which is why ``config/model/<model>.json``
is read *here*: an embedder is a resource a deployment attaches, and one nobody attached is a
configuration fault before the first record rather than a stack trace part-way through
``duplicate_check``. Composing still makes no network call; a client is constructed and
nothing is sent. The question store is the same shape -- ``create_engine`` opens no connection, so
attaching the pool here costs nothing and the pool is reached for in one place.

**The model file is not a policy file, and leaving it out of ``policy_digests`` is deliberate.**
Digesting every file a run reads is Requirement 45's rule and this would be the fifth -- except that
this one holds the key, so two people pointed at one endpoint with two keys would write two run
manifests for one configuration and a rotated key would read as a changed configuration, which is
I14 failing for a reason that is not a configuration change. What a run manifest records instead is
``embedding.model`` inside the modality manifest, whose digest is already in it.

**The embeddings call reaches ``openai`` directly, under one annotated exemption.** The library owns
the LLM client (I6) and offers ``complete``, ``complete_structured``, ``complete_with_reasoning``,
``count_tokens`` and the resolvers -- nothing embedding-shaped -- so there is no front door to go
through, and the exemption on the import is what the library task deletes when an ``embed`` lands
beside ``complete``.

**What is not solved here: a second run re-pays the corpus.** ``lru_cache`` used to hold a loaded
model, and the hosted analogue is a cache per document, without which running ``duplicate_check``
twice embeds every record twice. § *ai_review* makes the same argument about the panel: work that
costs money is not re-paid because something downstream moved. T49 is where a cache and its key get
designed; sizing one for twenty thousand documents is not a line to add in passing, so it is
recorded where the next reader hits it.

**Requirement 28 is not checked here yet.** The cross-border precondition is about a panel, and a
panel has no adapter until T49 -- there is no endpoint declared anywhere for this to read. T49's own
acceptance criteria own it, and this is the module it lands in: the break is recorded where the
next reader hits it. The embedder is a third call that requirement does not name either: embedding
sends every record's content to whatever ``config/model/`` points at, which with ``enable_redact``
shipped false is the same exposure a ``jury`` call on those records has.
"""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

import openai  # guard-exempt: I6 · agent-toolkit exposes no embeddings call · the edge · 2026-08-27
from agent_toolkit.llm import JsonDirConfigResolver, LLMConfig
from agent_toolkit.llm.exceptions import LLMConfigError

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

# Where a deployment attaches the endpoints it serves, under the `<model>.json` convention
# `JsonDirConfigResolver` keeps. Not in `policy.py` beside the other three: those name files a run
# manifest records by, and this is the one file it deliberately does not record.
MODEL = "model"


class ProfileInConcept(Modality, Profile, Protocol):
    """One object answering both axes: a module, and the concept it is one module inside.

    The type-system half of § *The two axes*. `Engine` keeps two slots and `Registry` keeps two
    namespaces, but since T52 one instance fills both -- so the composition root needs a name for
    *a thing that is both*, and Python has no intersection type to write it with inline.

    A shape in a `LOGIC ·` module gives way here: the abstraction belongs to the layer that
    consumes it, and this one has exactly one consumer. Putting it in `modalities/base.py` would
    make the modality protocol name the profile one; putting it in `profiles/base.py` would make
    every profile's contract mention a concept it does not have to be inside. Neither is true of
    the engine, and both are true here, which is where it therefore lives.
    """


# Which class answers to a manifest's name, per axis. A concept takes its manifest and an encoder;
# a module inside one takes both manifests, because since T52 it is a subclass and construction
# fills the base's half too. `BUILT_MODALITIES` is what a run with no module would build, and what
# `implementation_named` checks a modality declaration against either way.
BUILT_MODALITIES: Mapping[str, Callable[[Manifest, Encoder], Modality]] = {
    "text2text": Text2Text
}
BUILT_PROFILES: Mapping[
    str, Callable[[Manifest, Manifest, Encoder, str], ProfileInConcept]
] = {"tool_decision": ToolDecision}


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


def attached_endpoint(config_root: Path, model: str) -> LLMConfig:
    """Where this deployment serves that model, or a `ConfigError` naming the file it is not in.

    Resolved on an instance rather than through `set_config_resolver`, which writes a module-level
    global: Requirement 39 makes a registry instance state precisely so two engines in one process
    cannot fight over one slot, and a process-wide resolver is that slot again one layer down.

    `base_url` is required here and optional in the library, because the two defaults mean different
    things. An `LLMConfig` with none is a client pointed at the SDK's own API, so a deployment that
    left the line out would send a corpus to an endpoint nobody chose instead of being told.
    """
    directory = config_root / MODEL
    try:
        endpoint = JsonDirConfigResolver(directory).resolve(model)
    except LLMConfigError as unattached:
        raise ConfigError(
            f"the {model!r} embedder is a resource this deployment attaches, and "
            f"{unattached}"
        ) from unattached
    if not endpoint.base_url:
        raise ConfigError(
            f"{directory / model}.json declares no base_url; an embedder with none is a client "
            "pointed at whatever the SDK defaults to, which is not an endpoint anyone chose"
        )
    return endpoint


def hosted_encoder(endpoint: LLMConfig) -> Encoder:
    """One document into one vector, from the endpoint that file named.

    A closure over one client and no filesystem, which is the same split as the two builders below:
    reading where the endpoint is and calling it are two things, and only the first opens a file.
    Constructing a client sends nothing, so composing an engine still makes no network call.

    **One call per document**, because `Encoder` is one document at a time and a synchronous
    per-call signature has nothing to batch with. Against a local model that cost nothing; against
    an endpoint it is a round trip per record. The plural member that would fix it is a seventh on a
    protocol I21 says has six, so it is its own task and it lands before the pilot.
    """
    client = openai.OpenAI(
        api_key=endpoint.api_key, base_url=endpoint.base_url, timeout=endpoint.timeout
    )

    def encode(document: str) -> list[float]:
        answered = client.embeddings.create(model=endpoint.model, input=document)
        return list(answered.data[0].embedding)

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
    implementation_named(MODALITIES, BUILT_MODALITIES, modality.name)
    resolved = implementation_named(PROFILES, BUILT_PROFILES, profile.name)(
        modality, profile, encode, question
    )
    registry = Registry()
    registry.register_modality(modality.name, resolved)
    registry.register_profile(profile.name, resolved)
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
    so this is where it is constructed and `composed_engine` is where a caller says *not
    that one*.
    """
    declared_profile = read_manifest(config_root, PROFILES, profile)
    declared_modality = read_manifest(
        config_root, MODALITIES, paired_modality(declared_profile.declares, modality)
    )
    declared_thresholds = read_thresholds(params)
    declared_question = read_question_template(config_root, declared_profile.declares)
    embedder = attached_endpoint(
        config_root, embedding_model(declared_modality.declares)
    )
    files = (
        declared_modality,
        declared_profile,
        declared_thresholds,
        declared_question,
    )
    return composed_engine(
        modality=declared_modality.declares,
        profile=declared_profile.declares,
        encode=hosted_encoder(embedder),
        question=declared_question.declares,
        thresholds=declared_thresholds.declares,
        policy_digests={file.path: file.digest for file in files},
        personal_data_verifier=personal_data_verifier,
        jury_panel=jury_panel,
        question_store=question_store or SqlQuestionStore(sessions_to(store_engine())),
    )
