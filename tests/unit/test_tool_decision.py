"""`tool_decision`'s validity checks, training example, group key and controls.

Rules 4 and 5 of § *Rules a profile must satisfy* are proved here -- `build_record`
preserving what it does not own is in `test_build_record.py`, and
`training_example` reproducing the record's answer is below. Rules 1 to 3 are
in `test_answers.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agent_toolkit.file_utils import read_yaml
from conftest import CONFIG, TEXT, TOOL_DECISION

from dataforce.api import tool_decision_profile
from dataforce.declared.thresholds import max_answer_cardinality
from dataforce.profiles.tool_decision import build_record
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import Record
from dataforce.shared.registry import Registry

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"
CATALOGS = FIXTURES / "catalogs"

PROVENANCE = {
    "source": {
        "file_sha256": "0" * 64,
        "offset": 1,
        "ingested_at": "2026-08-19T00:00:00Z",
    },
    "producer": {"modality": "text@1", "profile": "tool_decision@1"},
}


def raw_item(
    *, catalog: str = "eight_tools.txt", label: list[str], assistant: str | None = None
) -> dict[str, Any]:
    return {
        "idx": 1,
        "messages": [
            {
                "role": "system",
                "content": (CATALOGS / catalog).read_text(encoding="utf-8"),
            },
            {"role": "user", "content": "cho tôi hỏi một chút"},
            {
                "role": "assistant",
                "content": assistant
                if assistant is not None
                else json.dumps(label, ensure_ascii=False),
            },
        ],
        "meta": {"label": label, "llm_model": "gemma-4-31B-it", "source_index": 1},
        build_record.PROVENANCE_KEY: PROVENANCE,
    }


def record_for(**kwargs: Any) -> Record:
    raw = raw_item(**kwargs)
    return TOOL_DECISION.build_record(raw, TEXT.content_parts(raw))


PARAMS = FIXTURES.parents[2] / "params.yaml"


@pytest.fixture
def check() -> dict[str, Any]:
    """The four checks, bound to the profile's contract and the committed ceiling."""
    return TOOL_DECISION.validity_checks()


# --- registration ------------------------------------------------------------


def test_the_profile_composes_with_the_text_modality() -> None:
    registry = Registry()
    registry.register_modality(TEXT)
    registry.register_profile(TOOL_DECISION)

    assert registry.profile("tool_decision", modality="text") is TOOL_DECISION


# --- the four validity checks ------------------------------------------------


def test_a_well_formed_record_fails_no_check(check: dict[str, Any]) -> None:
    record = record_for(label=["Lookup00_0a"])

    assert [name for name, fires in check.items() if fires(record)] == []


def test_validity_checks_are_the_four_names_params_declares_counts_for() -> None:
    """The names are identifiers `params.yaml` keys on, so they are not free to drift."""
    built = TOOL_DECISION.validity_checks()

    assert tuple(built) == build_record.CHECK_NAMES
    assert set(built) == set(read_yaml(PARAMS)["invalid_counts"])


def test_label_assistant_mismatch_fires_when_the_two_targets_disagree(
    check: dict[str, Any],
) -> None:
    record = record_for(label=["Lookup00_0a"], assistant='["Lookup01_1a"]')

    assert check["label_assistant_mismatch"](record)


def test_label_assistant_mismatch_ignores_order_and_repetition(
    check: dict[str, Any],
) -> None:
    record = record_for(
        label=["Lookup00_0a", "Lookup01_1a"], assistant='["Lookup01_1a", "Lookup00_0a"]'
    )

    assert not check["label_assistant_mismatch"](record)


def test_an_unparseable_assistant_message_is_a_mismatch(check: dict[str, Any]) -> None:
    """Agreement that cannot be confirmed is not agreement."""
    record = record_for(label=["Lookup00_0a"], assistant="tôi sẽ gọi tool")

    assert check["label_assistant_mismatch"](record)


def test_label_not_in_catalog_fires_when_the_target_names_a_tool_never_offered(
    check: dict[str, Any],
) -> None:
    record = record_for(catalog="one_tool.txt", label=["Lookup07_7a"])

    assert check["label_not_in_catalog"](record)
    assert not check["empty_catalog"](record)


