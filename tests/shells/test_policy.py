"""T27 · the readers: a config file becomes a declaration, and the digest that says which file.

`edge/policy.py` is the only module that turns `config/<axis>/*.yaml`, `params.yaml` and a prompt
template into something the engine can be built out of. What is worth proving here is not the
parsing -- pydantic does that and `tests/stages/test_manifest.py` states what the type refuses --
but the three things a reader adds around it:

**A file that is not there is a `ConfigError`, not an empty declaration.** `read_yaml` answers `{}`
for a file it cannot read and `read_txt` answers `""`, which is the right default for a tool reading
a corpus and the wrong one for a run's own configuration: a missing `params.yaml` read as `{}` is an
engine that quietly holds no thresholds at all.

**Requirement 40's filename check.** The identity is the filename, so only something holding a path
can see it, and this is the module that holds one.

**The digest, and the name it is recorded under.** A run manifest keyed by the path a deployment
happened to use would differ between two checkouts of one commit, which is I14 failing for a reason
that is not a configuration change.

Every fixture is invented (AGENTS.md §9).
"""

from pathlib import Path

import pytest

from dataforce.edge.policy import (
    MODALITIES,
    PROFILES,
    read_manifest,
    read_question_template,
    read_thresholds,
)
from dataforce.errors import ConfigError

MODALITY = """\
# A modality nobody ships, declaring the two keys its implementation reads.
name: text2text
version: "1"
embedding:
  model: a-static-embedder
  exclude_roles: [system]
language: vi
"""

PROFILE = """\
name: tool_decision
version: "1"
modality: text2text
prompts:
  question: profiles/tool_decision/question.v2
max_calls: 2
answer_control: names_and_json_arguments
shape: openai_chat_completion
roles:
  target: assistant
label:
  at: label
"""

TEMPLATE = "Những tool nào cần được gọi?\n"

PARAMS = """\
enable_redact: false
thresholds:
  aggregate:
    overlap_floor: 1
"""

QUESTION_AT = "config/prompts/profiles/tool_decision/question.v2.txt"


def a_config(
    root: Path,
    *,
    modality: str = MODALITY,
    profile: str = PROFILE,
    template: str | None = TEMPLATE,
) -> Path:
    """A `config/` tree holding both manifests and the template the profile's manifest names."""
    config = root / "config"
    (config / MODALITIES).mkdir(parents=True)
    (config / MODALITIES / "text2text.yaml").write_text(modality, encoding="utf-8")
    (config / PROFILES).mkdir(parents=True)
    (config / PROFILES / "tool_decision.yaml").write_text(profile, encoding="utf-8")
    if template is not None:
        asked = config / "prompts" / "profiles" / "tool_decision"
        asked.mkdir(parents=True)
        (asked / "question.v2.txt").write_text(template, encoding="utf-8")
    return config


def a_params(root: Path, declared: str = PARAMS) -> Path:
    """One `params.yaml`, wherever a deployment keeps it."""
    path = root / "params.yaml"
    path.write_text(declared, encoding="utf-8")
    return path


# --- a manifest ---


def test_a_manifest_comes_back_parsed(tmp_path: Path) -> None:
    """Identity off the file, and everything the reader did not route kept verbatim."""
    declared = read_manifest(a_config(tmp_path), PROFILES, "tool_decision").declares

    assert (declared.name, declared.version, declared.modality) == (
        "tool_decision",
        "1",
        "text2text",
    )
    assert declared.declarations["max_calls"] == 2


def test_a_modality_manifest_composes_with_no_modality(tmp_path: Path) -> None:
    """Its own `name` is the pair, and a file with no `modality:` key is not a broken file."""
    assert (
        read_manifest(a_config(tmp_path), MODALITIES, "text2text").declares.modality
        is None
    )


def test_the_name_inside_the_file_must_agree_with_the_filename(tmp_path: Path) -> None:
    """Requirement 40: the filename is the identity, and this is the reader that checks it."""
    renamed = PROFILE.replace("name: tool_decision", "name: summarize", 1)

    with pytest.raises(ConfigError, match="summarize"):
        read_manifest(a_config(tmp_path, profile=renamed), PROFILES, "tool_decision")


def test_a_manifest_that_is_not_there_names_the_file_it_is_not_at(
    tmp_path: Path,
) -> None:
    """`read_yaml` answers `{}` for a file that does not exist, which is not a declaration."""
    with pytest.raises(ConfigError, match="summarize.yaml"):
        read_manifest(a_config(tmp_path), PROFILES, "summarize")


