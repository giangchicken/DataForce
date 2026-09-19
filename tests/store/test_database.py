"""`edge/database.py` -- what *no database* answers, and what one engine for the process means.

**No database attached is a state**, not a failure: the labelling flow works with nothing behind
it, so `open_session()` answers `None` where the variable says `off`, in any case a person types it.

**Unset is not that state.** It is the default SQLite file in the working directory, tables and
all, so an install nobody configured can take the first record. The empty and the whitespace
spellings -- both of which a compose file produces -- mean the same default, because a blank line
in a compose file is an absence and not a decision to turn the store off.

**A time is stored as it was written.** Nothing converts, on either dialect, so what a row holds is
this deployment's own clock and not an instant anybody can place from the value alone. That is the
cost of having no `TypeDecorator` here, and it is the trade this store took on purpose.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import Engine

from dataforce.edge.database import DEFAULT_STORE_FILE, NO_STORE, db
from dataforce.profile.tool_decision.sample_building import (
    create_tables,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionRecord,
    ToolDecisionSample,
)
from dataforce.tables import Base

WROTE_AT = datetime(2026, 9, 16, 15, 30, 45)

THREADS = 8


def test_every_test_runs_with_the_store_turned_off_unless_it_says_otherwise() -> None:
    """The invariant the whole suite's safety rests on, asserted rather than assumed.

    `tests/conftest.py` sets the variable to `off` for every test. If that is ever relaxed back to
    *unset*, every test that does not declare its own DSN silently starts writing to one shared
    SQLite file in the checkout -- and the store suite drops every table it made. Finding that out
    by noticing a file appear is too slow, so it is a test.
    """
    assert os.environ["DATAFORCE_DATABASE_URL"] == NO_STORE
    assert db.open_engine() is None


@pytest.mark.parametrize(
    "declared", ["off", "OFF", " Off "], ids=["off", "shouted", "padded"]
)
def test_the_store_turned_off_is_a_state_and_nothing_raises(
    declared: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The state § *The page* requires: the whole review works with no store behind it.

    Matched without case and after stripping, because this is the spelling a deployment reaches
    for to turn the store off and there is nothing to gain by refusing three quarters of it.
    """
    monkeypatch.setenv("DATAFORCE_DATABASE_URL", declared)

    assert db.open_engine() is None
    assert db.open_session() is None


@pytest.mark.parametrize(
    "declared", [None, "", "   "], ids=["unset", "empty", "whitespace"]
)
def test_an_undeclared_dsn_is_the_file_in_the_working_directory(
    declared: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """§ *Context* -- unset means a SQLite file made on first use, not *no store*.

    `chdir` because the default is resolved against the working directory, which is the whole of
    what makes it a *checkout's* database; without it this test would write into the repository.

    The DSN is what is read, not the file: `create_engine` connects to nothing, so no SQLite file
    exists until something asks for a connection. That an unconfigured install can take a record is
    proven where the app is started, which is the layer that makes the tables.
    """
    if declared is None:
        monkeypatch.delenv("DATAFORCE_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATAFORCE_DATABASE_URL", declared)
    monkeypatch.chdir(tmp_path)

    assert db.read_url() == f"sqlite+pysqlite:///{tmp_path / DEFAULT_STORE_FILE}"
    assert db.open_engine() is not None
    assert db.open_session() is not None


def test_a_declared_dsn_beats_the_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A deployment that names a database gets that one, and the default is not consulted."""
    named = f"sqlite+pysqlite:///{tmp_path / 'named.sqlite3'}"
    monkeypatch.setenv("DATAFORCE_DATABASE_URL", named)
    monkeypatch.chdir(tmp_path)

    assert db.read_url() == named
    assert DEFAULT_STORE_FILE not in (db.read_url() or "")


def test_a_time_comes_back_the_way_it_was_written(store_engine: Engine) -> None:
    """Same value on either dialect, because nothing between here and the column converts it."""
    create_tables(store_engine)
    key = uuid.uuid4()
    writing = db.open_session()
    assert writing is not None
    with writing, writing.begin():
        writing.add(
            ToolDecisionRecord(
                id=key, document={}, created_time=WROTE_AT, modified_time=WROTE_AT
            )
        )

    reading = db.open_session()
    assert reading is not None
    with reading:
        stored = reading.get(ToolDecisionRecord, key)
        assert stored is not None
        assert stored.created_time == WROTE_AT
        assert stored.created_time.tzinfo is None


def test_eight_threads_through_a_cold_cache_get_one_engine(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case FastAPI produces: a sync handler runs in the anyio threadpool, so the cache is
    entered concurrently. Without the lock each thread builds an engine and all but one leak a pool.

    The barrier is what makes the race real rather than hoped for: no thread reads the cache until
    every thread has arrived. A DSN of this test's own is what makes the cache cold -- clearing it
    here would drop an engine without disposing it, which is the leak being tested for.
    """
    monkeypatch.setenv(
        "DATAFORCE_DATABASE_URL",
        f"sqlite+pysqlite:///{tmp_path_factory.mktemp('cold') / 'store.sqlite3'}",
    )
    together = Barrier(THREADS)

    def one_engine(_: int) -> Engine | None:
        together.wait()
        return db.open_engine()

    with ThreadPoolExecutor(max_workers=THREADS) as threads:
        built = list(threads.map(one_engine, range(THREADS)))

    assert len({id(engine) for engine in built}) == 1


def test_a_changed_dsn_releases_the_pool_the_old_one_held(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two DSNs in one process is a test pointing at a new file per case, and the old pool goes."""
    first_path = tmp_path_factory.mktemp("first") / "store.sqlite3"
    second_path = tmp_path_factory.mktemp("second") / "store.sqlite3"
    monkeypatch.setenv("DATAFORCE_DATABASE_URL", f"sqlite+pysqlite:///{first_path}")
    first = db.open_engine()
    assert first is not None
    held = first.pool

    monkeypatch.setenv("DATAFORCE_DATABASE_URL", f"sqlite+pysqlite:///{second_path}")
    second = db.open_engine()

    assert second is not first
    assert first.pool is not held


def test_one_metadata_holds_every_task_s_tables() -> None:
    """What `Base` being shared buys: a profile declares its own tables and one `MetaData` knows
    them, which is what lets `create_all` name a task's two rather than reach for a registry."""
    assert issubclass(ToolDecisionRecord, Base)
    assert issubclass(ToolDecisionSample, Base)
    assert {
        ToolDecisionRecord.__tablename__,
        ToolDecisionSample.__tablename__,
    } <= set(Base.metadata.tables)
