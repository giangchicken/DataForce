"""T27 · the composition root: one run's pair, resolved, registered and handed its ports.

`open_engine` is the only builder of an `Engine` (P19) and the only module that names a concrete
axis (Requirement 38). Everything it does is a decision a test can state:

**Which modality.** Naming none takes the profile at its word, which is what makes
`open_engine(profile=...)` the ordinary call; naming a different one is refused rather than
honoured, because a profile reads content one modality produced.

**With no filesystem anywhere.** `composed_engine` takes two `Manifest` objects and a template
string, and that is the whole of what a web handler and an in-process caller share -- the reader
above it is what turns paths into those three things, and nothing below it can tell which one ran.

**Nothing is loaded that a run may never use.** Composing an engine makes no network call: the
static embedder behind `duplicate_check` is a download, and a run of `label_check` alone should not
pay for one. The modality below names a model nobody has published, so an eager loader fails here.

The one test that reads the repository is deliberate: `config/` and `params.yaml` are what a
deployment actually composes, and a configuration that no longer composes is a break nothing else
in this suite would see. Every other fixture is invented (AGENTS.md §9).
"""

from pathlib import Path

import pytest

from dataforce.edge.bootstrap import composed_engine, open_engine
from dataforce.edge.policy import MODALITIES, PROFILES, read_manifest
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.pipeline.params import declared_switch

from .test_policy import MODALITY, PROFILE, TEMPLATE, a_config, a_params

REPOSITORY = Path(__file__).resolve().parents[2]


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

    assert (engine.modality.name, engine.modality.version) == ("text2text", "1")
    assert (engine.profile.name, engine.profile.modality) == (
        "tool_decision",
        "text2text",
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

    assert (engine.modality.name, engine.profile.name) == ("text2text", "tool_decision")


def test_naming_the_one_it_composes_with_is_the_same_run(tmp_path: Path) -> None:
    """Saying it out loud is permitted; it just may not disagree."""
    engine = open_engine(
        profile="tool_decision",
        modality="text2text",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert (engine.modality.name, engine.profile.name) == ("text2text", "tool_decision")


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
    """P25: no stage holds a number, so the file has to arrive intact at `pipeline/params.py`."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert declared_switch(engine, "enable_redact") is False
    assert engine.thresholds["thresholds"]["aggregate"]["overlap_floor"] == 1


def test_opening_an_engine_attaches_the_question_store(tmp_path: Path) -> None:
    """P19: the one place a connection is reached for. Building the pool connects to nothing."""
    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path),
        params=a_params(tmp_path),
    )

    assert engine.question_store is not None


def test_composing_an_engine_loads_no_model(tmp_path: Path) -> None:
    """`a-static-embedder` is published nowhere: an eager loader would go to the network here."""
    named = MODALITY.replace("a-static-embedder", "nobody/has-published-this", 1)

    engine = open_engine(
        profile="tool_decision",
        config_root=a_config(tmp_path, modality=named),
        params=a_params(tmp_path),
    )

    assert engine.modality.name == "text2text"


# --- the configuration this repository ships ---


def test_the_configuration_this_repository_ships_composes() -> None:
    """The one test here that reads `config/`: a manifest nobody can compose is a broken run."""
    engine = open_engine(
        profile="tool_decision",
        config_root=REPOSITORY / "config",
        params=REPOSITORY / "params.yaml",
    )

    assert (engine.modality.name, engine.profile.name) == ("text2text", "tool_decision")
    assert engine.thresholds["thresholds"]["triage"]["self_agreement_floor"] == 0.7
