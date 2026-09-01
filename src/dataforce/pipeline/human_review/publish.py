"""STEP · publish · questions written to the question store, ready for the annotation tool.

**No Label Studio anywhere.** ``publish`` writes to a database we own and a separate sync moves the
questions out (§ *The question store*), so the pipeline stays runnable and testable with no
instance and ``annotator_answers`` reads one shape whatever the annotation tool turns out to be.
Not one word of that tool's dialect is written here either: the payload this stage composes is keys
and values, and
every tag that reads them is ``edge/label_studio.py``'s.

**This module writes no annotation-tool markup at all** (Requirement 31). What it assembles is the
question *payload* -- the ``data`` dict a task carries -- out of the profile's capture half and the
two ids that join a task back to a record. The config an annotator's page is built from is the tool's
own grammar and is composed in ``edge/label_studio.py``, along with the fragment that renders the
content and the array it reads: a stage that knew what a fragment contained would be a second place
to change when the tool changed, and a stage that composed one could not be run without the tool
being the one on the other end.

**The payload carries no model output** (Requirement 30, I12). It is built from the capture half and
the question, and nothing in this module can reach `ai_review` -- the record's votes, its two
agreement figures and its bucket have no path into a `data` dict assembled out of three values none
of which is read from that key.

**Publishing twice is a no-op and that is the store's promise, not this stage's.** A `question_id`
is a pure function of its question, so the second write finds the rows already there; what comes
back names them anyway, because what the record records is *what the store holds*, not what this
call happened to insert. The receipt's two stamps are the store's for I1's reason -- a clock and an
identity for a write are I/O, and no engine module has either.

**A phase that selected nothing does not touch the database.** An empty batch would still open a
transaction, mint an id over nothing and stamp a clock nobody reads, so the stage returns before it:
*no questions* is an ordinary state of a corpus, not a degenerate write.
"""

from collections.abc import Iterable, Sequence

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.ports import QuestionToStore, StoreReceipt
from dataforce.record import PublishedQuestions, Question, Record

# The key this stage owns, under `human_review`: one key, one writer.
STAGE = "publish"

# The two payload keys neither axis owns, because neither axis knows a question. `question_id` rides
# inside `data` because Label Studio assigns its own task ids, and an annotation has to be joined
# back to the question that produced it across a project rebuild.
QUESTION_ID = "question_id"
QUESTION = "question"


def questions_to_publish(record: Record) -> Sequence[Question]:
    """This stage's precondition, as the value it needs: the questions asked about this record.

    Absent and empty are one fact here -- *there is nothing to publish* -- unlike `cohesion`, where
    a key with no votes and no key at all are two different things a bucket has to tell apart. A
    record `question_generate` skipped and a record it asked nothing about are both records no
    person is waiting on.
    """
    return record.human_review.question_generate or ()


def rows_for(engine: Engine, record: Record) -> tuple[QuestionToStore, ...]:
    """One record's questions in the shape the store takes.

    The capture half is read once per record rather than once per question: what it offers is a fact
    about the record's catalog, and every question about one record is asked on one page.

    The pair and the run come off the record's own `provenance`, already stamped `name@version`.
    A store outlives a run, so a row that did not carry them could not be read back safely.
    """
    capture = engine.profile.answer_config(record)
    return tuple(
        QuestionToStore(
            question_id=question.question_id,
            record_id=record.record_id,
            run_id=record.provenance.run_id,
            modality=record.provenance.modality,
            profile=record.provenance.profile,
            # The `data` dict the config's `$names` read, as far as this side owns them: the
            # capture half's keys and the question's two. The display fragment's own key is the
            # adapter's and joins them where the task is created, because that is where the tag
            # that reads it is written (Requirement 31).
            payload={
                QUESTION_ID: question.question_id,
                QUESTION: question.content,
                **capture.data,
            },
        )
        for question in questions_to_publish(record)
    )


def receipt_on(record: Record, receipt: StoreReceipt) -> PublishedQuestions:
    """What one record records about the write: its own questions, as the store confirmed them.

    Intersected with the receipt rather than copied from the record, because the field says which
    questions the *store* holds. The port promises to name every id in the batch, so the two agree
    today; what the intersection costs is nothing, and what it buys is that a store which quietly
    held fewer shows up as a shorter list instead of as a record that is confidently wrong.
    """
    held = set(receipt.stored)
    return PublishedQuestions(
        stored=tuple(
            question.question_id
            for question in questions_to_publish(record)
            if question.question_id in held
        ),
        store_run_id=receipt.store_run_id,
        published_at=receipt.published_at,
    )


def publish(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record with a question, one key richer: which questions the store now holds.

    One store call for the whole batch, because *which write* is what `store_run_id` names and a
    call per record would make twenty thousand writes out of one publish. Every record that
    contributed a question then carries the same two stamps, which is what makes a re-run's records
    comparable to the first run's.

    A missing store is a `ConfigError` before the first record, on `jury`'s line: it is a fact about
    the configuration and not about any record, and a key claiming a question was published would be
    a lie about a write nobody made.
    """
    store = engine.question_store
    if store is None:
        raise ConfigError(
            "publish needs a question store and this engine was opened without one; the "
            "edge supplies it at composition. A `stored` key naming a write nobody made "
            "would be a lie about this record"
        )
    running = tuple(records)
    outgoing = [row for record in running for row in rows_for(engine, record)]
    if not outgoing:
        return ServiceResult(records=running)
    receipt = store.stored_questions(outgoing)
    return ServiceResult(
        records=tuple(
            record.model_copy(
                update={
                    "human_review": record.human_review.model_copy(
                        update={STAGE: receipt_on(record, receipt)}
                    )
                }
            )
            if questions_to_publish(record)
            else record
            for record in running
        )
    )
