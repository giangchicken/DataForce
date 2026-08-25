"""T21 · triage: the two numbers become a cell, a group, and a quota that reaches a record or not.

The records reach this stage through the real `label_check`, `jury` and `cohesion`, because *which
cell a record lands in* is a fact about all four -- a hand-written `AgreementScores` would let this
module and `cohesion` agree about a floor by luck. The thresholds are declared per test, and one
test declares them by reading the `params.yaml` this repository ships: `declared_buckets` refuses a
cell the file does not answer for, so that test is what proves the shipped file is complete.

**No numeric literal is in the module under test** (Requirement 27), and the two below are in this
file on purpose: a test that could not name a boundary could not prove one was read.

Every fixture is invented (AGENTS.md §9).
"""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.ai_review.cohesion import cohesion
from dataforce.pipeline.ai_review.jury import jury
from dataforce.pipeline.ai_review.triage import CELLS, share_of, triage
from dataforce.pipeline.data_quality.label_check import label_check
from dataforce.record import Record, ReviewSelection, StoredAnswer

from .test_jury import a_panel_of
from .test_label_check import written_paths
from .test_load_data import an_engine
from .test_tool_decision import LOOKED_UP, SENT, a_record

PARAMS = Path(__file__).resolve().parents[2] / "params.yaml"

# Floors that put a unanimous panel above and a split one below, so a fixture can choose its cell.
FLOORS: dict[str, Any] = {"self_agreement_floor": 0.7, "label_agreement_floor": 0.7}
# Every cell reviewed in full, so a selection test measures the cell and not the sampling.
EVERYTHING: dict[str, Any] = {
    "buckets": {cell: {"stratum": "flagged", "quota": 1.0} for cell in CELLS.values()}
}


def thresholds(**triage_declared: Any) -> dict[str, Any]:
    """`params.yaml` as this stage reads it, with the triage block a test wants."""
    return {"thresholds": {"triage": {**FLOORS, **EVERYTHING, **triage_declared}}}


def an_engine_that(*votes: StoredAnswer | None, **declared: Any) -> Engine:
    """The engine all four stages are handed: the panel's port, and the declarations."""
    return replace(an_engine(thresholds(**declared)), jury_panel=a_panel_of(*votes))


def sorted_through(engine: Engine, *records: Record) -> tuple[Record, ...]:
    """Records through the phase's three stages, which is the only way this key gets written."""
    checked = label_check(engine, records).records
    return triage(
        engine, cohesion(engine, jury(engine, checked).records).records
    ).records


def selection_of(record: Record) -> ReviewSelection:
    """What this stage wrote on the record."""
    written = record.ai_review.triage

    assert written is not None
    return written


def landed(*votes: StoredAnswer | None, **declared: Any) -> ReviewSelection:
    """Where one record with that panel behind it lands, under those declarations."""
    engine = an_engine_that(*votes, **declared)
    return selection_of(sorted_through(engine, a_record())[0])


# --- the stage's own three promises ---


def test_a_record_gains_exactly_one_key() -> None:
    """I8. `ai_review.triage` and nothing else -- not the numbers it read, not the votes."""
    engine = an_engine_that((SENT,))
    checked = label_check(engine, [a_record()]).records
    before = cohesion(engine, jury(engine, checked).records).records[0]
    after = triage(engine, [before]).records[0]

    assert written_paths(before.model_dump(), after.model_dump()) == {
        "ai_review.triage"
    }


def test_every_record_comes_back() -> None:
    """I11, including the one that never reached a panel."""
    engine = an_engine_that((SENT,))
    given = (a_record(), a_record(tools=[]))

    assert len(sorted_through(engine, *given)) == len(given)


def test_there_is_no_side_output() -> None:
    """A bucket is a value on the record; the quota audit is a fold at the edge."""
    engine = an_engine_that((SENT,))
    checked = label_check(engine, [a_record()]).records
    measured = cohesion(engine, jury(engine, checked).records).records

    assert triage(engine, measured).side_output == {}


# --- the four cells of two floors ---


def test_a_panel_that_agrees_with_itself_and_the_label_is_confirmed() -> None:
    """Both floors met. This is the cell the audit sample is drawn from, not a review cell."""
    assert landed((SENT,), (SENT,)).bucket == "confirmed"


def test_a_panel_that_agrees_against_the_label_is_disputed() -> None:
    """The jurors agree with each other and the label is the outlier: the sharpest review case."""
    assert landed((LOOKED_UP,), (LOOKED_UP,)).bucket == "disputed"


def test_a_split_panel_leaning_toward_the_label_is_divided() -> None:
    """Two of three voted the label, so the label floor is met and the self floor is not."""
    assert landed((SENT,), (SENT,), (LOOKED_UP,), label_agreement_floor=0.6).bucket == (
        "divided"
    )


def test_a_panel_with_no_usable_votes_is_contested() -> None:
    """`cohesion` scores absent evidence as `0.0`, so a panel that answered nothing lands in the
    cell whose quota is declared for records a person should see -- deliberately, not by
    accident."""
    assert landed().bucket == "contested"


