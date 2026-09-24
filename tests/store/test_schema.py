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
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import (
    JSON,
    Column,
    Engine,
    MetaData,
    Table,
    Uuid,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import Session

from dataforce.edge.database import db
from dataforce.profile.tool_decision.sample_building import (
    count_by_facet,
    count_by_pair,
    count_total_samples,
    create_tables,
    select_sample_contents,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionQueuedSample,
    ToolDecisionRecord,
    ToolDecisionSample,
)
from dataforce.tables import Base

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


def read_columns_under(sentence: str) -> frozenset[str]:
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


def build_sample(**overridden: Any) -> ToolDecisionSample:
    """One row with every `NOT NULL` column answered, so a test can leave out the one it is about."""
    columns: dict[str, Any] = {
        "id": uuid.uuid4(),
        "input": {"messages": [], "tools": []},
        "label": [],
        "created_time": AT,
        "modified_time": AT,
        "language": "vi",
        "personal_data": [],
        "ambiguous": "LOW",
        "domain": "debt_collection",
        "call_trigger": [],
        "number_turns": 0,
        "number_label_tools": 0,
        "number_provided_tools": 0,
        "schema_valid": True,
    }
    return ToolDecisionSample(**(columns | overridden))


def test_created_tables_makes_this_task_s_three_and_no_others(
    store_engine: Engine,
) -> None:
    """Measured as a difference, because a throwaway server may already hold somebody else's."""
    before = set(inspect(store_engine).get_table_names())

    create_tables(store_engine)

    assert set(inspect(store_engine).get_table_names()) - before == {
        ToolDecisionRecord.__tablename__,
        ToolDecisionSample.__tablename__,
        ToolDecisionQueuedSample.__tablename__,
    }


@pytest.mark.parametrize(
    "model",
    [ToolDecisionRecord, ToolDecisionSample],
    ids=["record", "dataset"],
)
def test_the_made_table_holds_exactly_the_declared_columns(
    model: type[Base], store_engine: Engine
) -> None:
    """What the dialect made, against what the model declared -- the same names on both."""
    create_tables(store_engine)

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
    create_tables(store_engine)
    made = set(inspect(store_engine).get_table_names())

    create_tables(store_engine)

    assert set(inspect(store_engine).get_table_names()) == made


def test_a_table_missing_a_column_does_not_gain_one(store_engine: Engine) -> None:
    """The property the whole `notes` rule hangs off: `create_all` creates, and alters nothing.

    So a facet promoted to a column is a statement somebody writes by hand against a live database,
    and a facet added to a model is a column no existing deployment has.
    """
    stripped = MetaData()
    Table(
        ToolDecisionSample.__tablename__,
        stripped,
        Column("id", Uuid, primary_key=True),
        Column("input", JSON, nullable=False),
    ).create(store_engine)

    create_tables(store_engine)

    made = {
        column["name"]
        for column in inspect(store_engine).get_columns(
            ToolDecisionSample.__tablename__
        )
    }
    assert made == {"id", "input"}


def test_notes_is_an_empty_object_where_nothing_was_written_to_it(
    store_engine: Engine,
) -> None:
    """A missing key and an absent row are different readings, and `NULL` would make them one."""
    create_tables(store_engine)
    row = build_sample()
    session = db.open_session()
    assert session is not None
    with session, session.begin():
        session.add(row)
        key = row.id

    reading = db.open_session()
    assert reading is not None
    with reading:
        stored = reading.get(ToolDecisionSample, key)
        assert stored is not None
        assert stored.notes == {}


def test_the_facet_columns_are_the_ones_the_spec_names() -> None:
    """A facet added in code and not in § *`dataset`* fails here, and so does the other way round."""
    declared = frozenset(
        Base.metadata.tables[ToolDecisionSample.__tablename__].columns.keys()
    )

    assert declared - STRUCTURAL == read_columns_under(FACET_REQUIREMENT)


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

    assert declared == read_columns_under(RECORD_REQUIREMENT)


# --------------------------------------------------------------- what the corpus can be asked

# Three rows chosen so every count below has something to be wrong about: two share a
# `domain` × `call_trigger` pair and the third carries a set of two, which is the case a single
# `GROUP BY` cannot split. Each also ships its own input and label, because the same rows are what
# the duplicate grouping and the label measurements are read off.
COUNTED: tuple[Mapping[str, Any], ...] = (
    {
        "input": {"messages": [{"role": "user", "content": "nợ bao nhiêu"}]},
        "label": [{"name": "Lookup", "arguments": {"id": "KH-1"}}],
        "domain": "debt_collection",
        "call_trigger": ["condition_met"],
        "personal_data": ["PHONE"],
        "number_turns": 2,
        "notes": {"direction": "inbound", "have_conversation_flow": False},
    },
    {
        "input": {"messages": [{"role": "user", "content": "nợ bao nhiêu"}]},
        "label": [{"name": "Lookup", "arguments": {"id": "KH-1"}}],
        "domain": "debt_collection",
        "call_trigger": ["condition_met"],
        "personal_data": ["PHONE"],
        "number_turns": 2,
        "notes": {"direction": "outbound", "have_conversation_flow": True},
    },
    # **And one carrying no note at all**, which is what every row written before a facet was
    # declared looks like. A count that dropped it would say the corpus is smaller than it is.
    {
        "input": {"messages": [{"role": "user", "content": "cảm ơn em"}]},
        "label": None,
        "domain": "telesale",
        "call_trigger": ["user_utterance", "every_turn"],
        "language": "en",
        "ambiguous": "HIGH",
        "schema_valid": False,
        "number_turns": 4,
    },
)


@pytest.fixture
def corpus_session(store_engine: Engine) -> Iterator[Session]:
    """A session open over `COUNTED`, written into tables this fixture made."""
    create_tables(store_engine)
    writing = db.open_session()
    assert writing is not None
    with writing, writing.begin():
        for facets in COUNTED:
            writing.add(build_sample(**facets))

    reading = db.open_session()
    assert reading is not None
    with reading:
        yield reading


def test_the_facets_counted_are_the_columns_the_table_declares() -> None:
    """The list `count_by_facet` walks against the table it walks over.

    The list hangs off the class whose facets they are, so it cannot drift to another table -- but
    it is still the same nine names twice, and a column added without being counted is the failure
    this catches. § *`dataset`*'s own check is the test above.
    """
    declared = frozenset(
        Base.metadata.tables[ToolDecisionSample.__tablename__].columns.keys()
    )

    assert set(ToolDecisionSample.FACETS) == declared - STRUCTURAL


def test_row_counts_answers_each_table_and_not_one_of_them_twice(
    corpus_session: Session,
) -> None:
    """Deliberately lopsided: three rows in one table and one in the other, so a count that read
    a single table and answered for both would have to be right about a number it never saw."""
    corpus_session.add(
        ToolDecisionRecord(
            id=uuid.uuid4(), document={}, created_time=AT, modified_time=AT
        )
    )
    corpus_session.commit()

    assert count_total_samples(corpus_session) == {
        ToolDecisionRecord.__tablename__: 1,
        ToolDecisionSample.__tablename__: 3,
    }


def test_counted_by_facet_answers_a_count_per_value_of_every_facet(
    corpus_session: Session,
) -> None:
    """All nine, and every kind of column among them: text, boolean, integer and a JSON set.

    A text column is counted by its own value and every other kind by the JSON of it, which is
    what `ambiguous` reading `LOW` rather than `"LOW"` shows.
    """
    counted = count_by_facet(corpus_session)

    assert set(counted) >= set(ToolDecisionSample.FACETS)
    assert counted["domain"] == {"debt_collection": 2, "telesale": 1}
    assert counted["language"] == {"en": 1, "vi": 2}
    assert counted["ambiguous"] == {"LOW": 2, "HIGH": 1}
    assert counted["number_turns"] == {"2": 2, "4": 1}
    assert counted["schema_valid"] == {"false": 1, "true": 2}


def test_a_list_valued_facet_is_counted_by_the_value_and_not_by_the_set(
    corpus_session: Session,
) -> None:
    """One row answering twice is two answers, and both are counted.

    Counted whole, a facet holding a list draws a bar per combination -- `["FIRST_NAME", "NAME"]`
    beside `["FIRST_NAME"]` beside `[]` -- which is a chart of set membership and answers nothing
    a reviewer asks of the panel. *Which combinations occur* is the joint matrix's question and
    `count_by_pair` is where it is asked.

    A row answering nothing still answered, so an empty list keeps a name rather than falling out
    of the count -- *how many hold no personal data* is the first thing asked of that panel.
    """
    counted = count_by_facet(corpus_session)

    assert counted["call_trigger"] == {
        "condition_met": 2,
        "user_utterance": 1,
        "every_turn": 1,
    }
    assert counted["personal_data"] == {"none": 1, "PHONE": 2}


def test_a_facet_in_notes_is_counted_like_any_other(corpus_session: Session) -> None:
    """The hole this closes: a facet that is a key rather than a column was **write-only**.

    A person ticks `have_conversation_flow`, `build_tool_decision_sample` puts it in `notes`
    because it is not true of every row in the table, and then no reader on any route ever answers
    what the corpus holds of it -- not the page of rows, not the row opened whole, not the
    statistics. It was stored and unreadable.

    Counted in Python and not in a `GROUP BY`, because reading inside a JSON column is spelled
    differently in every dialect and this file is the one place the two must stay one code path.
    """
    counted = count_by_facet(corpus_session)

    assert set(counted) - set(ToolDecisionSample.FACETS) == {
        "direction",
        "have_conversation_flow",
    }
    assert counted["direction"] == {"inbound": 1, "none": 1, "outbound": 1}


def test_a_row_written_before_a_note_facet_existed_is_counted_under_none(
    corpus_session: Session,
) -> None:
    """Every distribution still adds up to the rows, which is what the panel reads them against.

    A facet declared today means every older row answered nothing, and a count that dropped those
    rows would draw a chart of a corpus smaller than the one the totals report -- the same reason
    an empty list keeps a name of its own.
    """
    counted = count_by_facet(corpus_session)

    assert counted["have_conversation_flow"] == {"false": 1, "none": 1, "true": 1}
    assert (
        sum(counted["have_conversation_flow"].values())
        == (count_total_samples(corpus_session)[ToolDecisionSample.__tablename__])
    )


def test_a_note_value_is_read_as_text_rather_than_as_its_json(
    corpus_session: Session,
) -> None:
    """`inbound`, never `"inbound"`. A string is a string wherever it is stored.

    The column path tells a text column from a JSON one by the column's own type, which a key
    inside one JSON object has nothing to answer with -- so the value's own type is what says it.
    A boolean still reads as `true`, the way `schema_valid` does.
    """
    counted = count_by_facet(corpus_session)

    assert "inbound" in counted["direction"]
    assert '"inbound"' not in counted["direction"]
    assert set(counted["have_conversation_flow"]) == {"true", "false", "none"}


def test_counted_by_pair_answers_only_the_pairs_the_rows_carry(
    corpus_session: Session,
) -> None:
    """Two of the twelve declared cells, because a `GROUP BY` cannot answer for a pair no row has.

    The set comes back as a tuple rather than as text: the caller has to reach the values inside
    it, and re-reading JSON this layer just wrote would be the same work twice.
    """
    assert count_by_pair(corpus_session, "domain", "call_trigger") == {
        ("debt_collection", ("condition_met",)): 2,
        ("telesale", ("user_utterance", "every_turn")): 1,
    }


def test_selecting_dataset_rows_answers_the_key_the_input_and_the_label(
    corpus_session: Session,
) -> None:
    """All three columns in one read, because the duplicate grouping is given all three."""
    rows = select_sample_contents(corpus_session)

    assert {key for key, _, _ in rows} == {
        str(row.id) for row in corpus_session.scalars(select(ToolDecisionSample))
    }
    assert sorted(
        (one_input["messages"][0]["content"], label is None)
        for _, one_input, label in rows
    ) == [("cảm ơn em", True), ("nợ bao nhiêu", False), ("nợ bao nhiêu", False)]


def test_a_numeric_facet_is_counted_in_number_order(corpus_session: Session) -> None:
    """Ordered by the value, not by the text it renders as.

    The keys are text because a JSON object has no other kind, and sorting *those* would put a
    corpus's ten-turn conversations between its one-turn and its two-turn ones.
    """
    corpus_session.add(build_sample(number_turns=10))
    corpus_session.commit()

    assert list(count_by_facet(corpus_session)["number_turns"]) == ["2", "4", "10"]


def test_a_json_column_holding_a_null_is_counted_and_does_not_raise(
    corpus_session: Session,
) -> None:
    """`nullable=False` does not refuse a JSON `null`: SQLAlchemy writes Python `None` into a JSON
    column as the text `null`, and the column is not null, it holds one.

    So the read has to be total over whatever a JSON column holds. Two of its values are not
    always comparable in Python, which is why nothing here sorts them, and the JSON `null` is kept
    apart from a row holding the *string* `null` because the column says how a value is written.
    """
    corpus_session.add(build_sample(personal_data=None))
    corpus_session.add(build_sample(personal_data="null"))
    corpus_session.commit()

    counted = count_by_facet(corpus_session)["personal_data"]

    assert counted["null"] == 1
    assert counted['"null"'] == 1
    assert counted["PHONE"] == 2


@pytest.mark.parametrize("facet", ToolDecisionSample.FACETS)
def test_every_facet_s_counts_add_up_to_the_number_of_rows(
    facet: str, corpus_session: Session
) -> None:
    """The property a `GROUP BY` read has to keep: every row is counted once **per answer**.

    It is what breaks first if two groups are ever folded onto one key by assignment rather than
    by adding -- a row disappears, and no figure in the answer says where it went. A facet holding
    a list is a row answering several times, so the sum it has to reach is the answers and not the
    rows; a row answering nothing is one answer, which is what keeps an empty list in the count.
    """
    answers = 0
    for value in corpus_session.scalars(select(getattr(ToolDecisionSample, facet))):
        answers += (len(value) or 1) if isinstance(value, list) else 1

    counted = count_by_facet(corpus_session)[facet]

    assert sum(counted.values()) == answers
    assert answers >= count_total_samples(corpus_session)["tool_decision_dataset"]


def test_two_spellings_of_one_json_value_are_summed_and_not_overwritten(
    corpus_session: Session,
) -> None:
    """T9's *both dialects answer the same* stated as a case, and the one place they differ.

    SQLite groups a JSON column by its stored **text**, so a value another writer spelled with a
    space is a second group that reads back as the same Python list; Postgres groups `jsonb` by
    value and returns one. Adding the groups is what makes the two agree -- and is what keeps the
    counts reaching the row count, which is the failure a reader would otherwise never see.
    """
    corpus_session.add(build_sample(domain="spelled", call_trigger=["condition_met"]))
    corpus_session.commit()
    corpus_session.execute(
        text(
            "UPDATE tool_decision_dataset SET call_trigger = '[\"condition_met\" ]' "
            "WHERE domain = 'spelled'"
        )
    )
    corpus_session.commit()

    assert count_by_facet(corpus_session)["call_trigger"]["condition_met"] == 3
