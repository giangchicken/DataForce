"""`edge/database.py` -- which database this is, and what one engine for the process means.

**There is always one.** A deployment that names nothing gets a SQLite file in the working
directory, tables and all, so an install nobody configured can take the first record; the empty and
the whitespace spellings -- both of which a compose file produces -- are that same absence, because
a blank line in a compose file is not a decision.

**A declared one is not fallen back on.** Named and unreachable is refused rather than quietly
replaced with the default: a service that wrote to a second place while the first was down would
split the corpus, and nobody would know until an export came back short.

**The tables are made on the way to a session.** `create_engine` connects to nothing, so a database
is only ever named until something reads it -- and one named at startup can be gone by the
afternoon.

**A time is stored as it was written.** Nothing converts, on either dialect, so what a row holds is
this deployment's own clock and not an instant anybody can place from the value alone. That is the
cost of having no `TypeDecorator` here, and it is the trade this store took on purpose.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from dataforce.edge.database import DEFAULT_STORE_FILE, Database, db
from dataforce.profile.tool_decision.sample_building import (
    create_tables,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionRecord,
    ToolDecisionSample,
)
from dataforce.tables import Base
from tests.conftest import attach

WROTE_AT = datetime(2026, 9, 16, 15, 30, 45)

THREADS = 8


def test_every_test_writes_to_a_database_of_its_own(tmp_path: Path) -> None:
    """The invariant the whole suite's safety rests on, asserted rather than assumed.

    `tests/conftest.py` hands every test a file under its own `tmp_path`. If that is ever relaxed,
    every test that names nothing silently starts writing to one shared SQLite file in the
    checkout, carried between tests in whatever order they ran. Finding that out by noticing a
    file appear is too slow, so it is a test.
    """
    assert db.database_url == make_url(
        f"sqlite+pysqlite:///{tmp_path / 'store.sqlite3'}"
    )


@pytest.mark.parametrize(
    "declared", [None, "", "   "], ids=["unset", "empty", "whitespace"]
)
def test_naming_no_database_is_the_file_in_the_working_directory(
    declared: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """§ *Context* -- naming nothing is a SQLite file made on first use, and never *no database*.

    `chdir` because the default is resolved against the working directory, which is the whole of
    what makes it a *checkout's* database; without it this test would write into the repository.
    """
    monkeypatch.chdir(tmp_path)
    unnamed = Database(declared)

    assert unnamed.database_url == make_url(
        f"sqlite+pysqlite:///{tmp_path / DEFAULT_STORE_FILE}"
    )
    with unnamed.open_session() as opened:
        assert opened.get_bind() is unnamed.open_engine()
    assert (tmp_path / DEFAULT_STORE_FILE).exists()


def test_a_declared_dsn_beats_the_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A deployment that names a database gets that one, and the default is not consulted."""
    named = f"sqlite+pysqlite:///{tmp_path / 'named.sqlite3'}"
    monkeypatch.chdir(tmp_path)

    assert Database(named).database_url == make_url(named)
    assert DEFAULT_STORE_FILE not in str(Database(named).database_url)


def test_a_url_handed_to_one_is_the_database_it_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A `Database` is told which one it is, and told nothing is the file in the working directory.

    It reads no environment variable to find out: the one way to name a database is to hand one
    over, so there is one seam and a test does not have to arrange the world to be heard.
    """
    monkeypatch.chdir(tmp_path)
    handed = f"sqlite+pysqlite:///{tmp_path / 'handed.sqlite3'}"

    assert Database(handed).database_url == make_url(handed)
    assert DEFAULT_STORE_FILE in str(Database("").database_url)
    assert DEFAULT_STORE_FILE in str(Database().database_url)


def test_a_session_is_handed_out_with_this_task_s_tables_already_made(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nothing is asked to run a command first, and nothing is asked to have started up first.

    `create_engine` does not connect, so a database is only ever *named* until something reads it.
    Making the tables on the way to a session is what lets the one that finds them gone -- deleted,
    restored from a copy, cleared by a suite run beside the service -- make them again and carry on,
    rather than answering the caller with a fault it can do nothing about.
    """
    store = tmp_path / "made.sqlite3"
    attach(monkeypatch, f"sqlite+pysqlite:///{store}")

    with db.open_session() as session:
        assert session.query(ToolDecisionRecord).count() == 0
    assert store.exists()

    store.unlink()

    with db.open_session() as again:
        assert again.query(ToolDecisionRecord).count() == 0
    assert store.exists()


def test_a_database_held_in_memory_is_not_a_file_that_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`:memory:` names no path, so looking for one on disk finds nothing there — every time.

    What that mistake costs is the whole database, and quietly: dropping the pool is what makes the
    next connection open the name afresh, and for an in-memory store a fresh connection *is* a
    fresh, empty database. So the row written a moment ago would simply not be there.

    A server dialect answers the same way for the same reason: it holds no file, so there is no
    file to find missing, and asking after one would drop its pool on every session.
    """
    assert Database("sqlite+pysqlite:///:memory:").check_database_exists() is True
    assert Database("sqlite://").check_database_exists() is True
    assert (
        Database(
            "postgresql+psycopg://user:pw@nosuchhost.invalid/db"
        ).check_database_exists()
        is True
    )
    named = tmp_path / "never.sqlite3"
    assert Database(f"sqlite+pysqlite:///{named}").check_database_exists() is False

    attach(monkeypatch, "sqlite+pysqlite:///:memory:")
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
        assert reading.get(ToolDecisionRecord, key) is not None


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
    attach(
        monkeypatch,
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
    attach(monkeypatch, f"sqlite+pysqlite:///{first_path}")
    first = db.open_engine()
    pool = first.pool

    attach(monkeypatch, f"sqlite+pysqlite:///{second_path}")
    second = db.open_engine()

    assert second is not first
    assert first.pool is not pool


def test_one_metadata_holds_every_task_s_tables() -> None:
    """What `Base` being shared buys: a profile declares its own tables and one `MetaData` knows
    them, which is what lets `create_all` name a task's two rather than reach for a registry."""
    assert issubclass(ToolDecisionRecord, Base)
    assert issubclass(ToolDecisionSample, Base)
    assert {
        ToolDecisionRecord.__tablename__,
        ToolDecisionSample.__tablename__,
    } <= set(Base.metadata.tables)
