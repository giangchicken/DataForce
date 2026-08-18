"""The suite itself: does it catch what it exists to catch?

A conformance suite that passes everything is worse than none, so each check gets
a profile built to break it -- and the well-behaved profile has to keep passing.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import (
    TOOLS,
    FreeTextProfile,
    NaNProfile,
    SetProfile,
    WobblyConsensusProfile,
)

from dataforce.profiles import conformance
from dataforce.profiles.base import Answer
from dataforce.shared.errors import ConformanceError


class RaisingDeltaProfile(SetProfile):
    """The same bug written the way Python actually punishes it."""

    name = "raising"

    def delta(self, a: Answer, b: Answer) -> float:
        left, right = set(a), set(b)
        return 1.0 - len(left & right) / len(left | right)


class AsymmetricProfile(SetProfile):
    name = "asymmetric"

    def delta(self, a: Answer, b: Answer) -> float:
        return float(len(set(a) - set(b)) > 0)


class OutOfRangeProfile(SetProfile):
    name = "out_of_range"

    def delta(self, a: Answer, b: Answer) -> float:
        return 0.0 if set(a) == set(b) else float(len(set(a) ^ set(b)))


class RaisingConsensusProfile(SetProfile):
    name = "raising_consensus"

    def consensus(self, answers: list[Answer]) -> Answer | None:
        raise RuntimeError("panel not configured")


class DisagreeingConsensusProfile(SetProfile):
    name = "disagreeing"

    def consensus(self, answers: list[Answer]) -> Answer | None:
        return sorted(TOOLS)


class DroppingAdapterProfile(SetProfile):
    name = "dropping"

    def adapt(self, raw: Any, parts: Any) -> Any:
        record = super().adapt(raw, parts)
        return record.model_copy(update={"meta": {}})


class LyingExporterProfile(SetProfile):
    name = "lying"

    def export(self, record: Any) -> dict[str, Any]:
        return {"tools": ["Calendar", "SendMail", "Search"]}


def _detail(profile: Any, check: str) -> str:
    report = conformance.run(profile)
    failures = {failure.name: failure.detail for failure in report.failures}
    assert check in failures, f"{check} passed when it should have failed: {report}"
    return failures[check]


def test_a_well_behaved_profile_passes_every_check() -> None:
    report = conformance.run(SetProfile())
    assert report.ok
    assert {check.name for check in report.checks} == {
        "delta_is_a_metric",
        "answers_survive_an_artifact",
        "consensus_is_deterministic_and_agrees_on_unanimity",
    }


def test_a_nan_on_the_empty_answer_is_caught_and_the_answer_named() -> None:
    detail = _detail(NaNProfile(), "delta_is_a_metric")
    assert "NaN" in detail and "[]" in detail


def test_a_delta_that_raises_on_the_empty_answer_is_caught_not_propagated() -> None:
    detail = _detail(RaisingDeltaProfile(), "delta_is_a_metric")
    assert "ZeroDivisionError" in detail


def test_asymmetry_is_caught() -> None:
    assert "not symmetric" in _detail(AsymmetricProfile(), "delta_is_a_metric")


def test_a_distance_outside_the_unit_interval_is_caught() -> None:
    assert "outside [0, 1]" in _detail(OutOfRangeProfile(), "delta_is_a_metric")


def test_a_non_deterministic_consensus_is_caught() -> None:
    detail = _detail(
        WobblyConsensusProfile(), "consensus_is_deterministic_and_agrees_on_unanimity"
    )
    assert "not deterministic" in detail


def test_a_consensus_that_ignores_unanimity_is_caught() -> None:
    detail = _detail(
        DisagreeingConsensusProfile(),
        "consensus_is_deterministic_and_agrees_on_unanimity",
    )
    assert "unanimous" in detail or "identical" in detail


def test_a_consensus_that_raises_is_a_failure_and_not_a_declaration() -> None:
    """Abstaining is a design decision; raising is a defect. They must not merge."""
    report = conformance.run(RaisingConsensusProfile())
    assert not report.ok
    assert not report.barred_from_consensus_tier
    detail = {failure.name: failure.detail for failure in report.failures}
    assert (
        "RuntimeError" in detail["consensus_is_deterministic_and_agrees_on_unanimity"]
    )


def test_no_consensus_skips_the_consensus_checks_and_records_the_bar() -> None:
    report = conformance.run(FreeTextProfile())
    assert report.ok
    assert report.barred_from_consensus_tier
    assert all("consensus" not in check.name for check in report.checks)


def test_answer_pairs_come_from_the_schema_and_include_the_empty_answer() -> None:
    """No per-profile fixture: the schema is the only input the suite needs."""
    answers = conformance.sample_answers(SetProfile.answer_schema)
    assert [] in answers
    assert ["SendMail"] in answers
    assert answers == conformance.sample_answers(SetProfile.answer_schema)


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": "array", "items": {"enum": TOOLS}}, (True, [])),
        ({"type": "array", "items": {"enum": TOOLS}, "minItems": 1}, (False, None)),
        ({"type": "string"}, (True, "")),
        ({"type": "object", "properties": {"a": {"type": "string"}}}, (True, {})),
        ({"enum": ["yes", "no"]}, (False, None)),
    ],
)
def test_the_empty_answer_is_derived_from_the_schema(
    schema: dict[str, Any], expected: tuple[bool, Any]
) -> None:
    assert conformance.empty_answer(schema) == expected


def test_a_schema_the_suite_cannot_generate_from_blocks_registration() -> None:
    class Opaque(SetProfile):
        answer_schema: dict[str, Any] = {"description": "whatever the model says"}

    with pytest.raises(ConformanceError, match="cannot generate answers"):
        conformance.run(Opaque())


def test_all_five_checks_run_where_a_raw_record_exists(parts: Any) -> None:
    raw = {"tools": ["SendMail"], "source_index": 7}
    report = conformance.run_with_sample(SetProfile(), raw, parts)
    assert report.ok
    assert {check.name for check in report.checks} >= {
        "adapter_preserves_unowned_fields",
        "export_reproduces_the_answer",
    }


def test_an_adapter_that_drops_what_it_does_not_own_is_caught(parts: Any) -> None:
    report = conformance.run_with_sample(DroppingAdapterProfile(), {"tools": []}, parts)
    assert not report.ok
    assert "adapter_preserves_unowned_fields" in {f.name for f in report.failures}


def test_an_exporter_that_does_not_reproduce_the_answer_is_caught(parts: Any) -> None:
    raw = {"tools": ["SendMail"]}
    report = conformance.run_with_sample(LyingExporterProfile(), raw, parts)
    assert not report.ok
    assert "export_reproduces_the_answer" in {f.name for f in report.failures}
