"""T15 · label_check: what the five checks write, and what they refuse to do about it.

The row is § *Per-service contracts*' second: reads `content`, `label` and `meta`, writes
`data_quality.label_check`, skips nothing. The five checks themselves are T13's and are asserted
there against the defects they find; what is asserted here is the stage's own three promises --
one key, every record, and nothing stopped.

**The last one is the point of the whole design.** No stage in the flow is a gate, so a
declared count that has moved is a line in a `metrics.json` diff and not a crash (Requirement 22):
a corpus where every record fails every check still comes out the other end carrying why.
`written_paths` below is how "exactly one key" (I8) is asserted, and the two stage tests after this
one and the property test in `tests/properties/` read it from here.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from dataforce.pipeline.data_quality.label_check import label_check
from dataforce.record import Record

from .test_load_data import an_engine
from .test_tool_decision import LOOKED_UP, SENT, TICKETED, a_record

FIVE = (
    "label_assistant_mismatch",
    "label_not_in_catalog",
    "empty_catalog",
    "label_cardinality_anomaly",
    "label_names_one_tool_twice",
)


def written_paths(before: Any, after: Any, at: str = "") -> set[str]:
    """Every dotted path where two record dumps differ -- `data_quality.label_check`.

    Descends only where both sides are mappings, so a key that was absent and is now written
    reports as itself rather than as every field inside it. That is the granularity I8 is about:
    *one key*, and the reason a stage that also touched `content` could not hide it.
    """
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        return {
            path
            for key in before.keys() | after.keys()
            for path in written_paths(
                before.get(key), after.get(key), f"{at}.{key}" if at else key
            )
        }
    return set() if before == after else {at}


def checked(*records: Record, **thresholds: Any) -> tuple[Record, ...]:
    """The records this stage hands back, run through the real profile's five checks."""
    return label_check(an_engine(thresholds), records).records


def failed(record: Record) -> Iterable[str]:
    """Which named checks this record's verdict says did not hold."""
    verdict = record.data_quality.label_check
    assert verdict is not None
    return verdict.failed_checks


# --- the stage's own three promises ---


def test_a_record_gains_exactly_one_key() -> None:
    """I8: one writer per record key, and this is the one it writes."""
    record = a_record()

    assert written_paths(record.model_dump(), checked(record)[0].model_dump()) == {
        "data_quality.label_check"
    }


def test_every_record_comes_back() -> None:
    """I11 and Requirement 41: a record that fails every check is marked, never removed."""
    records = (a_record(), a_record(tools=[]), a_record(label=(SENT, SENT)))

    assert len(checked(*records)) == len(records)


def test_a_declared_count_that_has_moved_stops_nothing() -> None:
    """Requirement 22, stated as a test: this is the cost of having no gates, and it is deliberate.

    `params.invalid_counts.empty_catalog` says none, the record has one, and the run completes with
    the defect on the record. The comparison is `metrics.json`'s -- a number a human reads in a
    diff (Requirement 44).
    """
    declared = {"invalid_counts": {"empty_catalog": 0}}

    verdicts = checked(a_record(tools=[]), **declared)

    assert "empty_catalog" in failed(verdicts[0])


# --- what the verdict says ---


def test_a_clean_record_passes_and_is_not_quarantined() -> None:
    """The declared shape's ordinary case: nothing restates the label, and every check reads 0."""
    verdict = checked(a_record())[0].data_quality.label_check

    assert verdict is not None
    assert verdict.passed
    assert verdict.failed_checks == ()
    assert not verdict.quarantined


def test_a_failing_record_names_the_defects_and_is_quarantined() -> None:
    """`failed_checks` is what triage reads; `quarantined` is what the next stages read."""
    verdict = checked(a_record(tools=[]))[0].data_quality.label_check

    assert verdict is not None
    assert not verdict.passed
    assert verdict.quarantined
    assert set(verdict.failed_checks) == {"label_not_in_catalog", "empty_catalog"}


def test_the_defects_are_named_in_the_order_the_profile_declares_them() -> None:
    """Two runs over one record write the same list, which a set would not have guaranteed."""
    named = failed(checked(a_record(tools=[]))[0])

    assert list(named) == [name for name in FIVE if name in set(named)]


def test_a_label_naming_more_tools_than_the_ceiling_is_the_only_defect_found() -> None:
    """Three calls against `max_calls: 2`, all three in the catalog: one defect and no others."""
    crowded = a_record(label=(SENT, LOOKED_UP, TICKETED))

    assert list(failed(checked(crowded)[0])) == ["label_cardinality_anomaly"]


def test_nothing_else_on_the_record_moves() -> None:
    """The record is frozen and the stage returns a copy: content, label and `meta` are untouched."""
    record = a_record()

    written = checked(record)[0]

    assert written.content == record.content
    assert written.content_version == record.content_version
    assert written.label == record.label
    assert written.meta == record.meta