def test_a_boundary_is_read_and_not_held() -> None:
    """Requirement 27: the same record lands in two different cells under two `params.yaml`, and
    nothing in the module changed."""
    split = ((SENT,), (SENT,), (LOOKED_UP,))
    lenient = {"label_agreement_floor": 0.6}

    assert landed(*split, self_agreement_floor=0.3, **lenient).bucket == "confirmed"
    assert landed(*split, self_agreement_floor=0.9, **lenient).bucket == "divided"


def test_the_stratum_is_the_one_declared_for_that_cell() -> None:
    """The sampling group is config's, because it is what a release's error bar is grouped by."""
    declared = {
        "buckets": {
            **EVERYTHING["buckets"],
            "confirmed": {"stratum": "audit", "quota": 1.0},
        }
    }

    assert landed((SENT,), (SENT,), **declared).stratum == "audit"


# --- the quota, and what it means to be inside one ---


def test_a_full_quota_reaches_every_record() -> None:
    """A share of 1.0 selects everything, because a share is in `[0, 1)`."""
    assert landed((LOOKED_UP,), (LOOKED_UP,)).selected_for_review


def test_a_bucket_with_no_quota_selects_nothing_and_says_so() -> None:
    """`objective.md` §8: a bucket whose precision the pilot cannot establish gets no quota. It
    is a `0` in a config file, and the reason distinguishes it from a record the sampling missed."""
    retired = {
        "buckets": {
            **EVERYTHING["buckets"],
            "disputed": {"stratum": "none", "quota": 0},
        }
    }
    written = landed((LOOKED_UP,), (LOOKED_UP,), **retired)

    assert not written.selected_for_review
    assert "no quota" in written.reason


def test_the_reason_names_the_cell_and_which_side_of_its_quota() -> None:
    """Requirement 26's audit: count the selected in one bucket against the records in it."""
    inside = landed((LOOKED_UP,), (LOOKED_UP,))
    outside = landed(
        (LOOKED_UP,),
        (LOOKED_UP,),
        buckets={**EVERYTHING["buckets"], "disputed": {"stratum": "f", "quota": 0.0}},
    )

    assert inside.reason == "disputed: within the declared quota"
    assert "disputed" in outside.reason


def test_the_sample_is_stable_across_runs() -> None:
    """Requirement 23: a re-tuning pass must not churn the audit sample, so selection is a
    function of the record's id and of nothing about the batch it arrived in."""
    record = a_record()

    assert share_of(record.record_id) == share_of(record.record_id)


def test_the_sample_is_a_share_and_not_a_count() -> None:
    """A count per bucket would make selection depend on which records were in the batch. One
    record's share does not move when a second record joins it."""
    engine = an_engine_that((SENT,), (SENT,))
    alone = selection_of(sorted_through(engine, a_record())[0])
    crowded = selection_of(
        sorted_through(engine, a_record(), a_record(label=(LOOKED_UP,)))[0]
    )

    assert alone.model_dump() == crowded.model_dump()


def test_a_share_is_inside_the_unit_interval() -> None:
    """`[0, 1)`: a share of exactly 1.0 would make `quota: 1.0` miss a record."""
    shares = [share_of(f"record-{seat}") for seat in range(20)]

    assert all(0.0 <= share < 1.0 for share in shares)
    assert len(set(shares)) == len(shares)


# --- the precondition, and the declarations read before it ---


def test_a_record_with_no_two_numbers_is_skipped() -> None:
    """§ *Per-service contracts*: `ai_review.cohesion` is absent, so there is no cell for it."""
    engine = an_engine_that((SENT,))
    before = a_record(tools=[])
    after = sorted_through(engine, before)[0]

    assert after.ai_review.triage is None
    assert after.ai_review.cohesion is None


@pytest.mark.parametrize(
    "declared",
    [
        {"self_agreement_floor": None},
        {"label_agreement_floor": "high"},
        {"buckets": {}},
        {"buckets": {cell: {"stratum": "f"} for cell in CELLS.values()}},
        {"buckets": {cell: {"quota": 1.0} for cell in CELLS.values()}},
        {"buckets": {cell: {"stratum": "", "quota": 1.0} for cell in CELLS.values()}},
    ],
    ids=[
        "no-floor",
        "floor-is-a-word",
        "no-cells",
        "cell-with-no-quota",
        "cell-with-no-stratum",
        "cell-with-a-blank-stratum",
    ],
)
def test_a_declaration_this_stage_cannot_run_on_stops_the_run(
    declared: Mapping[str, Any],
) -> None:
    """P23: configuration scope, so it is raised before the first record rather than during."""
    engine = an_engine_that((SENT,), **declared)

    with pytest.raises(ConfigError, match="params.yaml"):
        triage(engine, [])


def test_the_params_file_this_repository_ships_answers_for_every_cell() -> None:
    """`declared_buckets` refuses a cell the file does not answer for, so running against the
    real file is what proves it complete -- a fixture would only prove the fixture."""
    shipped = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    engine = replace(an_engine(shipped), jury_panel=a_panel_of((SENT,), (SENT,)))
    written = selection_of(sorted_through(engine, a_record())[0])

    assert written.bucket in set(CELLS.values())
    assert written.stratum
