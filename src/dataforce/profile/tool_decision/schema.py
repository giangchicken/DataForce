"""adapter · this task's two tables, and the SQL over them.

What `schema.py` means everywhere else in this repository -- what the stored data looks like --
except that here it is SQLAlchemy, so the tag is `adapter` and not `shape`. That tag is what lets
the router import this while `services/` cannot (`H-8`).

**Only what SQL and the domain have to say to each other is in here.** Every read below is that
translation and nothing else: a `GROUP BY` answers in the dialect's own terms -- one text per row
here and a parsed value there, a list that cannot be a key, two spellings of one value -- and each
read hands back what those rows *mean*.

**Which values a person may tick is not here, and not anywhere below the edge.** That is a list a
tick box is drawn from, so it lives with the page. A read here answers what the rows *carry*, never
what they were allowed to carry.

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

import json
import uuid
from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Engine,
    Integer,
    String,
    Uuid,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

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
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    language: Mapped[str] = mapped_column(String, nullable=False)
    personal_data: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    call_trigger: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    number_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    number_label_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    number_provided_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    FACETS: ClassVar[tuple[str, ...]] = (
        "language",
        "personal_data",
        "ambiguous",
        "domain",
        "call_trigger",
        "number_turns",
        "number_label_tools",
        "number_provided_tools",
        "schema_valid",
    )

    notes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


def create_tables(engine: Engine) -> None:
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


def count_rows(session: Session) -> Mapping[str, int]:
    """How many rows each of this task's two tables holds.

    The two agree, and a run where they do not is a bug rather than a figure: `dataset` is computed
    from `record`, and every row of one has a row of the other under the same key.
    """
    counted: dict[str, int] = {}
    for model in (ToolDecisionRecord, ToolDecisionDataset):
        counted[model.__tablename__] = (
            session.scalar(select(func.count()).select_from(model)) or 0
        )
    return counted


def count_by_facet(session: Session) -> Mapping[str, Mapping[str, int]]:
    """One `GROUP BY` per facet column: how many rows carry each value it holds.

    Keyed by the value as text, because this is read straight into an HTTP answer and a JSON
    object has no other kind of key. A list-valued facet -- `personal_data`, `call_trigger` -- is
    keyed by the whole set, which is the facet as the row carries it: *which combinations occur*.
    Counting the values inside a set is the joint distribution's question, which
    `create_joint_distribution_matrix` answers.

    **The column says how a value is written, not the value's Python type.** A `String` column
    holds one text per row, so its own text is the key. Everything else is written as JSON, which
    is what keeps the keys apart: a JSON column holding the string `null` and one holding a JSON
    `null` are different rows, and asking the *value* whether it is text would give them one key.

    **Ordered by SQL and summed rather than assigned.** A JSON column can hold any type, so two of
    its values are not always comparable in Python and `ORDER BY` is where the ordering belongs --
    `number_turns` reads 0, 1, 2, 10 rather than 0, 1, 10, 2 for the same reason. Two groups can
    still render to one key, because SQLite groups a JSON column by its stored *text* while
    Postgres groups `jsonb` by value, so the counts are added: assigning would drop a row on one
    dialect and not the other, and the totals would stop reaching the row count with nothing
    saying where the difference went.
    """
    counted: dict[str, Mapping[str, int]] = {}
    for facet in ToolDecisionDataset.FACETS:
        column = getattr(ToolDecisionDataset, facet)
        written_as_text = isinstance(column.type, String)
        found: dict[str, int] = {}
        for value, number in session.execute(
            select(column, func.count()).group_by(column).order_by(column)
        ):
            key = value if written_as_text else json.dumps(value, ensure_ascii=False)
            found[key] = found.get(key, 0) + number
        counted[facet] = found
    return counted


def count_by_pair(
    session: Session, row_facet: str, column_facet: str
) -> Mapping[tuple[Any, Any], int]:
    """How many rows carry each pair of values the two named facet columns actually hold.

    **Only the pairs that exist.** A `GROUP BY` cannot answer for a pair no row carries, and
    putting the empty ones back is `create_joint_distribution_matrix`'s job in `services/`.

    A list-valued facet comes back as a tuple rather than as text, because the caller has to reach
    the values inside it and re-reading JSON it just wrote would be the same work twice. Splitting
    a set in SQL is what is *not* done here: `json_each` and `jsonb_array_elements` are two
    statements for one question, and *one code path, two DSNs* is the claim this store makes.
    """
    rows = getattr(ToolDecisionDataset, row_facet)
    columns = getattr(ToolDecisionDataset, column_facet)
    counted: Counter[tuple[Any, Any]] = Counter()
    for row, column, number in session.execute(
        select(rows, columns, func.count()).group_by(rows, columns)
    ):
        # A JSON list arrives unhashable, and a count has to be keyed by it.
        keyed_row = tuple(row) if isinstance(row, list) else row
        keyed_column = tuple(column) if isinstance(column, list) else column
        counted[(keyed_row, keyed_column)] += number
    return dict(counted)


def select_dataset_rows(
    session: Session,
) -> tuple[tuple[str, Mapping[str, Any], Any], ...]:
    found = session.execute(
        select(
            ToolDecisionDataset.id, ToolDecisionDataset.input, ToolDecisionDataset.label
        )
    )
    return tuple((str(key), one_input, label) for key, one_input, label in found)
