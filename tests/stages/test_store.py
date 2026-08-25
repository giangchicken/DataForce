"""T23 · the question store: three tables, one adapter, and the two constraints the sync rests on.

**Every test in this file runs twice** (Decision 7). The `store` fixture is parametrised over two
DSNs: a SQLite file in `tmp_path`, which is what `make check` runs, and a real Postgres named by
`DATAFORCE_TEST_DATABASE_URL`, which is marked `integration` and runs behind that gate. A store test
that passes on SQLite and has never run on Postgres is not evidence — the two disagree about type
affinity, about what a JSON column is, and about which constraint violation surfaces as what, and
this schema leans on two unique constraints for the sync's idempotency.

**The schema comes from the migration, never from `create_all`.** Applying `alembic upgrade head` to
an empty database is the acceptance criterion, and it is also what makes every test below a test of
the migration: a column the migration forgot is a query that fails here rather than in the pilot.

Every fixture is invented (AGENTS.md §9).
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from dataforce.edge.store.models import AnnotatorAnswer, Publication, Question
from dataforce.edge.store.repository import SqlQuestionStore, store_run_id_for
from dataforce.edge.store.session import (
    DATABASE_URL,
    sessions_to,
    store_engine,
)
from dataforce.ports import QuestionToStore

ROOT = Path(__file__).resolve().parents[2]

# Where `make integration` says a real Postgres is. Named rather than assumed: a missing address is
# *not run*, which is a different report from *failed* (T34's own distinction).
POSTGRES_URL = "DATAFORCE_TEST_DATABASE_URL"

# The three tables § *The question store* draws, and no fourth.
TABLES = {"question", "publication", "annotator_answer"}

# One annotation's control values, in Label Studio's shape: a `choices` list and a `textarea` list.
# Verbatim is the promise, so the fixture is nested and awkward on purpose.
RESULT: list[dict[str, Any]] = [
    {
        "from_name": "verdict",
        "to_name": "conversation",
        "type": "choices",
        "value": {"choices": ["incorrect"]},
    },
    {
        "from_name": "corrected_arguments",
        "to_name": "conversation",
        "type": "textarea",
        "value": {"text": ['{"SendStatement": {"ky": "thang_nay"}}']},
    },
]

SUBMITTED = datetime(2026, 8, 25, 9, 30, tzinfo=UTC)


def a_question(
    question_id: str = "q_0000000000000001", **written: Any
) -> QuestionToStore:
    """One question in the shape `publish` hands the store."""
    return QuestionToStore(
        **{
            "question_id": question_id,
            "record_id": "3f9a1c0b7e4d2856",
            "run_id": "r_2026-08-25T00:00:00Z_9f3c",
            "modality": "text2text@1",
            "profile": "tool_decision@1",
            "payload": {"question_id": question_id, "question": "Tool nào cần gọi?"},
            "config_digest": "a1b2c3d4",
            **written,
        }
    )


def an_answer(
    answer_id: str = "a_1",
    question_id: str = "q_0000000000000001",
    **written: Any,
) -> AnnotatorAnswer:
    """One answer as the sync will write it — by the model, because writing answers is T26's."""
    return AnnotatorAnswer(
        **{
            "answer_id": answer_id,
            "question_id": question_id,
            "annotator_id": "u_14",
            "result": RESULT,
            "was_skipped": False,
            "lead_time_seconds": 41.5,
            "submitted_at": SUBMITTED,
            "external_annotation_id": None,
            **written,
        }
    )


