"""STEP · triage · the two numbers become a bucket, a stratum and a review quota.

The last stage of the phase and the only one in the pipeline that is re-run on purpose:
``objective.md`` §8 calls bucket thresholds provisional until the pilot measures them and gives
this stage **exactly one** re-tuning pass afterwards. That is what Decision 3 bought -- a boundary
that moves re-runs this module and never the panel.

**No number is written here** (Requirement 27, P25). Both floors, every stratum and every quota are
lines in ``params.yaml``, so moving a boundary is a committed, attributable edit whose digest the
run manifest records. What *is* here is the cell structure, because four cells of two floors is
logic and not a threshold:

===========  ================  =======================================================
self ≥ floor  label ≥ floor    the cell
===========  ================  =======================================================
yes           yes              ``confirmed``  -- the panel and the label say the same thing
yes           no               ``disputed``   -- the panel agrees, and the label is the outlier
no            yes              ``divided``    -- the jurors split, and lean toward the label
no            no               ``contested``  -- no agreement anywhere, including no panel at all
===========  ================  =======================================================

``contested`` is where a record with no usable votes lands, because ``cohesion`` scores absent
evidence as ``0.0``: a panel that failed, a panel of one, a panel that answered nothing valid. That
is deliberate -- those are records a person should see, and they arrive in the cell whose quota is
declared for records a person should see.

**A quota is a share, and the record's own id is what applies it.** Every alternative is worse: a
*count* per bucket makes selection depend on which records happened to be in the batch, so two runs
over one corpus select different records and neither is reproducible (Requirement 23); a random
draw is worse again. A digest of the ``record_id`` read as a fraction is stable, uniform, needs no
batch-wide state, and re-runs identically after a re-tuning pass -- so the audit sample does not
churn every time a boundary moves.

**A bucket with no quota selects nothing**, which is ``objective.md`` §8's rule for a bucket whose
precision the pilot cannot establish. It is a `0` in a config file rather than a branch here.
"""

from collections.abc import Iterable, Mapping

from agent_toolkit.string_utils import compute_hash

from dataforce.engine import Engine, ServiceResult
from dataforce.record import AgreementScores, Record, ReviewSelection

from ..params import declared_ratio, declared_text

# The key this stage owns, under `ai_review` (P16: one key, one writer).
STAGE = "triage"

# Where `params.yaml` declares the two floors and the row for each cell they make.
TRIAGE = ("thresholds", "triage")
SELF_FLOOR = (*TRIAGE, "self_agreement_floor")
LABEL_FLOOR = (*TRIAGE, "label_agreement_floor")
BUCKETS_AT = (*TRIAGE, "buckets")
STRATUM = "stratum"
QUOTA = "quota"

# The cells, by which floors the record's two numbers met. Named for what the cell *says*, since a
# bucket name is read by whoever audits a quota and a coordinate pair is not a sentence.
CELLS: Mapping[tuple[bool, bool], str] = {
    (True, True): "confirmed",
    (True, False): "disputed",
    (False, True): "divided",
    (False, False): "contested",
}

# The digits a digest is written in, named so the base below is not a tuned literal in disguise.
HEX = "0123456789abcdef"


def share_of(record_id: str) -> float:
    """Where this record sits in `[0, 1)`: a digest of its id, read as a fraction in base sixteen.

    Hashed rather than read straight off the id, for one reason: `record_id` is 16 lowercase hex by
    construction (Requirement 6) and `Record.record_id` is a string, so reading it as base sixteen
    would turn a malformed record into a `ValueError` from arithmetic. The digest is hex whatever it
    was handed, and two identical records still sample identically because the id already covers
    the content.
    """
    digest = compute_hash(record_id)
    # Annotated because `int ** int` is `Any` to mypy -- `**` may return a float, and this one
    # cannot: both operands are lengths.
    span: int = len(HEX) ** len(digest)
    return int(digest, len(HEX)) / span


def declared_buckets(engine: Engine) -> Mapping[str, tuple[str, float]]:
    """Every cell, with the stratum and the quota `params.yaml` gives it.

    Read once, before the first record: a cell the file does not answer for is a `ConfigError` at
    that point rather than twenty thousand records into a run (Requirement 43, P23). Every cell is
    read even where the corpus produces none of one, because *the file is incomplete* is worth
    knowing on the run that would otherwise have hidden it.
    """
    return {
        bucket: (
            declared_text(engine, *BUCKETS_AT, bucket, STRATUM),
            declared_ratio(engine, *BUCKETS_AT, bucket, QUOTA),
        )
        for bucket in sorted(set(CELLS.values()))
    }


def cell_of(scores: AgreementScores, self_floor: float, label_floor: float) -> str:
    """Which of the four cells this record's two numbers fall in."""
    return CELLS[
        (
            scores.self_agreement >= self_floor,
            scores.label_agreement >= label_floor,
        )
    ]


def selection_of(
    record: Record,
    scores: AgreementScores,
    floors: tuple[float, float],
    buckets: Mapping[str, tuple[str, float]],
) -> ReviewSelection:
    """One record's cell, its group, and whether the quota on that cell reaches it.

    `reason` names the cell and which side of its quota the record fell, because that is what an
    audit of a quota needs: count the records selected in one bucket, count the records in it, and
    the ratio is the declared share or the declaration is not being applied.
    """
    bucket = cell_of(scores, *floors)
    stratum, quota = buckets[bucket]
    selected = share_of(record.record_id) < quota
    if selected:
        reason = f"{bucket}: within the declared quota"
    elif not quota:
        reason = f"{bucket}: no quota is declared for this bucket"
    else:
        reason = f"{bucket}: outside the declared quota"
    return ReviewSelection(
        bucket=bucket,
        stratum=stratum,
        selected_for_review=selected,
        reason=reason,
    )


def triage(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every measured record, one key richer: where it landed, and whether a person sees it.

    The precondition is `ai_review.cohesion` (P12): a record with no two numbers has no cell, and
    `question_generate` reads the same absence. The declarations are read before the first record,
    so a `params.yaml` this stage cannot run on stops the run rather than half of it.
    """
    floors = (
        declared_ratio(engine, *SELF_FLOOR),
        declared_ratio(engine, *LABEL_FLOOR),
    )
    buckets = declared_buckets(engine)
    return ServiceResult(
        records=tuple(
            record.model_copy(
                update={
                    "ai_review": record.ai_review.model_copy(
                        update={
                            STAGE: selection_of(
                                record, record.ai_review.cohesion, floors, buckets
                            )
                        }
                    )
                }
            )
            if record.ai_review.cohesion is not None
            else record
            for record in records
        )
    )