def test_a_name_with_a_dot_or_a_tab_is_in_its_catalog(check: dict[str, Any]) -> None:
    """The convention that decides whether 722 records are invalid or none are."""
    record = record_for(
        catalog="odd_names.txt", label=["card.search_faq", "calculate_triangl\te_area"]
    )

    assert not check["label_not_in_catalog"](record)


def test_empty_catalog_fires_when_the_record_offers_no_tools(
    check: dict[str, Any],
) -> None:
    record = record_for(catalog="header_without_entries.txt", label=[])

    assert check["empty_catalog"](record)
    assert not check["label_not_in_catalog"](record)


def test_label_cardinality_anomaly_reads_its_ceiling_from_params(
    check: dict[str, Any],
) -> None:
    record = record_for(
        label=["Lookup00_0a", "Lookup01_1a", "Lookup02_2a", "Lookup03_3a"],
        assistant='["Lookup00_0a", "Lookup01_1a", "Lookup02_2a", "Lookup03_3a"]',
    )

    assert check["label_cardinality_anomaly"](record)
    assert not check["label_cardinality_anomaly"](record_for(label=["Lookup00_0a"]))


def test_an_undeclared_ceiling_fails_before_the_profile_that_would_check_with_it(
    tmp_path: Path,
) -> None:
    """Not on the first of 21,172 records, and now earlier still.

    The ceiling is a constructor argument, so an undeclared one fails while the
    profile is being built rather than when a stage asks it for its checks.
    """
    (tmp_path / "params.yaml").write_text("source: {}\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="max_answer_cardinality"):
        max_answer_cardinality(params=tmp_path / "params.yaml")

    with pytest.raises(ConfigError, match="max_answer_cardinality"):
        tool_decision_profile(config_root=CONFIG, params=tmp_path / "params.yaml")


# --- training example, group key, controls ------------------------------------


def test_export_states_the_label_in_both_places() -> None:
    exported = TOOL_DECISION.training_example(
        record_for(label=["Lookup00_0a", "Lookup01_1a"])
    )

    assistant = next(m for m in exported["messages"] if m["role"] == "assistant")
    assert json.loads(assistant["content"]) == exported["meta"]["label"]
    assert exported["meta"]["label"] == ["Lookup00_0a", "Lookup01_1a"]


def test_export_keeps_the_source_messages_shape() -> None:
    exported = TOOL_DECISION.training_example(record_for(label=[]))

    assert [m["role"] for m in exported["messages"]] == ["system", "user", "assistant"]
    assert (
        json.loads(
            next(m for m in exported["messages"] if m["role"] == "assistant")["content"]
        )
        == []
    )


def test_export_preserves_the_marker_dsl_in_the_system_message() -> None:
    exported = TOOL_DECISION.training_example(record_for(label=[]))

    system = next(m for m in exported["messages"] if m["role"] == "system")["content"]
    for marker in (
        "{trigger}",
        "{hold_other}",
        "{hold_missing}",
        "{constraint}",
        "{or}",
    ):
        assert marker in system


def test_the_group_key_is_the_catalog_and_not_the_source_index() -> None:
    one = record_for(label=["Lookup00_0a"])
    other = record_for(label=[])

    assert one.meta["source_index"] == other.meta["source_index"]
    assert TOOL_DECISION.group_key(one) == TOOL_DECISION.group_key(other)
    assert TOOL_DECISION.group_key(one) != TOOL_DECISION.group_key(
        record_for(catalog="one_tool.txt", label=[])
    )


def test_the_answer_control_offers_exactly_this_record_s_catalog() -> None:
    control = TOOL_DECISION.answer_config(record_for(catalog="one_tool.txt", label=[]))

    assert control.count("<Choice ") == 1
    assert 'value="Lookup00_0a"' in control


def test_a_tab_in_a_tool_name_survives_the_answer_control() -> None:
    """An XML parser folds a literal tab in an attribute to a space; a reference is kept."""
    control = TOOL_DECISION.answer_config(record_for(catalog="odd_names.txt", label=[]))

    assert "&#9;" in control
    assert "calculate_triangl\te_area" not in control


def test_the_question_leaves_the_marker_dsl_alone() -> None:
    """Single braces are the DSL's; `slot_filling` only fills doubled ones."""
    asked = TOOL_DECISION.question_text(record_for(label=[]), "{trigger} ở lượt cuối")

    assert "{trigger} ở lượt cuối" in asked
    assert "{{focus}}" not in asked
