"""STEP · curate · the verdict becomes the record's final label, or an adjudication.

The last stage of the phase, and the only one that touches what ships. Everything before it
measures; this one decides, and what it decides is one of three things: the label the record arrived
with was right, the people who looked at it agreed on a different one, or nobody can say
(Requirement 35).

**It names no verdict value** (§ *Per-service contracts*). Which verdict says *the label as it
stands is right* is the capture half's to declare and ``answer_config().endorsing_verdict`` is where
it does, so adding a
fourth verdict stays one directory's edit. What this module does name is the three **statuses**,
because those are the record's own vocabulary -- ``FinalLabel.status`` is a ``Literal`` of exactly
them, and `tool_decision`'s ``final_label`` already reads one.

**A correction is folded by the profile, through the same member the panel's votes go through.**
``vote_consensus`` is *given several answers to one record, which one is defensible* -- a question
that does not care whether the answers came from models or from people -- and one owner for it is
what keeps ``jury`` and this stage from drifting into two ideas of what agreement means. It needs a
strict majority per tool name, so at an overlap of two both annotators must have named it.

**``()`` and ``None`` are not the same consensus.** The empty answer is a real corrected label --
*this record should call nothing* -- and ``vote_consensus`` returns ``None`` for *nothing here is
defensible*. Testing the value for truth would file every *call nothing* correction as unresolved,
which is a wrong label rather than a missing one.

**Unresolved keeps the original label and says so.** A verdict that the label is wrong, with no
correction anyone can act on, is not a reason to ship an empty answer -- it is a reason for the
record to carry `status: "unresolved"`, which is the flag ``final_label`` reads and export's
precondition will. Requirement 49's malformed correction and a verdict of *unsure* both land here.

**``decided_at`` is the last annotator's clock, not this stage's.** No engine module holds one (I1),
and inventing an ingest-time timestamp would put a value in the record that two runs disagree about
(I15). When it was decided *is* when the last person who decided it pressed submit.

**This is the one stage that imports another.** ``one_answer_each`` is ``aggregate``'s, because
what an overlap *is* belongs to the stage that writes ``overlap`` -- and a majority here has to be
of the same people that verdict was folded from, or the two keys describe different rooms. The
dependency is not new: this stage already reads ``human_review.aggregate``, and § *Per-service
contracts* says so. The import makes it visible instead of implied.

**``adjudicated_by`` is always ``None``, and that is a gap rather than a design.** Requirement 35
says curate records who adjudicated where the validators disagreed; nothing in this system performs
an adjudication, which would be a second trip through the store with a named arbiter. Until one
exists a disagreement is ``unresolved`` and goes back to a person, and the field stays empty rather
than being filled with the first annotator's name.
"""

from collections.abc import Iterable, Sequence
from typing import Literal

from dataforce.engine import Engine, ServiceResult
from dataforce.record import (
    AnnotatorResponse,
    FinalLabel,
    OverlapVerdict,
    Record,
    StoredAnswer,
)

from .aggregate import one_answer_each

# The key this stage owns, under `human_review`: one key, one writer.
STAGE = "curate"

# The record's own three words for what happened to a label. `FinalLabel.status` is a `Literal` of
# exactly these, so naming them here is naming the record's vocabulary and not the profile's.
type Status = Literal["original", "corrected", "unresolved"]

ORIGINAL: Status = "original"
CORRECTED: Status = "corrected"
UNRESOLVED: Status = "unresolved"


def verdict_to_curate(record: Record) -> OverlapVerdict | None:
    """This stage's precondition, as the value it needs: what `aggregate` folded, or None."""
    return record.human_review.aggregate


def responses_behind(record: Record) -> tuple[AnnotatorResponse, ...]:
    """The answers that verdict was folded from: who decided, when, and what they proposed.

    `aggregate` writes a verdict, a confidence and three counts, and none of those is a person or a
    correction -- so this stage reads the answers themselves rather than adding four fields to a
    summary. Its § *Per-service contracts* cell says so.

    Folded to one answer per person by `aggregate.one_answer_each`, for the reason that function
    carries and for one of this stage's own: `vote_consensus` needs a *strict majority per tool
    name*, so one person answering twice would otherwise outvote two people who each answered once.
    `validators` was already de-duplicated and the corrections were not, which is one stage holding
    two ideas of what an annotator is.

    A verdict with no answers under it cannot happen through the flow, because `aggregate` writes
    one only where the overlap floor was met. It can happen through `POST /human-review/curate` with
    a hand-made body, and the fold treats it as nothing to curate rather than as a crash: the
    validators and the clock both come from here, and there is no honest value for either.
    """
    returned = record.human_review.annotator_answers
    return one_answer_each(returned.responses) if returned else ()


def corrections_in(responses: Sequence[AnnotatorResponse]) -> tuple[StoredAnswer, ...]:
    """Every corrected answer the responses carry, in the order they were read back.

    A response with no correction contributes nothing rather than the empty answer: *I did not
    propose one* and *I propose calling nothing* are two different things, and `vote_consensus`
    counts the second toward a majority for the empty answer.
    """
    return tuple(
        response.corrected_value
        for response in responses
        if response.corrected_value is not None
    )


def curated_label(
    engine: Engine,
    record: Record,
    verdict: OverlapVerdict,
    responses: Sequence[AnnotatorResponse],
) -> FinalLabel:
    """One record's final label: what ships, why it is that, and who decided.

    `validators` is every annotator who answered, in the order they came back. It needs no
    de-duplication of its own: `responses_behind` hands one answer per person, which is the same
    list the verdict, the confidence and α were folded from.
    """
    status: Status
    if verdict.verdict == engine.profile.answer_config(record).endorsing_verdict:
        status, label = ORIGINAL, record.label
    else:
        agreed = engine.profile.vote_consensus(corrections_in(responses), record)
        # `is not None` and not truth: `()` is *call nothing*, which is a corrected label.
        status, label = (
            (CORRECTED, agreed) if agreed is not None else (UNRESOLVED, record.label)
        )
    return FinalLabel(
        status=status,
        label=label,
        validators=tuple(response.annotator_id for response in responses),
        adjudicated_by=None,
        decided_at=max(response.submitted_at for response in responses),
    )


def curate(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record with a verdict, one key richer: the label that ships and how it was decided.

    Two conditions, each named beside the signature: the verdict, which is the contract's
    own cell, and the answers it was folded from, which is where the validators and the clock come
    from. A record missing either is passed on untouched.
    """
    written: list[Record] = []
    for record in records:
        verdict = verdict_to_curate(record)
        answered = responses_behind(record)
        if verdict is None or not answered:
            written.append(record)
            continue
        written.append(
            record.model_copy(
                update={
                    "human_review": record.human_review.model_copy(
                        update={STAGE: curated_label(engine, record, verdict, answered)}
                    )
                }
            )
        )
    return ServiceResult(records=tuple(written))
