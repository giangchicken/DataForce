"""The published surface: what a caller gets, and what it does not have to have.

Three claims are worth a test of their own. Records can be built with no filesystem
anywhere, which is the whole point of the engine taking parsed declarations. An
engine opens against a config root that is not this repository's, which is what a
web handler or another codebase does. And a run records what it read, which is what
replaces DVC's declared dependencies now that nothing else tracks lineage.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG, PARAMS

from dataforce import api
from dataforce.modalities.text import TextModality
from dataforce.profiles.tool_decision import ToolDecisionProfile, build_record
from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest
from dataforce.shared.registry import Registry

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"

PROVENANCE = {
    "source": {
        "file_sha256": "0" * 64,
        "offset": 0,
        "ingested_at": "2026-08-20T00:00:00Z",
    },
    "producer": {"modality": "text@1", "profile": "tool_decision@1"},
}

# The two declarations, spelled out rather than read, so the test below can prove
# that building a record needs no file at all -- not even a manifest on disk.
TEXT_DECLARED = Manifest(
    name="text",
    version="1",
    declared={
        "version": "1",
        "embedding": {
            "model": "minishlab/potion-multilingual-128M",
            "exclude_roles": ["system"],
        },
    },
)
TOOL_DECISION_DECLARED = Manifest(
    name="tool_decision",
    version="1",
    declared={
        "version": "1",
        "modality": "text",
        "prompts": {"question": "profiles/tool_decision/question.v1"},
        "answer_control": "per_name_arguments",
        "shape": "legacy_system_prompt",
        "roles": {
            "instruction": "system",
            "conversation": ["user"],
            "target": "assistant",
        },
        "label": {"at": "label"},
        "meta": {
            "labelling_model": "llm_model",
            "prior_label": "orig_label",
            "label_provenance": "label_source",
            "human_checked": "human_checked",
            "human_checked_by": "human_check_src",
        },
        "gold": {"from": "human_checked"},
    },
)


def raw_item(catalog: str, label: list[str]) -> dict[str, Any]:
    return {
        "idx": 1,
        "messages": [
            {
                "role": "system",
                "content": (FIXTURES / "catalogs" / catalog).read_text(
                    encoding="utf-8"
                ),
            },
            {"role": "user", "content": "cho tôi hỏi một chút"},
            {"role": "assistant", "content": f"{label}".replace("'", '"')},
        ],
        "meta": {"label": label, "llm_model": "gemma-4-31B-it", "source_index": 1},
        build_record.PROVENANCE_KEY: PROVENANCE,
    }


# --- an engine with no files behind it ----------------------------------------


def test_records_are_built_with_no_filesystem_anywhere() -> None:
    """Requirement 2. Both axes are handed declarations, a template and an integer.

    No config root, no manifest on disk, no path named. This is the assertion that
    an in-process caller -- a web handler, a notebook -- depends on.
    """
    engine = api.Engine(
        modality=TextModality(TEXT_DECLARED),
        profile=ToolDecisionProfile(
            TOOL_DECISION_DECLARED,
            question_template="Tập trung vào: {{focus}}",
            answer_ceiling=3,
        ),
        registry=Registry(),
        policy=(),
    )

    records = list(
        api.build_records(
            engine,
            [
                raw_item("one_tool.txt", ["Lookup00_0a"]),
                raw_item("eight_tools.txt", []),
            ],
        )
    )

    assert [record.label for record in records] == [["Lookup00_0a"], []]
    assert all(len(record.rid) == 16 for record in records)
    assert {record.producer.profile for record in records} == {"tool_decision@1"}
    assert engine.producer == {"modality": "text@1", "profile": "tool_decision@1"}


# --- an engine opened against somebody else's config root ---------------------


@pytest.fixture
def elsewhere(tmp_path: Path) -> Path:
    """This repository's policy, copied somewhere that is not this repository."""
    shutil.copytree(CONFIG, tmp_path / "policy")
    shutil.copy(PARAMS, tmp_path / "params.yaml")
    return tmp_path


def test_an_engine_opens_against_a_config_root_that_is_not_this_repository(
    elsewhere: Path,
) -> None:
    engine = api.open_engine(
        profile="tool_decision",
        config_root=elsewhere / "policy",
        params=elsewhere / "params.yaml",
    )

    assert engine.modality.name == "text"
    assert engine.profile.name == "tool_decision"
    assert all(path.is_file() for path in engine.policy)
    assert all(elsewhere in path.parents for path in engine.policy)


def test_the_modality_is_an_assertion_and_a_wrong_one_hard_stops(
    elsewhere: Path,
) -> None:
    """Naming no modality takes the profile at its word; naming a different one stops."""
    opened = api.open_engine(
        profile="tool_decision",
        modality="text",
        config_root=elsewhere / "policy",
        params=elsewhere / "params.yaml",
    )
    assert opened.modality.name == "text"

    with pytest.raises(ConfigError, match="composes with modality 'text'"):
        api.open_engine(
            profile="tool_decision",
            modality="audio",
            config_root=elsewhere / "policy",
            params=elsewhere / "params.yaml",
        )


def test_an_unknown_profile_names_the_ones_that_exist(elsewhere: Path) -> None:
    with pytest.raises(ConfigError, match="tool_decision"):
        api.open_engine(
            profile="nothing_declares_this",
            config_root=elsewhere / "policy",
            params=elsewhere / "params.yaml",
        )


# --- what a run records ------------------------------------------------------


def test_the_run_manifest_records_every_policy_file_and_both_versions(
    elsewhere: Path,
) -> None:
    """Requirement 9. This is what replaces DVC's declared dependencies."""
    engine = api.open_engine(
        profile="tool_decision",
        config_root=elsewhere / "policy",
        params=elsewhere / "params.yaml",
    )
    artifact = elsewhere / "loaded.jsonl"
    artifact.write_text('{"rid": "0123456789abcdef"}\n', encoding="utf-8")

    recorded = api.run_manifest(engine, artifacts={"loaded": artifact})

    assert recorded["producer"] == {
        "modality": "text@1",
        "profile": "tool_decision@1",
    }
    assert set(recorded["policy"]) == {str(path) for path in engine.policy}
    assert sorted(Path(named).name for named in recorded["policy"]) == [
        "params.yaml",
        "question.v1.txt",
        "text.yaml",
        "tool_decision.yaml",
    ]
    assert all(len(digest) == 64 for digest in recorded["policy"].values())
    assert recorded["artifacts"]["loaded"] == api.file_digest(artifact)


def test_two_manifests_of_one_unchanged_run_are_identical(elsewhere: Path) -> None:
    """Invariant 14, as it now reads: two runs agreeing is two manifests agreeing."""
    opened = {
        "profile": "tool_decision",
        "config_root": elsewhere / "policy",
        "params": elsewhere / "params.yaml",
    }
    artifact = elsewhere / "loaded.jsonl"
    artifact.write_text('{"rid": "0123456789abcdef"}\n', encoding="utf-8")

    first = api.run_manifest(api.open_engine(**opened), artifacts={"loaded": artifact})
    second = api.run_manifest(api.open_engine(**opened), artifacts={"loaded": artifact})

    assert first == second

    (elsewhere / "params.yaml").write_text("max_answer_cardinality: 9\n", "utf-8")
    after = api.run_manifest(api.open_engine(**opened), artifacts={"loaded": artifact})

    assert after != first, "a changed policy file has to change the manifest"