def test_an_empty_manifest_is_refused_rather_than_read_as_declaring_nothing(
    tmp_path: Path,
) -> None:
    """The other half of the same default: a file that is there and says nothing."""
    with pytest.raises(ConfigError, match="empty"):
        read_manifest(a_config(tmp_path, profile="\n"), PROFILES, "tool_decision")


def test_a_manifest_that_does_not_validate_is_a_config_error(tmp_path: Path) -> None:
    """Requirement 43: `ConfigError` is the only exception, so pydantic's does not escape."""
    unquoted = PROFILE.replace('version: "1"', "version: 1", 1)

    with pytest.raises(ConfigError, match="tool_decision.yaml"):
        read_manifest(a_config(tmp_path, profile=unquoted), PROFILES, "tool_decision")


# --- the digest, and what it is recorded under ---


def test_the_path_recorded_is_the_layouts_and_not_the_deployments(
    tmp_path: Path,
) -> None:
    """I14 across two checkouts: a key built from `tmp_path` would differ for every run."""
    read = read_manifest(a_config(tmp_path), PROFILES, "tool_decision")

    assert read.path == "config/profiles/tool_decision.yaml"


def test_one_unchanged_file_reads_the_same_digest_twice(tmp_path: Path) -> None:
    """I14's half of Requirement 45: an unchanged configuration is the same configuration."""
    config = a_config(tmp_path)

    assert (
        read_manifest(config, PROFILES, "tool_decision").digest
        == read_manifest(config, PROFILES, "tool_decision").digest
    )


def test_a_changed_comment_is_a_changed_policy_file(tmp_path: Path) -> None:
    """The digest is over the file and not over what was parsed out of it: a reviewed line moved."""
    commented = "# why this profile declares two calls and not three\n" + PROFILE

    assert (
        read_manifest(a_config(tmp_path / "one"), PROFILES, "tool_decision").digest
        != read_manifest(
            a_config(tmp_path / "two", profile=commented), PROFILES, "tool_decision"
        ).digest
    )


# --- the thresholds ---


def test_the_thresholds_come_back_as_the_file_declares_them(tmp_path: Path) -> None:
    """`Engine.thresholds` is this file, parsed, and no stage holds a number of its own (P25)."""
    read = read_thresholds(a_params(tmp_path))

    assert read.declares["thresholds"]["aggregate"]["overlap_floor"] == 1
    assert read.declares["enable_redact"] is False


def test_params_is_recorded_under_its_own_filename(tmp_path: Path) -> None:
    """Which file was read is a fact worth keeping; where the checkout sits is not."""
    assert read_thresholds(a_params(tmp_path)).path == "params.yaml"


def test_a_params_file_that_is_not_there_stops_the_run(tmp_path: Path) -> None:
    """Read as `{}` this is an engine whose every threshold reader refuses, one record at a time."""
    with pytest.raises(ConfigError, match="params.yaml"):
        read_thresholds(tmp_path / "params.yaml")


# --- the question template ---


def test_the_template_is_resolved_from_the_name_the_profile_declares(
    tmp_path: Path,
) -> None:
    """The one profile key the edge reads: the profile is handed a string, because it opens no file."""
    config = a_config(tmp_path)
    profile = read_manifest(config, PROFILES, "tool_decision").declares

    read = read_question_template(config, profile)

    assert read.declares == TEMPLATE
    assert read.path == QUESTION_AT


def test_a_template_the_profile_names_and_nobody_wrote_names_the_file(
    tmp_path: Path,
) -> None:
    """A declaration pointing at nothing is a `ConfigError` before a record, not an empty question."""
    config = a_config(tmp_path, template=None)
    profile = read_manifest(config, PROFILES, "tool_decision").declares

    with pytest.raises(ConfigError, match="question.v2.txt"):
        read_question_template(config, profile)


def test_a_profile_declaring_no_template_says_which_key_is_missing(
    tmp_path: Path,
) -> None:
    """§ *Configuration*: every key a manifest declares has a reader, and the reader validates it."""
    silent = PROFILE.replace(
        "prompts:\n  question: profiles/tool_decision/question.v2\n", "", 1
    )
    config = a_config(tmp_path, profile=silent)
    profile = read_manifest(config, PROFILES, "tool_decision").declares

    with pytest.raises(ConfigError, match="prompts.question"):
        read_question_template(config, profile)
