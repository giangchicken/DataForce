"""T27 · the composition root: one run's pair, resolved, registered and handed its ports.

`open_engine` is the only builder of an `Engine` and the only module that names a concrete
axis (Requirement 38). Everything it does is a decision a test can state:

**Which modality.** Naming none takes the profile at its word, which is what makes
`open_engine(profile=...)` the ordinary call; naming a different one is refused rather than
honoured, because a profile reads content one modality produced.

**With no filesystem anywhere.** `composed_engine` takes two `Manifest` objects and a template
string, and that is the whole of what a web handler and an in-process caller share -- the reader
above it is what turns paths into those three things, and nothing below it can tell which one ran.

**The embedder is read at composition and called nowhere near it.** That is the opposite of what
these tests used to prove: the model was a download, so the point was that nothing was loaded until
the first vector. It is an endpoint now, so the point is that a deployment which attached none is
told before the first record, and that composing still sends nothing -- the endpoint below is
`.invalid`, which resolves nowhere.

The one test that reads the repository is deliberate: `config/` and `params.yaml` are what a
deployment actually composes, and a configuration that no longer composes is a break nothing else in
this suite would see. It attaches the committed `.example` because the endpoint file itself is not in
the history, which makes it the test that would also notice an example that stopped being a
usable file. Every other fixture is invented.
"""

import shutil
from pathlib import Path

import pytest

from dataforce.edge.bootstrap import (
    BUILT_MODALITIES,
    BUILT_PROFILES,
    composed_engine,
    open_engine,
)
from dataforce.edge.policy import MODALITIES, PROFILES, read_manifest
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text import Encoder, Text2Text
from dataforce.pipeline.params import declared_switch

from .test_policy import ENDPOINT, PROFILE, TEMPLATE, a_config, a_params

REPOSITORY = Path(__file__).resolve().parents[2]
SHIPPED = REPOSITORY / "config"
EXAMPLE = "*.json.example"


def a_pair(root: Path) -> tuple[Manifest, Manifest]:
    """Both manifests, read the way `open_engine` reads them, for the no-filesystem builder."""
    config = a_config(root)
    return (
        read_manifest(config, MODALITIES, "text2text").declares,
        read_manifest(config, PROFILES, "tool_decision").declares,
    )


def no_vector(document: str) -> tuple[float, ...]:
    """An encoder that never loads anything: what the modality is handed where nothing embeds."""
    return (float(len(document)),)


# --- an engine with no filesystem anywhere ---


def test_an_engine_is_built_from_two_manifests_and_a_template(tmp_path: Path) -> None:
    """T27's first acceptance criterion, which is also Requirement 46's whole mechanism."""
    modality, profile = a_pair(tmp_path)

    engine = composed_engine(
        modality=modality,
        profile=profile,
        encode=no_vector,
        question=TEMPLATE,
    )

    assert (engine.modality.modality_name, engine.modality.modality_version) == (
        "text2text",
        "1",
    )
    assert (engine.profile.profile_name, engine.profile.profile_version) == (
        "tool_decision",
        "1",
    )


def test_both_axes_are_registered_under_the_names_their_manifests_gave_them(
    tmp_path: Path,
) -> None:
    """Requirement 38: both arrive through a registry, and this is the module that fills one."""
    modality, profile = a_pair(tmp_path)

    engine = composed_engine(
        modality=modality,
        profile=profile,
        encode=no_vector,
        question=TEMPLATE,
    )

    assert engine.registry.modality("text2text") is engine.modality
    assert engine.registry.profile("tool_decision") is engine.profile


def test_an_engine_with_no_filesystem_reaches_no_backing_service(
    tmp_path: Path,
) -> None:
    """*No filesystem anywhere* covers the store too: a port is attached, never assumed."""
    modality, profile = a_pair(tmp_path)

    engine = composed_engine(
        modality=modality,
        profile=profile,
        encode=no_vector,
        question=TEMPLATE,
    )

    assert engine.question_store is None
    assert (engine.jury_panel, engine.personal_data_verifier) == (None, None)


def test_a_name_nothing_implements_names_the_ones_that_are_built(
    tmp_path: Path,
) -> None:
    """A manifest is a declaration; something still has to answer to it."""
    config = a_config(
        tmp_path, profile=PROFILE.replace("tool_decision", "summarize", 1)
    )
    (config / PROFILES / "tool_decision.yaml").rename(
        config / PROFILES / "summarize.yaml"
    )
    modality = read_manifest(config, MODALITIES, "text2text").declares
    profile = read_manifest(config, PROFILES, "summarize").declares

    with pytest.raises(ConfigError, match="tool_decision"):
        composed_engine(
            modality=modality, profile=profile, encode=no_vector, question=TEMPLATE
        )


