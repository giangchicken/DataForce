"""`tool_decision` against the conformance suite, and its four validity checks.

The suite is the gate this profile has to pass before any stage will accept it, so
it is run here through the real registry rather than called directly: a profile that
only passes when invoked by its own test is not registered.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dataforce.modalities import registry as modality_registry
from dataforce.modalities.text import TEXT
from dataforce.profiles import conformance
from dataforce.profiles import registry as profile_registry
from dataforce.profiles.tool_decision import TOOL_DECISION, adapter, checks
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import Record

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
        adapter.PROVENANCE_KEY: PROVENANCE,
    }


def record_for(**kwargs: Any) -> Record:
    raw = raw_item(**kwargs)
    return TOOL_DECISION.adapt(raw, TEXT.load(raw))


@pytest.fixture(autouse=True)
def _params_are_the_repo_s(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The checks read a committed threshold; point them at it regardless of cwd.

    Cleared on the way out as well as in: the ceiling is cached, and a test that
    points it at a temporary file would otherwise leave that value behind.
    """
    monkeypatch.setattr(checks, "PARAMS", FIXTURES.parents[2] / "params.yaml")
    checks._max_cardinality.cache_clear()
    yield
    checks._max_cardinality.cache_clear()


# --- the suite ---------------------------------------------------------------


def test_the_profile_registers_and_the_suite_passes() -> None:
    report = profile_registry.register(TOOL_DECISION)

    assert report.ok, report.failures
    assert not report.barred_from_consensus_tier
    assert {check.name for check in report.checks} == {
        "delta_is_a_metric",
        "answers_survive_an_artifact",
        "consensus_is_deterministic_and_agrees_on_unanimity",
    }


def test_all_five_checks_pass_against_a_real_sample() -> None:
    """Including the two that need a raw item: adapt preserves, export reproduces."""
    raw = raw_item(label=["Lookup00_0a", "Lookup01_1a"])

    report = conformance.run_with_sample(TOOL_DECISION, raw, TEXT.load(raw))

    assert report.ok, report.failures
    assert len(report.checks) == 5


def test_the_empty_answer_is_among_the_answers_the_suite_tries() -> None:
    """The case that inverts the signal on a third of this corpus if δ gets it wrong."""
    has_empty, empty = conformance.empty_answer(TOOL_DECISION.answer_schema)

    assert (has_empty, empty) == (True, [])


def test_the_profile_composes_with_the_text_modality() -> None:
    modality_registry.register(TEXT)
    profile_registry.register(TOOL_DECISION)

    assert profile_registry.get("tool_decision", modality="text") is TOOL_DECISION


def test_a_zero_label_record_passes_the_suite_too() -> None:
    raw = raw_item(label=[])

    report = conformance.run_with_sample(TOOL_DECISION, raw, TEXT.load(raw))

    assert report.ok, report.failures


# --- the four validity checks ------------------------------------------------


def test_a_well_formed_record_fails_no_check() -> None:
    record = record_for(label=["Lookup00_0a"])

    fired = [
        name for name, check in TOOL_DECISION.validity_checks().items() if check(record)
    ]

    assert fired == []


def test_validity_checks_are_the_four_the_spec_names() -> None:
    assert list(TOOL_DECISION.validity_checks()) == [
        "label_assistant_mismatch",
        "label_not_in_catalog",
        "empty_catalog",
        "label_cardinality_anomaly",
    ]


def test_label_assistant_mismatch_fires_when_the_two_targets_disagree() -> None:
    record = record_for(label=["Lookup00_0a"], assistant='["Lookup01_1a"]')

    assert checks.label_assistant_mismatch(record)


def test_label_assistant_mismatch_ignores_order_and_repetition() -> None:
    record = record_for(
        label=["Lookup00_0a", "Lookup01_1a"], assistant='["Lookup01_1a", "Lookup00_0a"]'
    )

    assert not checks.label_assistant_mismatch(record)


