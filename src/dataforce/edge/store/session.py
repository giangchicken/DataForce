"""TOOL · the store's connection and its lifetime.

The DSN is read here and nowhere else, from ``DATAFORCE_DATABASE_URL`` (P25, Twelve-Factor III): a
backing service is a resource a deployment attaches, so the store's address is the environment's and
never a literal in a module. The default is a SQLite file in the working directory, which is
Decision 7's whole point -- ``make check`` needs no database server -- and it is a default and not a
substitute: the same tests run against Postgres under ``-m integration``, because SQLite and
Postgres disagree about exactly the constraints this schema leans on.

**One session per unit of work, not one per process.** ``sessions_to`` hands back a factory and the
adapter opens a transaction around each call, so a run of twenty thousand records does not hold one
transaction open across the whole of it and a process that dies mid-run loses no committed write
(P24). The factory is what the composition root passes; the connection pool underneath it belongs to
the SQLAlchemy engine and is shared.

``StoreEngine`` is SQLAlchemy's ``Engine``, aliased on import. There is a ``dataforce.engine.Engine``
and it is a different thing entirely -- one is a resolved axis pair with no I/O, and this one is a
connection pool.
"""

import os
from typing import Any

from sqlalchemy import Engine as StoreEngine
from sqlalchemy import create_engine, event, make_url
from sqlalchemy.orm import Session, sessionmaker

from dataforce.errors import ConfigError

# Where a deployment says which database. Absent is ordinary, which is what the default is for.
DATABASE_URL = "DATAFORCE_DATABASE_URL"

# A file beside the working directory, so a developer with no server has a store that survives a
# restart. `.gitignore` holds the name: a committed database is a corpus in the repository, and this
# one holds questions about real records.
DEFAULT_URL = "sqlite+pysqlite:///dataforce.sqlite3"

# The dialect that needs asking. SQLite has enforced foreign keys since 3.6.19 and ships with them
# *off* for backwards compatibility, so a schema whose integrity Postgres enforces is decoration in
# the default backend -- which is P26's classic violation and Decision 7's named risk, arriving in
# the one place a substitute is allowed to differ silently.
SQLITE = "sqlite"

# The other one, and the two together are what this store is written for (Decision 7). A list rather
# than an assumption because `repository.py` forks on the dialect to spell its `ON CONFLICT`: a third
# backend would reach that fork with nothing to do there. Read from the DSN when the pool is built,
# which is before any record (P23), and by parsing rather than by connecting -- naming a database
# nobody installed a driver for should say so, not fail importing the driver.
POSTGRES = "postgresql"
SUPPORTED = (SQLITE, POSTGRES)


def store_url() -> str:
    """The DSN this deployment attached, or the local SQLite file when it attached none."""
    return os.environ.get(DATABASE_URL) or DEFAULT_URL


def turn_on_foreign_keys(connection: Any, _record: Any) -> None:
    """Make SQLite enforce the foreign keys it was handed, on every connection it opens.

    Per connection and not per database: the pragma is connection state, so a pool that opens a
    second one gets an unenforced schema unless it is set again.
    """
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def store_engine(url: str | None = None) -> StoreEngine:
    """A connection pool over that DSN, or over the one the environment named.

    The parameter is what a test uses to point at a file in `tmp_path`, and what `make integration`
    uses to point at a real Postgres. Nothing else passes one: the composition root reads the
    environment, which is the one place a deployment's address is allowed to come from.
    """
    dsn = url or store_url()
    backend = make_url(dsn).get_backend_name()
    if backend not in SUPPORTED:
        raise ConfigError(
            f"{DATABASE_URL} names a {backend} database and this store is written for "
            f"{' and '.join(SUPPORTED)} (Decision 7); the schema leans on constraints "
            "the two of them have been tested against and a third has not"
        )
    engine = create_engine(dsn)
    if backend == SQLITE:
        event.listen(engine, "connect", turn_on_foreign_keys)
    return engine


def sessions_to(engine: StoreEngine) -> sessionmaker[Session]:
    """The factory a caller opens one transaction at a time from."""
    return sessionmaker(bind=engine)
