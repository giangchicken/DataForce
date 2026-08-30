"""The two fixtures a store test and a `publish` test both need, and the migration behind them.

Here rather than in `test_store.py` because `test_publish.py` runs the stage against the real
adapter too — §30's second half, since one adapter is a hypothetical seam. A fixture shared by
importing it is a name pytest then sees twice; a `conftest.py` is the mechanism that exists for this.

`store_at` is what makes Decision 7's *run the tests twice* real: every test that takes it runs once
on a SQLite file in `tmp_path` and once, under `-m integration`, on the Postgres named by
`DATAFORCE_TEST_DATABASE_URL`. With none attached the second is skipped rather than passed, because
*not run* and *passed* are different claims.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from dataforce.edge.store.models import AnnotatorAnswer
from dataforce.edge.store.repository import SqlQuestionStore
from dataforce.edge.store.session import DATABASE_URL, sessions_to, store_engine
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
