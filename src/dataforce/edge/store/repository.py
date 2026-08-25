"""LOGIC · the QuestionStore adapter, over a SQLAlchemy session.

The port is ``dataforce/ports.py``. This is an adapter of it, and calling it a port is the path by
which someone adds a method *here* and the engine then has to import ``edge/store/`` to name a type
-- the inversion Decision 12 moved ``ports.py`` inward to prevent (T37).

**One adapter, two DSNs.** There is no ``PostgresQuestionStore`` beside a SQLite one, because SQLite
and Postgres are one adapter addressed two ways (Decision 7) and nothing below is dialect-specific:
no ``ON CONFLICT``, no ``RETURNING``, no server-side default. What the two disagree about is the
behaviour this module leans on, which is why the tests run twice rather than why the code forks.

**Writing a question the store already holds is a no-op, not an error** (P22). The id is a pure
function of the question, so a second publish of an unchanged corpus is the same rows and re-running
a phase is not something a caller has to be careful about. Insert-if-absent rather than an upsert,
and the difference is deliberate: an existing row records what was *published*, and overwriting its
payload would rewrite the question a person may already have answered.

**``store_run_id`` is a digest of what was written, not a fresh id per call.** A random one would
make two publishes of one batch two different keys on the record, and the field exists to say the
opposite -- *these questions, this write*. Deterministic, so a re-run's record is byte-identical
except for ``published_at``, which is a clock and is the one value this adapter puts on a record
that two runs cannot agree on. I15 meets that at T29, where both shells publish.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from agent_toolkit.string_utils import compute_hash
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dataforce.ports import (
    QuestionToStore,
    StoredAnnotation,
    StoreReceipt,
)

from .models import AnnotatorAnswer, Question

# How a `store_run_id` is written, on `question_id`'s pattern: a prefix a person can read in a
# record and sixteen hex of digest.
RUN_PREFIX = "sr_"
RUN_LENGTH = 16

# What the written ids are joined with before they are hashed, as `scenario_hash` joins tool names.
ID_SEPARATOR = "|"


def store_run_id_for(question_ids: Sequence[str]) -> str:
    """The id of the write that put exactly those questions in the store.

    Sorted first, so the order a batch happened to arrive in is not part of which write it was:
    two runs over one corpus publish the same questions and record the same id.
    """
    joined = ID_SEPARATOR.join(sorted(question_ids))
    return RUN_PREFIX + compute_hash(joined)[:RUN_LENGTH]


def held_ids(session: Session, question_ids: Sequence[str]) -> set[str]:
    """Which of those questions the store already holds. Empty in, empty out and no query."""
    if not question_ids:
        return set()
    rows = session.scalars(
        select(Question.question_id).where(Question.question_id.in_(question_ids))
    )
    return set(rows)


class SqlQuestionStore:
    """The `QuestionStore` port over a relational database, whichever of the two it is."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        """Built with a session factory rather than a session: a transaction is per call."""
        self._sessions = sessions

    def stored_questions(self, questions: Sequence[QuestionToStore]) -> StoreReceipt:
        """Every question the store holds after writing these, and the stamps of the write."""
        published_at = datetime.now(UTC)
        asked = [question.question_id for question in questions]
        with self._sessions.begin() as session:
            already = held_ids(session, asked)
            session.add_all(
                Question(
                    question_id=question.question_id,
                    record_id=question.record_id,
                    run_id=question.run_id,
                    modality=question.modality,
                    profile=question.profile,
                    payload=dict(question.payload),
                    config_digest=question.config_digest,
                    created_at=published_at,
                )
                for question in questions
                if question.question_id not in already
            )
        return StoreReceipt(
            stored=tuple(asked),
            store_run_id=store_run_id_for(asked),
            published_at=published_at,
        )

    def answers_to(self, question_ids: Sequence[str]) -> Sequence[StoredAnnotation]:
        """Every answer the store holds to any of those questions, in no promised order."""
        if not question_ids:
            return ()
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(AnnotatorAnswer).where(
                    AnnotatorAnswer.question_id.in_(question_ids)
                )
            )
            # Materialised inside the transaction and converted here, because a row is a live ORM
            # object and the port's shape is a frozen value -- what crosses the seam must survive
            # the session that produced it.
            return tuple(
                StoredAnnotation(
                    answer_id=row.answer_id,
                    question_id=row.question_id,
                    annotator_id=row.annotator_id,
                    result=tuple(row.result),
                    was_skipped=row.was_skipped,
                    lead_time_seconds=row.lead_time_seconds,
                    submitted_at=row.submitted_at,
                )
                for row in rows
            )
