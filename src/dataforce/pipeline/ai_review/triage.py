"""STEP · triage · the two numbers become a bucket, a stratum and a review quota.

The last stage of the phase and the only one in the pipeline that is re-run on purpose:
``objective.md`` §8 calls bucket thresholds provisional until the pilot measures them and gives this
stage **exactly one** re-tuning pass afterwards. That is what § *ai_review*'s three stages are for
-- a boundary that moves re-runs this module and never the panel.

**No number is written here** (Requirement 27). Both floors, every stratum and every quota are
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
from typing import NamedTuple

from agent_toolkit.string_utils import compute_hash

from dataforce.engine import Engine, ServiceResult
from dataforce.record import AgreementScores, Record, ReviewSelection

from ..params import declared_ratio, declared_text

# The key this stage owns, under `ai_review`: one key, one writer.
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


class Floors(NamedTuple):
    """The two boundaries, named rather than ordered.

    They are two floats of one type read from two adjacent lines and passed through three calls,
    which is connascence of position at exactly the distance to convert it: a swap type-checks,
    runs, and moves every record one cell sideways. `flow.py`'s `Stage` is the same conversion.
    """

    self_agreement: float  # below it, the jurors do not agree with each other
    label_agreement: (
        float  # below it, they do not agree with the label the record carries
    )


def sampling_position(record_id: str) -> float:
    """Where this record sits in `[0, 1)`: a digest of its id, read as a fraction in base sixteen.

    Not `share_of`, which is what this was called: a *share* is what a quota is, and the call site
    then read as one share compared against another. What comes back is the record's position in
    the interval the quota cuts.

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
    that point rather than twenty thousand records into a run (Requirement 43). Every cell is
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


def bucket_for(scores: AgreementScores, floors: Floors) -> str:
    """The bucket this record's two numbers place it in: a cell's *name*, which is what comes back.

    A cell is the pair of booleans and a bucket is what `CELLS` calls it -- the word `params.yaml`
    declares a quota against, the field `ReviewSelection` carries, and the word the caller binds.
    `cell_of` named the lookup rather than the result and disagreed with its own call site.

    The suffix stays because the rule only refuses one that stands *in place of* the object: a bucket is
    what this returns, so `bucket = bucket_for(scores, floors)` says so twice rather than hiding it.
    `triage_for` would read as well and cannot be had -- `triage` is this module, its stage key, its
    service function and already a constant here, which is the third bullet of the same section.
    """
    return CELLS[
        (
            scores.self_agreement >= floors.self_agreement,
            scores.label_agreement >= floors.label_agreement,
        )
    ]


def scores_to_place(record: Record) -> AgreementScores | None:
    """This stage's precondition, as the value it needs: what `cohesion` wrote, or None.

    A record with no two numbers has no cell, and `question_generate` reads the same absence. It
    returns the scores rather than a `bool` for `votes_to_fold`'s reason: a predicate cannot narrow,
    so the caller would read the key twice and prove twice that it is there.
    """
    return record.ai_review.cohesion


def review_selection(
    record: Record,
    scores: AgreementScores,
    floors: Floors,
    buckets: Mapping[str, tuple[str, float]],
) -> ReviewSelection:
    """One record's cell, its group, and whether the quota on that cell reaches it.

    `reason` names the cell and which side of its quota the record fell, because that is what an
    audit of a quota needs: count the records selected in one bucket, count the records in it, and
    the ratio is the declared share or the declaration is not being applied.
    """
    bucket = bucket_for(scores, floors)
    stratum, quota = buckets[bucket]
    selected = sampling_position(record.record_id) < quota
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

    The precondition is `scores_to_place`, named beside the signature rather than spelled inside
    the fold. The declarations are read before the first record, so a `params.yaml` this
    stage cannot run on stops the run rather than half of it.
    """
    floors = Floors(
        self_agreement=declared_ratio(engine, *SELF_FLOOR),
        label_agreement=declared_ratio(engine, *LABEL_FLOOR),
    )
    buckets = declared_buckets(engine)
    written: list[Record] = []
    for record in records:
        scores = scores_to_place(record)
        if scores is None:
            written.append(record)
            continue
        written.append(
            record.model_copy(
                update={
                    "ai_review": record.ai_review.model_copy(
                        update={
                            STAGE: review_selection(record, scores, floors, buckets)
                        }
                    )
                }
            )
        )
    return ServiceResult(records=tuple(written))
