"""STEP · annotator_answers · responses read back out of the store onto the record.

The other half of the exchange ``publish`` opened, and a separate stage because **a person answers
in between** (Decision 22). They cannot run in one call -- ``POST /human-review`` stops after
``publish`` for exactly this reason -- they re-run for different reasons, and they read different
things: ``publish`` reads the questions and the two config halves, this reads the store.

**It names no verdict and no control.** What a `result` list means is the capture half's, and the
inverse of that half is one profile member (Requirement 49); this stage asks it what the annotation
said and copies the answer onto the record. A stage that reached into `result` for `verdict` would
be a second reader of an annotation tool's shape, in the layer that is supposed to know least about
one -- and adding a fourth verdict would then be an edit in two packages instead of one.

**A skip is not an answer** (Requirement 50). ``was_skipped`` is Label Studio's ``was_cancelled``:
the annotator saw the question and declined it, which is evidence about the *question* and not about
the label. It is excluded here rather than filtered later, which is what keeps it out of
``aggregate``'s overlap structurally -- and the skip itself is not lost, because the store counts it
and the pilot reads the rate from there.

**Looked-at-and-empty is not the same as not-looked-at.** A record whose every answer was a skip
gets the key with no responses in it; a record the store holds no answers for gets no key at all.
Both end with no verdict from ``aggregate``, and only the first says *someone was asked and declined*.

**One query for the batch.** The ids of every record's published questions go across the port
together and the answers come back grouped, because a call per record is twenty thousand round trips
to a database for a phase that has one question about each.
"""

from collections.abc import Iterable, Mapping, Sequence

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.ports import QuestionStore, StoredAnnotation
from dataforce.record import AnnotatorResponse, Record, ReturnedAnswers

# The key this stage owns, under `human_review` (P16: one key, one writer).
STAGE = "annotator_answers"


def published_question_ids(record: Record) -> tuple[str, ...]:
    """This stage's precondition, as the value it needs: what `publish` said the store holds.

    The receipt and not `question_generate`, because a question that was never published cannot
    have been answered -- and the receipt is the store's own word for which ids it has, which is
    the only thing this stage can join on. A record `publish` skipped comes back with none from
    here too, so a reader downstream sees one absence rather than two.
    """
    receipt = record.human_review.publish
    return receipt.stored if receipt else ()


def answers_by_question(
    store: QuestionStore, question_ids: Sequence[str]
) -> Mapping[str, list[StoredAnnotation]]:
    """Every answer the store holds to any of those questions, grouped by the one it answers."""
    grouped: dict[str, list[StoredAnnotation]] = {}
    for annotation in store.answers_to(question_ids):
        grouped.setdefault(annotation.question_id, []).append(annotation)
    return grouped


def response_from(
    engine: Engine, record: Record, annotation: StoredAnnotation
) -> AnnotatorResponse | None:
    """One store row as an answer on the record, or None where it is not an answer at all.

    Two ways it is not one. A **skip** is Requirement 50's: the person declined, and a record of
    what they declined belongs to the question rather than to the label. An annotation with **no
    verdict** is the other, and it should not exist -- the capture half marks that control
    `required="true"`, so the tool refuses a submission without it -- which is why it is dropped
    rather than given a place on the record: `AnnotatorResponse.verdict` is required, and inventing
    a value for a control nobody answered is the coercion Requirement 49 forbids one line away.
    """
    if annotation.was_skipped:
        return None
    said = engine.profile.annotation_response(annotation.result, record)
    if said.verdict is None:
        return None
    return AnnotatorResponse(
        annotator_id=annotation.annotator_id,
        question_id=annotation.question_id,
        verdict=said.verdict,
        corrected_value=said.corrected_value,
        note=said.note,
        submitted_at=annotation.submitted_at,
    )


def responses_on(
    engine: Engine, record: Record, held: Mapping[str, list[StoredAnnotation]]
) -> tuple[AnnotatorResponse, ...]:
    """Every answer this record's questions got, in the order the store handed them over.

    In no promised order, which is the port's own word for it: `aggregate` folds them and a fold
    has no first element. The record is passed down because a correction is validated against
    *this* record's answer space, which is the whole of why the profile takes one.
    """
    return tuple(
        response
        for question_id in published_question_ids(record)
        for annotation in held.get(question_id, ())
        for response in [response_from(engine, record, annotation)]
        if response is not None
    )


def annotator_answers(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record the store holds answers for, one key richer: what people said about it.

    A missing store is a `ConfigError` before the first record, on `publish`'s line: reading no
    answers because there is nowhere to read from would write *nobody has answered yet* onto a
    corpus nobody has asked about (P23).
    """
    store = engine.question_store
    if store is None:
        raise ConfigError(
            "human_review needs a question store and this engine was opened without one; "
            "the edge supplies it at composition"
        )
    running = tuple(records)
    asked = [
        question_id
        for record in running
        for question_id in published_question_ids(record)
    ]
    if not asked:
        return ServiceResult(records=running)
    held = answers_by_question(store, asked)
    return ServiceResult(
        records=tuple(
            record.model_copy(
                update={
                    "human_review": record.human_review.model_copy(
                        update={
                            STAGE: ReturnedAnswers(
                                responses=responses_on(engine, record, held)
                            )
                        }
                    )
                }
            )
            if any(
                question_id in held for question_id in published_question_ids(record)
            )
            else record
            for record in running
        )
    )
