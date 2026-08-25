"""DEFINITION · the store's rows: what a published question and a returned answer look like.

Three tables, and § *The question store* draws them. Every column carries its purpose as a SQL
``comment``, so the reason a column exists survives into the database a person is querying rather
than living only here (Requirement 1's intent at the one boundary pydantic does not reach).

**The store holds the questions and the answers, and no part of a record.** No content, no label, no
verdict from an earlier phase: a store is the thing an annotation tool syncs against, so anything in
it is one integration away from a person, and Requirement 30 is asserted on what reaches one. What
joins a row back to the bus is ``record_id``, and reading it is the pipeline's business.

**``annotator_answer`` keeps the annotation's control values verbatim and decomposes nothing.**
§ *The question store* drew ``verdict``, ``corrected_value`` and ``note`` as columns; they are one
``result`` here instead, because Requirement 49 makes ``annotation_response`` *the only place an
annotation tool's shape is read* and three decomposed columns need a second reader of that shape --
in the layer furthest from the capture half that defines it, and with no record to validate a
corrected value against. The envelope is a different fact and stays decomposed: ``was_skipped`` and
``lead_time_seconds`` are the pilot's instruments and answer nothing (§8; recorded in ``spec.md``).

**Two dialects, one schema, and the differences are carried rather than argued away** (Decision 7).
``JSON`` is a real type in Postgres and a text affinity in SQLite; a timezone-aware ``DateTime`` is
stored as one in Postgres and as a naive string in SQLite; and the unique constraints this schema
leans on for the sync's idempotency are precisely where the two disagree about which violation
surfaces as what. That is why the store's tests run twice, and why nothing here reaches for a
dialect-specific upsert.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Dialect, ForeignKey, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Long enough for a digest-shaped id and short enough that a dialect with a length limit still
# indexes it. Named once because all four id columns are the same kind of string.
ID_LENGTH = 64


class UtcDateTime(TypeDecorator[datetime]):
    """An instant, in both dialects.

    ``DateTime(timezone=True)`` is an instant in Postgres and a naive string in SQLite, so the same
    row read through the default backend comes back as something that raises when compared to the
    value that was written. That is the substitute-behaves-identically assumption P26 forbids, and
    it is on a column that reaches a record -- so it is normalised here rather than carried.

    **A naive datetime is refused, not assumed to be UTC.** Guessing a caller's timezone is how a
    seven-hour error gets into a measurement nobody re-derives, and the codebase already refuses
    rather than coerces where a value could mean two things (``declared_switch``).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """UTC on the way in, so what a backend stores does not depend on who wrote it."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "the store takes an instant and this datetime names no timezone; "
                "an annotation tool's clock is a real clock somewhere"
            )
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """UTC on the way out, including from the backend that dropped the offset."""
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """What Alembic's autogenerate compares a database against: these three tables and no others."""


class Question(Base):
    """One question a run published: the join keys, the task payload, and what composed it."""

    __tablename__ = "question"

    question_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        primary_key=True,
        comment="Minted by `question_generate` over the question itself; everything joins on it.",
    )
    record_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        index=True,
        comment="Which record it asks about. Indexed: answers are read back per record.",
    )
    run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        index=True,
        comment="Which pipeline run published it. A store outlives any one run.",
    )
    modality: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        comment="The pair it was composed under, `name@version`; a question read under another is not the same question.",
    )
    profile: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        comment="The other half of that pair, stamped the same way.",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        comment="The task payload as the annotation tool takes it: `data` and nothing else.",
    )
    config_digest: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        comment="Of the annotation config this payload was composed against, as published.",
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        comment="When the store first held it. A re-publish does not move it.",
    )


class Publication(Base):
    """Where one question was pushed to, and what came back — the sync's half of the store."""

    __tablename__ = "publication"

    question_id: Mapped[str] = mapped_column(
        ForeignKey("question.question_id"),
        primary_key=True,
        comment="Which question was pushed. Half of the pair that makes the sync idempotent.",
    )
    external_system: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        primary_key=True,
        comment="Which annotation tool it went to; the other half of that pair.",
    )
    external_project_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH),
        comment="The project it landed in over there, where that system has projects.",
    )
    external_task_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH),
        comment="The id that system gave the task, which is why `question_id` also rides in `data`.",
    )
    status: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        comment="What the push did, in the sync's own words.",
    )
    pushed_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        comment="When it was pushed, by the syncing process's clock.",
    )


class AnnotatorAnswer(Base):
    """One person's answer to one question, as the annotation tool returned it."""

    __tablename__ = "annotator_answer"

    answer_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        primary_key=True,
        comment="The store's own id for this answer.",
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("question.question_id"),
        index=True,
        comment="Which question it answers. Indexed: answers are read back by question.",
    )
    annotator_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        comment="Who answered. The overlap `aggregate` folds is a count of distinct values here.",
    )
    result: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        comment="The annotation's control values, verbatim. Only `annotation_response` reads this shape.",
    )
    was_skipped: Mapped[bool] = mapped_column(
        comment="The annotator saw the question and declined it. Not a verdict, and not a missing row.",
    )
    lead_time_seconds: Mapped[float | None] = mapped_column(
        comment="How long they took, where the tool reported it. An instrument the pilot reads.",
    )
    submitted_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        comment="When they submitted it, by the annotation tool's clock.",
    )
    external_annotation_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH),
        unique=True,
        comment="That tool's id for the annotation. Unique, which is what makes pulling twice a no-op.",
    )
