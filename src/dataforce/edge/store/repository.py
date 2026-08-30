"""LOGIC · the QuestionStore adapter, over a SQLAlchemy session.

The port is ``dataforce/ports.py``. This is an adapter of it, and calling it a port is the path by
which someone adds a method *here* and the engine then has to import ``edge/store/`` to name a type
-- the inversion Decision 12 moved ``ports.py`` inward to prevent (T37).

**One adapter, two DSNs, and one line that knows which.** There is no ``PostgresQuestionStore``
beside a SQLite one, because SQLite and Postgres are one adapter addressed two ways (Decision 7).
The single fork is ``insert_of``: ``ON CONFLICT DO NOTHING`` has two spellings and no neutral one,
and what was written in its place was a check that races. No ``RETURNING`` and no server-side
default, so everything else the two disagree about is behaviour this module leans on -- which is why
the tests run twice rather than why the code forks.

**Writing a question the store already holds is a no-op, not an error** (§32). The id is a pure
function of the question, so a second publish of an unchanged corpus is the same rows and re-running
a phase is not something a caller has to be careful about. Insert-if-absent rather than an upsert,
and the difference is deliberate: an existing row records what was *published*, and overwriting its
payload would rewrite the question a person may already have answered.

**The no-op is the constraint's answer and not this module's.** Reading which ids the store holds
and inserting the rest is a check with a window in it: two publishes of one batch both see nothing,
both insert, and the second raises ``IntegrityError`` about a row that says exactly what it wanted
to say. ``edge/label_studio.py`` states the rule -- *a check races with a second sync and a
constraint does not* -- and this module was the one place in the tree that broke it.

**``store_run_id`` is a digest of what was written, not a fresh id per call.** A random one would
make two publishes of one batch two different keys on the record, and the field exists to say the
opposite -- *these questions, this write*. Deterministic, so a re-run's record is byte-identical
except for ``published_at``, which is a clock and is the one value this adapter puts on a record
that two runs cannot agree on. I15 meets that at T29, where both shells publish.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from agent_toolkit.string_utils import compute_hash
from sqlalchemy import Insert, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from dataforce.ports import (
    QuestionToStore,
    StoredAnnotation,
    StoreReceipt,
)

from .models import AnnotatorAnswer, Question
from .session import POSTGRES

# How a `store_run_id` is written, on `question_id`'s pattern: a prefix a person can read in a
# record and sixteen hex of digest.
RUN_PREFIX = "sr_"
RUN_LENGTH = 16

# What the written ids are joined with before they are hashed, as `scenario_hash` joins tool names.
ID_SEPARATOR = "|"

# What a second publish of one corpus conflicts on. `question_id` is a pure function of the question,
# so the conflict *is* "this question is already published" and there is nothing to update.
CONFLICT_ON = ("question_id",)


def store_run_id_for(question_ids: Sequence[str]) -> str:
    """The id of the write that put exactly those questions in the store.

    Sorted first, so the order a batch happened to arrive in is not part of which write it was:
    two runs over one corpus publish the same questions and record the same id.
    """
    joined = ID_SEPARATOR.join(sorted(question_ids))
    return RUN_PREFIX + compute_hash(joined)[:RUN_LENGTH]


def rows_for(
    questions: Sequence[QuestionToStore], published_at: datetime
) -> list[dict[str, Any]]:
    """Those questions as the columns `question` holds, stamped with one clock for the batch."""
    return [
        {
            "question_id": question.question_id,
            "record_id": question.record_id,
            "run_id": question.run_id,
            "modality": question.modality,
            "profile": question.profile,
            "payload": dict(question.payload),
            "config_digest": question.config_digest,
            "created_at": published_at,
        }
        for question in questions
    ]


def insert_of(dialect: str, rows: Sequence[Mapping[str, Any]]) -> Insert:
    """An insert of those rows that leaves a `question_id` the store holds exactly as it is.

    The one dialect-specific line in the adapter. `store_engine` admits exactly two backends
    (Decision 7), so the fallthrough is SQLite by construction rather than by default -- and a
    third would have been refused when the pool was built.
    """
    if dialect == POSTGRES:
        return (
            postgres_insert(Question)
            .values(list(rows))
            .on_conflict_do_nothing(index_elements=CONFLICT_ON)
        )
    return (
        sqlite_insert(Question)
        .values(list(rows))
        .on_conflict_do_nothing(index_elements=CONFLICT_ON)
    )


class SqlQuestionStore:
    """The `QuestionStore` port over a relational database, whichever of the two it is."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        """Built with a session factory rather than a session: a transaction is per call."""
        self._sessions = sessions

    def stored_questions(self, questions: Sequence[QuestionToStore]) -> StoreReceipt:
        """Every question the store holds after writing these, and the stamps of the write."""
        published_at = datetime.now(UTC)
        asked = [question.question_id for question in questions]
        if questions:
            with self._sessions.begin() as session:
                dialect = session.get_bind().dialect.name
                session.execute(insert_of(dialect, rows_for(questions, published_at)))
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