def test_two_manifests_that_disagree_are_refused_with_no_files_involved(
    tmp_path: Path,
) -> None:
    """The pair check is the builder's and not the reader's, so a request body cannot dodge it."""
    modality, profile = a_pair(tmp_path)
    other = modality.model_copy(update={"name": "speech2text"})

    with pytest.raises(ConfigError, match="text2text"):
        composed_engine(
            modality=other, profile=profile, encode=no_vector, question=TEMPLATE
        )


# --- which modality ---


def test_naming_no_modality_takes_the_profile_at_its_word(tmp_path: Path) -> None:
    """The ordinary call. The pair is a fact about the profile, stated in one place."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert (engine.modality.modality_name, engine.profile.profile_name) == (
        "text2text",
        "tool_decision",
    )


def test_naming_the_one_it_composes_with_is_the_same_run(tmp_path: Path) -> None:
    """Saying it out loud is permitted; it just may not disagree."""
    engine = open_engine(
        profile="tool_decision",
        modality="text2text",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert (engine.modality.modality_name, engine.profile.profile_name) == (
        "text2text",
        "tool_decision",
    )


def test_naming_a_different_modality_says_which_one_the_profile_composes_with(
    tmp_path: Path,
) -> None:
    """T27's second acceptance criterion. The message names the pair, because that is the fix."""
    with pytest.raises(ConfigError, match="text2text"):
        open_engine(
            profile="tool_decision",
            modality="speech2text",
            config_root=a_config(tmp_path),
            params=a_params(tmp_path),
        )


def test_a_profile_that_names_no_modality_cannot_be_composed(tmp_path: Path) -> None:
    """There is nothing to take at its word, and guessing would pair it with whatever is built."""
    unpaired = PROFILE.replace("modality: text2text\n", "", 1)

    with pytest.raises(ConfigError, match="names no modality"):
        open_engine(
            profile="tool_decision",
            config_root=a_config(tmp_path, profile=unpaired),
            params=a_params(tmp_path),
        )


# --- what the run read ---


def test_the_engine_carries_the_digest_of_every_policy_file_it_read(
    tmp_path: Path,
) -> None:
    """Requirement 45: four files, each recorded under what it is rather than where it was."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert sorted(engine.policy_digests) == [
        "config/modalities/text2text.yaml",
        "config/profiles/tool_decision.yaml",
        "config/prompts/profiles/tool_decision/question.v2.txt",
        "params.yaml",
    ]


def test_the_thresholds_reach_the_engine_where_a_stage_reads_them(
    tmp_path: Path,
) -> None:
    """No stage holds a number, so the file has to arrive intact at `pipeline/params.py`."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert declared_switch(engine, "enable_redact") is False
    assert engine.thresholds["thresholds"]["aggregate"]["overlap_floor"] == 1


def test_opening_an_engine_attaches_the_question_store(tmp_path: Path) -> None:
    """The one place a connection is reached for. Building the pool connects to nothing."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert engine.question_store is not None


def test_composing_an_engine_reaches_the_endpoint_it_resolved_not_at_all(
    tmp_path: Path,
) -> None:
    """The point survived the design and the reason did not: there is nothing to download now, so
    what would go wrong is a call. `.invalid` is reserved and resolves nowhere, so one would fail."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert engine.modality.modality_name == "text2text"


def test_a_deployment_that_attached_no_embedder_is_told_before_the_first_record(
    tmp_path: Path,
) -> None:
    """The file is a resource a deployment attaches, and an absent one stops the run
    at composition rather than part-way through `duplicate_check`."""
    with pytest.raises(ConfigError, match="an-attached-embedder"):
        open_engine(
            profile="tool_decision",
            config_root=a_config(tmp_path, endpoint=None),
            params=a_params(tmp_path),
        )


def test_an_embedder_that_names_no_endpoint_is_refused_rather_than_defaulted(
    tmp_path: Path,
) -> None:
    """The library's default for `base_url` is the SDK's own API, which for a corpus of real
    conversations is the one wrong answer that looks like a working run."""
    nowhere = ENDPOINT.replace('"base_url": "https://embeddings.invalid/v1", ', "", 1)

    with pytest.raises(ConfigError, match="base_url"):
        open_engine(
            profile="tool_decision",
            config_root=a_config(tmp_path, endpoint=nowhere),
            params=a_params(tmp_path),
        )


