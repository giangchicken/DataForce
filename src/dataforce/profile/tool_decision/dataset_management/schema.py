"""adapter · this task's two tables, and the SQL over them.

What `schema.py` means everywhere else in this repository -- what the stored data looks like --
except that here it is SQLAlchemy, so the tag is `adapter` and not `shape`. That tag is what lets
the router import this while `services/` cannot (`H-8`).

`record` keeps the whole of what the eight steps answered and holds personal data verbatim, so it
is never exported. `dataset` keeps what a buyer gets, de-identified, with the facets saying what
kind of sample it is. The two hold the **same rows** and differ by what is in them.

There is no `task` column: the table name is the task. `id` is a `Uuid` -- native on Postgres, 32
characters on SQLite -- so nothing has a length to choose. The two times are naive and this
deployment's own, which `edge/database.py` states the cost of.

**Which columns may be empty, and why.** The nine facets are `NOT NULL` because § *`dataset`* keeps
a facet as a column only where it is true of every row, so a facet arriving unanswered is a write
that should fail here rather than a column that quietly fills with `NULL`. `label` is the one that
may be `NULL`: whether a sample with no calls writes `[]` or `null` is § *Open*, and a column that
refused one of them would answer that question by schema.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Engine, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dataforce.edge.database import Base


class ToolDecisionRecord(Base):
    """The review, whole and unaltered. The evidence for trusting the other table."""

    __tablename__ = "tool_decision_record"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ToolDecisionDataset(Base):
    """What a buyer gets: the input and the label as the review left them, and the facets.

    Every column is computed from the `record` row of the same key, so this table can be dropped
    and rebuilt at any time and nothing else writes to it.
    """

    __tablename__ = "tool_decision_dataset"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    # `{messages, tools}` -- the turns and the catalog together, because a tool call is a call
    # against a catalog and a label stored apart from one is a label nothing can check.
    input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    label: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    # This deployment's own time, naive: nothing converts, so both dialects hand back what
    # they were given. See `edge/database.py`.
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # The nine facets § *`dataset`* names. Each is true of every row in this table and is expected
    # to stay true; anything else is a key in `notes`.
    #
    # The two that hold a set are `JSONB` on Postgres and `JSON` everywhere else, which is one
    # column type with a variant rather than two adapters. **Postgres `json` has no equality
    # operator**, so `GROUP BY call_shape` raises `could not identify an equality operator for
    # type json` there while SQLite, which stores it as text, answers -- and § *The statistics*
    # counts per value of every facet column. `jsonb` is the type that can be grouped by, and
    # § *Design*'s "both dialects group by identically" is the sentence that requires it.
    language: Mapped[str] = mapped_column(String, nullable=False)
    personal_data: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    call_shape: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    number_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    number_label_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    number_provided_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # `have_conversation_flow` and `direction` start here, each true of a *group* of label sets
    # rather than of the table. A facet added later starts here too, always: a declared column
    # added late is `NULL` for the whole corpus that existed before it, and nothing can fill it.
    # Empty rather than `NULL`, so a missing key and an absent row read differently.
    notes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


def created_tables(engine: Engine) -> None:
    """This task's two tables, made on a database that does not hold them.

    The only thing in this design that makes a table: there are no migrations, so this **creates
    and never alters**. A column added to a model above does not reach a database that already
    holds the table, which is the property that sends a new facet into `notes`.

    Named tables rather than the whole `MetaData`: `Base` is shared, so `create_all(engine)` alone
    would make every task's tables from inside this one's package.
    """
    Base.metadata.create_all(
        engine,
        tables=[
            Base.metadata.tables[named]
            for named in (
                ToolDecisionRecord.__tablename__,
                ToolDecisionDataset.__tablename__,
            )
        ],
    )
