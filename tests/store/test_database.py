"""`edge/database.py` -- what *no database* answers, and what one engine for the process means.

**No database attached is a state**, not a failure: the labelling flow works with nothing behind
it, so `open_session()` answers `None` for the unset, the empty and the whitespace spellings, all
three of which a compose file produces.

**A time is stored as it was written.** Nothing converts, on either dialect, so what a row holds is
this deployment's own clock and not an instant anybody can place from the value alone. That is the
cost of having no `TypeDecorator` here, and it is the trade this store took on purpose.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest
from sqlalchemy import Engine

from dataforce.edge.database import Base, db
from dataforce.profile.tool_decision.schema import (
    ToolDecisionDataset,
    ToolDecisionRecord,
    create_tables,
)

WROTE_AT = datetime(2026, 9, 16, 15, 30, 45)

THREADS = 8


@pytest.mark.parametrize(
    "declared", [None, "", "   "], ids=["unset", "empty", "whitespace"]
)
def test_an_undeclared_dsn_is_a_state_and_nothing_raises(
    declared: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The state § *The page* requires: all eight steps work with no store behind them.

    Whitespace among them, because a variable set to a blank line in a compose file is the same
    absence as an unset one and must not be read as a DSN somewhere further away.
    """
    if declared is None:
        monkeypatch.delenv("DATAFORCE_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATAFORCE_DATABASE_URL", declared)

    assert db.open_engine() is None
    assert db.open_session() is None


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
    assert issubclass(ToolDecisionDataset, Base)
    assert {
        ToolDecisionRecord.__tablename__,
        ToolDecisionDataset.__tablename__,
    } <= set(Base.metadata.tables)