def test_the_embedders_file_is_not_one_of_the_policy_files(tmp_path: Path) -> None:
    """It holds the key, so digesting it would make two people at one endpoint two configurations
    and a rotated key a changed one -- I14 failing for something that is not a change."""
    config = a_config(tmp_path)
    rekeyed = ENDPOINT.replace('"invented"', '"invented-again"', 1)

    first = open_engine(
        profile="tool_decision", config_root=config, params=a_params(tmp_path)
    )
    (config / "model" / "an-attached-embedder.json").write_text(
        rekeyed, encoding="utf-8"
    )
    second = open_engine(
        profile="tool_decision", config_root=config, params=a_params(tmp_path)
    )

    assert first.policy_digests == second.policy_digests


# --- one object, two identities ---


def test_one_object_fills_both_slots(tmp_path: Path) -> None:
    """T52's shape: `ToolDecision` is a `Text2Text`, so a run resolves to one instance.

    Two slots and one object. `Engine` keeps both because a stage asks for what it needs by axis,
    and the registry keeps two namespaces because a name is only unique inside the
    `config/<axis>/` directory it was read from.
    """
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert engine.modality is engine.profile
    assert engine.registry.modality("text2text") is engine.registry.profile(
        "tool_decision"
    )


def test_every_built_profile_is_built_on_a_built_modality() -> None:
    """The wiring `composed_engine` no longer checks at runtime, checked where it costs nothing.

    A runtime `issubclass` in the builder would be a third statement of one fact, read at the one
    moment the manifests have already agreed. The fact worth holding is about these two literals:
    the class answering to a profile name has to be a subclass of some class answering to a modality
    name, or the containment is a claim in a docstring — the rule fails the build.
    """
    concepts = tuple(BUILT_MODALITIES.values())

    assert concepts, "a scan over no modalities would pass whatever it was pointed at"
    for name, module in BUILT_PROFILES.items():
        assert issubclass(module, concepts), name  # type: ignore[arg-type]


def test_a_second_module_in_the_family_shares_the_concept_it_is_inside(
    tmp_path: Path,
) -> None:
    """The test the whole task exists for: sharing, without a second implementation of anything.

    `Summarize` declares nothing. It is a `Text2Text`, so it reads content, embeds it, scans it and
    displays it exactly the way `tool_decision` does — which is what "a modality is a concept and a
    profile is one module inside it" is supposed to mean, and what it did not mean while the
    relationship was a string in a manifest.
    """

    class Summarize(Text2Text):
        """A second module in `text2text`, with nothing of its own but its identity."""

        def __init__(self, modality: Manifest, encode: Encoder) -> None:
            super().__init__(modality, encode)
            self.profile_name = "summarize"
            self.profile_version = "1"

    declared = read_manifest(a_config(tmp_path), MODALITIES, "text2text").declares
    shared = Summarize(declared, no_vector)

    assert (shared.modality_name, shared.profile_name) == ("text2text", "summarize")
    assert shared.content_parts({"messages": [{"role": "user", "content": "xin chào"}]})
    assert Summarize.content_parts is Text2Text.content_parts, (
        "a second module redeclaring a member of its concept is what inheritance was for"
    )
    assert shared.modality_version == Text2Text(declared, no_vector).modality_version


# --- the configuration this repository ships ---


def test_the_configuration_this_repository_ships_composes(tmp_path: Path) -> None:
    """The one test here that reads `config/`: a manifest nobody can compose is a broken run.

    The endpoint file is the deployment's and never in the history, so the `.example` beside it
    stands in -- which is also what makes an example that has stopped naming what the resolver reads
    a failure here rather than on somebody's first run.
    """
    attached = tmp_path / "config"
    shutil.copytree(SHIPPED, attached, ignore=shutil.ignore_patterns("model"))
    (attached / "model").mkdir()
    for example in (SHIPPED / "model").glob(EXAMPLE):
        shutil.copy(example, attached / "model" / example.stem)

    engine = open_engine(
        profile="tool_decision",
        config_root=attached,
        params=REPOSITORY / "params.yaml",
    )

    assert (engine.modality.modality_name, engine.profile.profile_name) == (
        "text2text",
        "tool_decision",
    )
    assert engine.thresholds["thresholds"]["triage"]["self_agreement_floor"] == 0.7