def test_an_unparseable_assistant_message_is_a_mismatch() -> None:
    """Agreement that cannot be confirmed is not agreement."""
    record = record_for(label=["Lookup00_0a"], assistant="tôi sẽ gọi tool")

    assert checks.label_assistant_mismatch(record)


def test_label_not_in_catalog_fires_when_the_target_names_a_tool_never_offered() -> (
    None
):
    record = record_for(catalog="one_tool.txt", label=["Lookup07_7a"])

    assert checks.label_not_in_catalog(record)
    assert not checks.empty_catalog(record)


def test_a_name_with_a_dot_or_a_tab_is_in_its_catalog() -> None:
    """The convention that decides whether 722 records are invalid or none are."""
    record = record_for(
        catalog="odd_names.txt", label=["card.search_faq", "calculate_triangl\te_area"]
    )

    assert not checks.label_not_in_catalog(record)


def test_empty_catalog_fires_when_the_record_offers_no_tools() -> None:
    record = record_for(catalog="header_without_entries.txt", label=[])

    assert checks.empty_catalog(record)
    assert not checks.label_not_in_catalog(record)


def test_label_cardinality_anomaly_reads_its_ceiling_from_params() -> None:
    record = record_for(
        label=["Lookup00_0a", "Lookup01_1a", "Lookup02_2a", "Lookup03_3a"],
        assistant='["Lookup00_0a", "Lookup01_1a", "Lookup02_2a", "Lookup03_3a"]',
    )

    assert checks.label_cardinality_anomaly(record)
    assert not checks.label_cardinality_anomaly(record_for(label=["Lookup00_0a"]))


def test_an_undeclared_ceiling_is_a_config_error_not_a_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(checks, "PARAMS", tmp_path / "params.yaml")
    (tmp_path / "params.yaml").write_text("source: {}\n", encoding="utf-8")
    checks._max_cardinality.cache_clear()

    with pytest.raises(ConfigError, match="max_answer_cardinality"):
        checks.label_cardinality_anomaly(record_for(label=[]))


# --- export, group key, controls ---------------------------------------------


def test_export_states_the_label_in_both_places() -> None:
    exported = TOOL_DECISION.export(record_for(label=["Lookup00_0a", "Lookup01_1a"]))

    assistant = next(m for m in exported["messages"] if m["role"] == "assistant")
    assert json.loads(assistant["content"]) == exported["meta"]["label"]
    assert exported["meta"]["label"] == ["Lookup00_0a", "Lookup01_1a"]


def test_export_keeps_the_source_messages_shape() -> None:
    exported = TOOL_DECISION.export(record_for(label=[]))

    assert [m["role"] for m in exported["messages"]] == ["system", "user", "assistant"]
    assert (
        json.loads(
            next(m for m in exported["messages"] if m["role"] == "assistant")["content"]
        )
        == []
    )


def test_export_preserves_the_marker_dsl_in_the_system_message() -> None:
    exported = TOOL_DECISION.export(record_for(label=[]))

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
    control = TOOL_DECISION.answer_control(record_for(catalog="one_tool.txt", label=[]))

    assert control.count("<Choice ") == 1
    assert 'value="Lookup00_0a"' in control


def test_a_tab_in_a_tool_name_survives_the_answer_control() -> None:
    """An XML parser folds a literal tab in an attribute to a space; a reference is kept."""
    control = TOOL_DECISION.answer_control(
        record_for(catalog="odd_names.txt", label=[])
    )

    assert "&#9;" in control
    assert "calculate_triangl\te_area" not in control


def test_the_question_leaves_the_marker_dsl_alone() -> None:
    """Single braces are the DSL's; `slot_filling` only fills doubled ones."""
    asked = TOOL_DECISION.question(record_for(label=[]), "{trigger} ở lượt cuối")

    assert "{trigger} ở lượt cuối" in asked
    assert "{{focus}}" not in asked
