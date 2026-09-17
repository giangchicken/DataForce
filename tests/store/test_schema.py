"""This task's two tables, and the one thing `create_all` will never do for you.

**It creates and never alters.** That is not a limitation worked around here, it is the property
the design rests on: with no migrations, a column added to a model does not reach a database that
already holds the table, which is exactly why a facet added later goes into `notes` rather than
into a column. `a table missing a column does not gain it` is that property, stated as a test, so
nobody discovers it by adding a column and wondering why the corpus is empty on it.

The facet list is read out of `spec.md` rather than copied here. A copy would agree with whichever
half was edited last, and the column list is the one place where the document and the table have to
say the same thing -- § *`dataset`* is where a facet becomes a column, and this is the check that a
column added in code went through that sentence first.
"""

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, Column, Engine, MetaData, Table, Uuid, inspect

from dataforce.edge.database import Base, store
from dataforce.profile.tool_decision.dataset_management import (
    ToolDecisionDataset,
    ToolDecisionRecord,
    created_tables,
)

SPEC = Path(__file__).resolve().parents[2] / "docs" / "tool-decision-store" / "spec.md"
FACET_REQUIREMENT = (
    "A facet is a column only where it is true of every row in the table"
)

RECORD_REQUIREMENT = "One row per reviewed sample"

# What a `dataset` row carries whatever the facets are: the key, what ships, and the JSON a new
# facet starts life in, from § *`dataset`*; the two times from `layout.md`, which is where they
# are declared for this table. Hand-written, because those six are spread over five requirements
# and one table row and there is no single sentence to read them off -- which is also this check's
# limit: it holds the *facet* list against the spec, and a seventh structural column would have to
# be added here before it passed.
STRUCTURAL = frozenset(
    {"id", "input", "label", "created_time", "modified_time", "notes"}
)

AT = datetime(2026, 9, 16, 8, 30, tzinfo=UTC)


def columns_named_under(sentence: str) -> frozenset[str]:
    """Every column name in code font under the requirement that opens with that sentence.

    A requirement runs to the next numbered one or to a blank line, and the names in it are the
    backticked lower-case words -- so the sentence is the citation (`R-7`) and the list is read
    rather than copied into a second place.
    """
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    start = next(at for at, line in enumerate(lines) if sentence in line)
    requirement = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.strip() or re.match(r"\s*\d+\.\s", line):
            break
        requirement.append(line)
    return frozenset(re.findall(r"`([a-z_]+)`", " ".join(requirement)))


def a_dataset_row(**overridden: Any) -> ToolDecisionDataset:
    """One row with every `NOT NULL` column answered, so a test can leave out the one it is about."""
    columns: dict[str, Any] = {
        "id": uuid.uuid4(),
        "input": {"messages": [], "tools": []},
        "label": [],
        "created_time": AT,
        "modified_time": AT,
        "language": "vi",
        "personal_data": [],
        "ambiguous": False,
        "domain": "debt_collection",
        "call_shape": [],
        "number_turns": 0,
        "number_label_tools": 0,
        "number_provided_tools": 0,
        "schema_valid": True,
    }
    return ToolDecisionDataset(**(columns | overridden))


def test_created_tables_makes_this_task_s_two_and_no_others(
    store_engine: Engine,
) -> None:
    """Measured as a difference, because a throwaway server may already hold somebody else's."""
    before = set(inspect(store_engine).get_table_names())

    created_tables(store_engine)

    assert set(inspect(store_engine).get_table_names()) - before == {
        ToolDecisionRecord.__tablename__,
        ToolDecisionDataset.__tablename__,
    }


@pytest.mark.parametrize(
    "model",
    [ToolDecisionRecord, ToolDecisionDataset],
    ids=["record", "dataset"],
)
def test_the_made_table_holds_exactly_the_declared_columns(
    model: type[Base], store_engine: Engine
) -> None:
    """What the dialect made, against what the model declared -- the same names on both."""
    created_tables(store_engine)

    made = {
        column["name"]
        for column in inspect(store_engine).get_columns(model.__tablename__)
    }

    assert made == set(Base.metadata.tables[model.__tablename__].columns.keys())


def test_running_it_twice_makes_nothing_and_raises_nothing(
    store_engine: Engine,
) -> None:
    """Nothing wires this to a startup yet. Whatever does will call it against a database that
    already holds the tables, so the second call has to make nothing and raise nothing."""
    created_tables(store_engine)
    made = set(inspect(store_engine).get_table_names())

    created_tables(store_engine)

    assert set(inspect(store_engine).get_table_names()) == made


def test_a_table_missing_a_column_does_not_gain_one(store_engine: Engine) -> None:
    """The property the whole `notes` rule hangs off: `create_all` creates, and alters nothing.

    So a facet promoted to a column is a statement somebody writes by hand against a live database,
    and a facet added to a model is a column no existing deployment has.
    """
    stripped = MetaData()
    Table(
        ToolDecisionDataset.__tablename__,
        stripped,
        Column("id", Uuid, primary_key=True),
        Column("input", JSON, nullable=False),
    ).create(store_engine)

    created_tables(store_engine)

    made = {
        column["name"]
        for column in inspect(store_engine).get_columns(
            ToolDecisionDataset.__tablename__
        )
    }
    assert made == {"id", "input"}


def test_notes_is_an_empty_object_where_nothing_was_written_to_it(
    store_engine: Engine,
) -> None:
    """A missing key and an absent row are different readings, and `NULL` would make them one."""
    created_tables(store_engine)
    row = a_dataset_row()
    session = store.open_session()
    assert session is not None
    with session, session.begin():
        session.add(row)
        key = row.id

    reading = store.open_session()
    assert reading is not None
    with reading:
        stored = reading.get(ToolDecisionDataset, key)
        assert stored is not None
        assert stored.notes == {}


def test_the_facet_columns_are_the_ones_the_spec_names() -> None:
    """A facet added in code and not in § *`dataset`* fails here, and so does the other way round."""
    declared = frozenset(
        Base.metadata.tables[ToolDecisionDataset.__tablename__].columns.keys()
    )

    assert declared - STRUCTURAL == columns_named_under(FACET_REQUIREMENT)


def test_the_record_table_holds_the_four_columns_the_spec_names() -> None:
    """The other half, and the one the model cannot answer for itself.

    Comparing a made table with the model that made it is true by construction. § *`record`* names
    four columns, and this is what holds the model to them -- `record` is the table that keeps
    personal data verbatim, so a column arriving in it without going through that sentence first is
    the one worth catching.
    """
    declared = frozenset(
        Base.metadata.tables[ToolDecisionRecord.__tablename__].columns.keys()
    )

    assert declared == columns_named_under(RECORD_REQUIREMENT)
