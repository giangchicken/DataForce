"""One posted document as one row in each table -- or as neither -- and the table that is a function.

Written once and run twice, against a temporary SQLite file and against `DATAFORCE_TEST_DATABASE_URL`:
*one code path, two DSNs* is a claim the spec makes, and a write that behaved differently on the two
is the claim failing where it matters most, because the write is the only thing here that cannot be
re-run to find out.

**Two rows or none** is the invariant the transaction exists for. A `dataset` row with no `record`
behind it is a row nothing can prove; a `record` with no `dataset` is a review nobody can buy. So
the rollback is tested with a real constraint violation rather than a stubbed failure -- the thing
that will actually happen is a facet arriving unanswered.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dataforce.edge.database import db
from dataforce.modalities.text2text.dataset_management import DatasetSample
from dataforce.profile.tool_decision.sample_building import (
    ToolDecisionSampleBuilding,
    count_total_samples,
    create_tables,
    merge_tool_decision_db,
    rebuild_tool_decision_dataset,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionRecord,
    ToolDecisionSample,
)

POSTED_ID = "s4471"
CATALOG = [
    {
        "type": "function",
        "function": {
            "name": "OpenTicket",
            "parameters": {"type": "object", "required": [], "properties": {}},
        },
    }
]
OPENED = [{"name": "OpenTicket", "arguments": {}}]
TICKED = {
    "language": "vi",
    "ambiguous": False,
    "domain": "customer_care",
    "call_trigger": ["user_utterance"],
    "direction": "inbound",
    "have_conversation_flow": True,
}


def build_document(**overridden: Any) -> dict[str, Any]:
    """A finished review with nothing to redact: `reported` is a scan that found none."""
    document: dict[str, Any] = {
        "id": POSTED_ID,
        "messages": [{"role": "user", "content": "mở phiếu"}],
        "tools": CATALOG,
        "label": OPENED,
        "new_messages": [{"role": "user", "content": "mở phiếu"}],
        "new_tools": None,
        "new_label": OPENED,
        "personal_data": {
            "review_text": "user: mở phiếu",
            "claims": [],
            "spans": [],
            "redacted_text": None,
            "outcome": "reported",
        },
        "duplicate": None,
        "abnormal": None,
        "llm": None,
        "sft": None,
        "class": dict(TICKED),
    }
    return document | overridden


def build_stored_sample(**overridden: Any) -> DatasetSample:
    """The row a document becomes, so a write test can leave out the facet it is about."""
    facets: dict[str, Any] = {
        **TICKED,
        "personal_data": [],
        "number_turns": 1,
        "number_label_tools": 1,
        "number_provided_tools": 1,
        "schema_valid": True,
    }
    return DatasetSample(
        input={"messages": [{"role": "user", "content": "mở phiếu"}], "tools": CATALOG},
        label=tuple(OPENED),
        facets=facets | overridden,
    )


@pytest.fixture
def store_session(store_engine: Engine) -> Iterator[Session]:
    """A session on tables this fixture made, and nothing written into them yet."""
    create_tables(store_engine)
    session = db.open_session()
    assert session is not None
    with session:
        yield session


def read_dataset_row(session: Session, key: uuid.UUID) -> ToolDecisionSample:
    row = session.get(ToolDecisionSample, key)
    assert row is not None
    return row


# ------------------------------------------------------------------ the key


def test_one_posted_name_answers_to_one_key_and_two_names_to_two(
    store_session: Session,
) -> None:
    """*A second post under one `id` replaces both rows* is only true while a name keeps its key,
    which is why the key is derived from the name and not minted: a fresh one would make a
    re-reviewed sample a second row holding the same review.

    Asserted through the write rather than against the derivation, because keeping its key is a
    property of storing the same name twice and not of a hash function.
    """
    first = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )

    assert (
        merge_tool_decision_db(
            store_session, build_document(), build_stored_sample()
        ).key
        == first.key
    )
    assert (
        merge_tool_decision_db(
            store_session, build_document(id="s4472"), build_stored_sample()
        ).key
        != first.key
    )


# ------------------------------------------------------------------ two rows, one transaction


def test_one_post_writes_one_row_in_each_table_under_the_same_key(
    store_session: Session,
) -> None:
    """The two tables hold the same rows and differ by what is in them, which is the whole design:
    the protected table and the sold table, rather than one table and a promise."""
    stored = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )

    assert count_total_samples(store_session) == {
        ToolDecisionRecord.__tablename__: 1,
        ToolDecisionSample.__tablename__: 1,
    }
    assert store_session.get(ToolDecisionRecord, stored.key) is not None
    assert read_dataset_row(store_session, stored.key).id == stored.key


def test_the_record_keeps_the_document_whole_and_the_dataset_keeps_what_ships(
    store_session: Session,
) -> None:
    """Both halves of § *`dataset`*'s argument in one assertion: the raw transcript is in the
    table nothing is exported from, and the sold table holds no copy of it to find."""
    stored = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )

    record = store_session.get(ToolDecisionRecord, stored.key)
    assert record is not None
    assert record.document["id"] == POSTED_ID
    assert set(read_dataset_row(store_session, stored.key).input) == {
        "messages",
        "tools",
    }


def test_a_facet_the_table_has_no_column_for_lands_in_notes(
    store_session: Session,
) -> None:
    """`FACETS` is the whole of what splits them, so promoting one is that list and a column.
    `direction` and `have_conversation_flow` are each true of a group of label sets rather than
    of the table, which is why they start here."""
    stored = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )

    row = read_dataset_row(store_session, stored.key)
    assert row.notes == {"direction": "inbound", "have_conversation_flow": True}
    assert row.domain == "customer_care"


def test_a_second_post_replaces_both_rows_and_leaves_created_time_where_it_was(
    store_session: Session,
) -> None:
    """`merge` replaces the whole row, so the column that never moves is carried forward by hand.
    A record posted twice is one sample reviewed twice -- and the review it used to hold is gone,
    which is the cost § *`record`* states rather than designs around."""
    first = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )

    again = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample(domain="telesale")
    )

    assert again.key == first.key
    assert again.created_time == first.created_time
    assert again.modified_time > first.modified_time
    assert count_total_samples(store_session)[ToolDecisionSample.__tablename__] == 1
    assert read_dataset_row(store_session, again.key).domain == "telesale"


def test_the_first_write_of_a_sample_stamps_both_times_at_once(
    store_session: Session,
) -> None:
    """There is no row to read a `created_time` off yet, so *now* is what both columns take. That
    is also what makes the two times equal a first post and apart a replacement."""
    stored = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )

    assert stored.created_time == stored.modified_time


def test_a_failure_on_the_second_table_leaves_neither_written(
    store_session: Session,
) -> None:
    """A facet arriving unanswered is a write that fails, which is what the `NOT NULL` columns are
    for -- and it must fail *both*, or `record` grows a review whose sample was never sold."""
    unanswered = build_stored_sample()
    with pytest.raises(IntegrityError):
        merge_tool_decision_db(
            store_session,
            build_document(),
            DatasetSample(
                input=unanswered.input,
                label=unanswered.label,
                facets={
                    name: value
                    for name, value in unanswered.facets.items()
                    if name != "language"
                },
            ),
        )

    store_session.rollback()
    assert count_total_samples(store_session) == {
        ToolDecisionRecord.__tablename__: 0,
        ToolDecisionSample.__tablename__: 0,
    }


# ------------------------------------------------------------------ dataset is a function of record


def test_a_rebuild_leaves_every_row_as_it_was(store_session: Session) -> None:
    """*Drop it, rebuild it, get the same table.* The invariant that makes `dataset` safe to
    throw away, and the reason nothing else is allowed to write to it."""
    stored = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )
    before = read_dataset_row(store_session, stored.key)
    was = (before.input, before.label, before.domain, before.created_time)

    written = rebuild_tool_decision_dataset(store_session, ToolDecisionSampleBuilding())

    after = read_dataset_row(store_session, stored.key)
    assert written == 1
    assert (after.input, after.label, after.domain, after.created_time) == was


def test_a_row_edited_by_hand_is_corrected_by_a_rebuild(
    store_session: Session,
) -> None:
    """The failure this is insurance against: a `dataset` row that disagrees with its `record` is
    a bug with one possible cause, and the fix is not a migration."""
    stored = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    )
    with store_session.begin():
        store_session.execute(
            update(ToolDecisionSample)
            .where(ToolDecisionSample.id == stored.key)
            .values(domain="wrong", number_turns=99)
        )

    rebuild_tool_decision_dataset(store_session, ToolDecisionSampleBuilding())

    row = read_dataset_row(store_session, stored.key)
    assert row.domain == "customer_care"
    assert row.number_turns == 1


def test_a_rebuild_over_an_empty_record_table_empties_the_dataset(
    store_session: Session,
) -> None:
    """A function of nothing is nothing. A rebuild that left the old rows standing would make
    `dataset` a table that only ever grows, which is the opposite of the invariant."""
    merge_tool_decision_db(store_session, build_document(), build_stored_sample())
    with store_session.begin():
        store_session.execute(
            ToolDecisionRecord.__table__.delete()  # type: ignore[attr-defined]
        )

    assert (
        rebuild_tool_decision_dataset(store_session, ToolDecisionSampleBuilding()) == 0
    )
    assert count_total_samples(store_session)[ToolDecisionSample.__tablename__] == 0


def test_a_rebuild_reads_every_record_and_not_only_the_last(
    store_session: Session,
) -> None:
    """Two samples, so a rebuild that wrote one row for the whole table would be caught."""
    merge_tool_decision_db(store_session, build_document(), build_stored_sample())
    merge_tool_decision_db(
        store_session,
        build_document(id="s4472", **{"class": TICKED | {"domain": "telesale"}}),
        build_stored_sample(domain="telesale"),
    )

    assert (
        rebuild_tool_decision_dataset(store_session, ToolDecisionSampleBuilding()) == 2
    )
    assert dict(
        store_session.execute(
            select(ToolDecisionSample.domain, ToolDecisionSample.number_turns)
        ).all()
    ) == {"customer_care": 1, "telesale": 1}


def test_a_rebuilt_row_carries_the_facets_the_document_was_ticked_with(
    store_session: Session,
) -> None:
    """A rebuild recomputes the derived half and re-reads the declared half off `record.document`,
    which is the only place a tick survives -- a page has moved on by the time this runs."""
    key = merge_tool_decision_db(
        store_session, build_document(), build_stored_sample()
    ).key

    rebuild_tool_decision_dataset(store_session, ToolDecisionSampleBuilding())

    row = read_dataset_row(store_session, key)
    assert (row.language, row.ambiguous, row.call_trigger) == (
        "vi",
        False,
        ["user_utterance"],
    )
    assert row.notes == {"direction": "inbound", "have_conversation_flow": True}


def test_the_two_tables_agree_after_every_write_this_suite_makes(
    store_session: Session,
) -> None:
    """§ *Invariants* -- every `dataset` row has a `record` row under the same key, and the two
    counts agree. Asserted over keys rather than over totals, so two tables holding two different
    rows each would not pass."""
    merge_tool_decision_db(store_session, build_document(), build_stored_sample())
    merge_tool_decision_db(
        store_session, build_document(id="s4472"), build_stored_sample()
    )

    assert set(store_session.scalars(select(ToolDecisionRecord.id))) == set(
        store_session.scalars(select(ToolDecisionSample.id))
    )