def upgraded(url: str) -> None:
    """`alembic upgrade head` against that database, through the real command.

    Down to base first, so a Postgres that a previous run left populated is the empty database this
    is supposed to be applied to. On a fresh SQLite file it is a no-op.
    """
    config = Config(str(ROOT / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(
    params=[
        "sqlite",
        pytest.param("postgres", marks=pytest.mark.integration),
    ]
)
def store_at(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """A migrated, empty database of that dialect, and the DSN reaching it.

    The environment is where the DSN goes, because that is where `env.py` and `session.py` both read
    it — pointing a test at a database by any other channel would prove a path production has not.
    """
    if request.param == "sqlite":
        url = f"sqlite+pysqlite:///{tmp_path / 'store.sqlite3'}"
    else:
        declared = os.environ.get(POSTGRES_URL)
        if not declared:
            pytest.skip(
                f"{POSTGRES_URL} names no Postgres; the same tests did not run on one"
            )
        url = declared
    monkeypatch.setenv(DATABASE_URL, url)
    upgraded(url)
    yield url


@pytest.fixture
def sessions(store_at: str) -> sessionmaker[Session]:
    """A session factory onto that database, for the rows only the sync will ever write."""
    return sessions_to(store_engine(store_at))


@pytest.fixture
def store(sessions: sessionmaker[Session]) -> SqlQuestionStore:
    """The adapter under test, over that database."""
    return SqlQuestionStore(sessions)


def rows_of(sessions: sessionmaker[Session], model: Any) -> list[Any]:
    """Every row of one table, read outside the adapter so a test can see what it wrote.

    A read-only session rather than `begin()`: a commit expires every attribute, and the rows are
    read after it closes.
    """
    with sessions() as session:
        return list(session.scalars(select(model)).all())


# --- the migration, which is where the schema comes from ---


def test_the_migration_applies_to_an_empty_database(store_at: str) -> None:
    """T23's acceptance criterion, run through `alembic upgrade head` and not `create_all`."""
    assert TABLES <= set(inspect(store_engine(store_at)).get_table_names())


def test_the_migration_and_the_models_say_the_same_schema(store_at: str) -> None:
    """P31 over a schema that is written twice: `alembic check` is the comparison, and it is run.

    A column added to `models.py` and never migrated passes every test whose database the migration
    built — right up to the first query that reads it, which is production. This is the day-one
    failure instead.
    """
    command.check(Config(str(ROOT / "alembic.ini")))


def test_applying_it_twice_is_a_no_op(store_at: str) -> None:
    """A migration that is not idempotent makes a deploy a thing someone has to time."""
    upgraded(store_at)

    assert TABLES <= set(inspect(store_engine(store_at)).get_table_names())


# --- writing questions ---


def test_a_question_written_is_a_question_the_store_holds(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """Every column the row carries, read back through a second connection."""
    store.stored_questions([a_question()])

    held = rows_of(sessions, Question)
    assert [row.question_id for row in held] == ["q_0000000000000001"]
    assert held[0].record_id == "3f9a1c0b7e4d2856"
    assert held[0].payload == a_question().payload
    assert held[0].config_digest == "a1b2c3d4"


def test_writing_one_question_twice_is_one_row(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """P22: re-running a phase is not something a caller has to be careful about."""
    store.stored_questions([a_question()])
    store.stored_questions([a_question()])

    assert len(rows_of(sessions, Question)) == 1


def test_a_second_write_does_not_rewrite_what_was_published(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """Insert-if-absent, not upsert: the row records the question a person may have answered."""
    store.stored_questions([a_question()])

    store.stored_questions([a_question(config_digest="deadbeef")])

    assert rows_of(sessions, Question)[0].config_digest == "a1b2c3d4"


def test_the_receipt_names_every_question_in_the_batch(store: SqlQuestionStore) -> None:
    """Including one an earlier write stored — the receipt is what the store holds, not what it just did."""
    store.stored_questions([a_question()])

    receipt = store.stored_questions(
        [a_question(), a_question(question_id="q_0000000000000002")]
    )

    assert receipt.stored == ("q_0000000000000001", "q_0000000000000002")


def test_the_receipt_stamps_when_the_store_wrote(store: SqlQuestionStore) -> None:
    """The clock is the store's, because no engine module holds one (I1)."""
    before = datetime.now(UTC)

    receipt = store.stored_questions([a_question()])

    assert before <= receipt.published_at <= datetime.now(UTC)


def test_writing_nothing_stores_nothing_and_still_returns_a_receipt(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """A phase where `triage` selected no record is an ordinary phase, not an error."""
    receipt = store.stored_questions([])

    assert receipt.stored == ()
    assert rows_of(sessions, Question) == []


# --- the id of a write ---


def test_two_writes_of_one_batch_share_a_store_run_id(store: SqlQuestionStore) -> None:
    """The field says *these questions, this write*; a random id would say the opposite."""
    first = store.stored_questions([a_question()])

    assert store.stored_questions([a_question()]).store_run_id == first.store_run_id


def test_the_order_a_batch_arrived_in_is_not_part_of_which_write_it_was() -> None:
    """Two runs over one corpus publish the same questions and record the same id."""
    forwards = store_run_id_for(["q_0000000000000001", "q_0000000000000002"])

    assert forwards == store_run_id_for(["q_0000000000000002", "q_0000000000000001"])


def test_a_different_batch_is_a_different_write() -> None:
    """One more question in the batch is one more question published, and the id says so."""
    one = store_run_id_for(["q_0000000000000001"])

    assert one != store_run_id_for(["q_0000000000000001", "q_0000000000000002"])


# --- reading answers ---


def test_answers_come_back_for_the_questions_asked_about(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """The join is `question_id`, and the store has never seen a record."""
    store.stored_questions([a_question(), a_question(question_id="q_0000000000000002")])
    with sessions.begin() as session:
        session.add(an_answer())
        session.add(an_answer(answer_id="a_2", question_id="q_0000000000000002"))

    answered = store.answers_to(["q_0000000000000001"])

    assert [answer.question_id for answer in answered] == ["q_0000000000000001"]
    assert answered[0].annotator_id == "u_14"


def test_the_control_values_come_back_verbatim(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """Requirement 49: only `answer_from_response` reads this shape, so the store may not touch it."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(an_answer())

    assert list(store.answers_to(["q_0000000000000001"])[0].result) == RESULT


def test_the_two_instruments_the_pilot_reads_survive_the_round_trip(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """`was_skipped` and `lead_time_seconds` are measurements, not bookkeeping."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(an_answer(was_skipped=True, lead_time_seconds=None))

    skipped = store.answers_to(["q_0000000000000001"])[0]
    assert skipped.was_skipped
    assert skipped.lead_time_seconds is None


def test_when_it_was_submitted_survives_the_round_trip(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """The same instant, and still an instant: a naive datetime out of one backend and an aware one
    out of the other is the substitution P26 forbids assuming away."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(an_answer())

    assert store.answers_to(["q_0000000000000001"])[0].submitted_at == SUBMITTED


def test_two_annotators_answering_one_question_are_two_answers(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """The overlap `aggregate` folds is this: one question, as many answers as the rung asked for."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(an_answer())
        session.add(an_answer(answer_id="a_2", annotator_id="u_15"))

    assert len(store.answers_to(["q_0000000000000001"])) == 2


def test_a_question_nobody_answered_comes_back_with_nothing(
    store: SqlQuestionStore,
) -> None:
    """Counting is what tells *unanswered* from *answered with nothing*."""
    store.stored_questions([a_question()])

    assert store.answers_to(["q_0000000000000001"]) == ()


def test_asking_about_no_questions_returns_nothing(store: SqlQuestionStore) -> None:
    """A record with no published question makes no query at all."""
    assert store.answers_to([]) == ()


# --- the constraints the sync's idempotency rests on (Decision 7) ---


def test_one_annotation_cannot_be_pulled_into_two_rows(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """The unique `external_annotation_id`: pulling the same annotation twice is a no-op."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(an_answer(external_annotation_id="ls_88"))

    with pytest.raises(IntegrityError):
        with sessions.begin() as session:
            session.add(an_answer(answer_id="a_2", external_annotation_id="ls_88"))


def test_two_annotations_with_no_external_id_are_both_kept(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """A unique column full of nulls is not a unique column, in either dialect."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(an_answer())
        session.add(an_answer(answer_id="a_2"))

    assert len(store.answers_to(["q_0000000000000001"])) == 2


def test_one_question_cannot_be_pushed_to_one_system_twice(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """The other half of the sync's idempotency: `(question_id, external_system)`."""
    store.stored_questions([a_question()])
    with sessions.begin() as session:
        session.add(
            Publication(
                question_id="q_0000000000000001",
                external_system="label_studio",
                external_project_id="7",
                external_task_id="1041",
                status="pushed",
                pushed_at=SUBMITTED,
            )
        )

    with pytest.raises(IntegrityError):
        with sessions.begin() as session:
            session.add(
                Publication(
                    question_id="q_0000000000000001",
                    external_system="label_studio",
                    external_project_id="7",
                    external_task_id="1042",
                    status="pushed",
                    pushed_at=SUBMITTED,
                )
            )


def test_the_same_question_may_be_pushed_to_two_systems(
    store: SqlQuestionStore, sessions: sessionmaker[Session]
) -> None:
    """The pair is the constraint, not the question: the sync is per system."""
    store.stored_questions([a_question()])

    with sessions.begin() as session:
        for system in ("label_studio", "somewhere_else"):
            session.add(
                Publication(
                    question_id="q_0000000000000001",
                    external_system=system,
                    external_project_id=None,
                    external_task_id=None,
                    status="pushed",
                    pushed_at=SUBMITTED,
                )
            )

    assert len(rows_of(sessions, Publication)) == 2


def test_an_answer_to_a_question_the_store_does_not_hold_is_refused(
    sessions: sessionmaker[Session],
) -> None:
    """The foreign key, which SQLite ships switched off — so this is the P26 test, not a formality."""
    with pytest.raises(IntegrityError):
        with sessions.begin() as session:
            session.add(an_answer(question_id="q_nobody_published"))
