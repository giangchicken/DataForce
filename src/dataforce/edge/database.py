"""adapter · the DSN, the engine, the session, and the one write every task makes.

**No table is declared here, and neither is the base.** Which tables exist is the profile's, and
each profile's own `schema.py` hangs them off the `Base` in `dataforce/tables.py` -- a `shape`,
which is what lets those files stay shapes too. There are no migrations:
`create_all` only ever *creates*, so changing a column on a database that already holds rows is a
statement somebody writes by hand.

**Unset means a SQLite file in the working directory**, made on first use, so a deployment that
configured nothing still has somewhere to put a row. A DSN that is set wins, which is how Postgres
arrives. *No store* is still a state every caller handles -- `open_session()` answers `None` and
nothing raises -- and it is reached by setting the variable to `off`, because the labelling flow
works with nothing attached and a state nothing can reach is a state nothing tests.

The default is resolved against the working directory rather than against this file: a checkout is
what this tool is run from, and `.gitignore` already names that file at the root. The cost, stated:
started from two different directories it is two different corpora, so a deployment that cannot
promise its working directory names the DSN.

**No table is made here, and none is declared here.** Which tables exist is the profile's, and
making them is the app's -- `create_app` does it once at startup, which is what lets an
unconfigured install accept the first record without anyone running a command. Doing it on the way
to an engine would make it impossible to open one and find the database as it really is, which is
what the store's own suite is for.

**Times are this deployment's own, written naive.** No conversion on the way in or out, so both
dialects hand back the value they were given. The cost is that a row's instant is only readable by
someone who knows where the deployment runs; UTC is the change to make the day a second region
reads the same corpus, and not before.
"""

import os
from pathlib import Path
from threading import Lock

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# The one variable a deployment names its database in. Read here and nowhere else.
DSN_VARIABLE = "DATAFORCE_DATABASE_URL"

# What the variable is set to for *no store at all*. One spelling, matched without case, because
# this is the state the review runs in and a deployment turning the store off should not have to
# guess whether it wanted `off`, `none` or an empty string -- empty is the default now.
NO_STORE = "off"

# The file an unconfigured deployment gets, relative to the working directory.
DEFAULT_STORE_FILE = "dataforce.sqlite3"


class Database:
    """Whatever the DSN names, or nothing at all -- one engine for the process, and a session.

    The lock and the cache are the whole of the state, which is why they are here rather than
    three module globals: FastAPI runs a sync handler in the anyio worker threadpool, so several
    requests enter a cold cache at once, and without the lock each builds an engine and every one
    but the last leaks its pool.
    """

    def __init__(self, variable: str) -> None:
        self.variable = variable
        self.lock = Lock()
        self.engines: dict[str, Engine] = {}

    def read_url(self) -> str | None:
        """The DSN this process should use, or `None` where the store is turned off.

        Whitespace is nothing declared: a variable set to a blank line in a compose file is the
        same absence as an unset one, and both mean the default file rather than no store.
        """
        declared = os.environ.get(self.variable, "").strip()
        if declared.lower() == NO_STORE:
            return None
        if not declared:
            return f"sqlite+pysqlite:///{Path.cwd() / DEFAULT_STORE_FILE}"
        return declared

    def open_engine(self) -> Engine | None:
        """One engine for the process, built on first use. `None` where the store is turned off.

        A DSN that has changed releases the pool the old one held, which is what makes the cache
        safe for a test pointing at a new file per case.
        """
        url = self.read_url()
        if url is None:
            return None
        with self.lock:
            built = self.engines.get(url)
            if built is None:
                for stale in self.engines.values():
                    stale.dispose()
                self.engines.clear()
                built = create_engine(url)
                self.engines[url] = built
            return built

    def describe(self) -> str | None:
        """Which database this is, in words safe to put on a screen. `None` where there is none.

        **Never the DSN.** A connection string carries a password, and this is read by a route any
        viewer of the page can call -- so what comes back is the dialect, the host and the database
        name, and nothing that would let a reader connect. The user is left out too: it is not
        needed to answer *am I writing where I think I am*, which is the whole of the question.

        A SQLite file is named by its file name alone, because that is what a person recognises,
        and the path it sits in is the working directory this process was started from.
        """
        url = self.read_url()
        if url is None:
            return None
        named = make_url(url)
        if named.get_backend_name() == "sqlite":
            return Path(named.database or ":memory:").name
        where = f"{named.host or 'local'}/{named.database or '?'}"
        return f"{named.get_backend_name()} · {where}"

    def open_session(self) -> Session | None:
        """A session on the declared database, or `None` where the store is turned off.

        `None` is an answer every caller handles and not a failure: the store is a place to put
        the result of a review, never a dependency of one.
        """
        engine = self.open_engine()
        if engine is None:
            return None
        return Session(engine)


db = Database(DSN_VARIABLE)


def merge_rows(session: Session, *rows: object) -> None:
    """Every row merged and committed together, or none of them written at all.

    Here and not in each profile because every task makes this same write and the rule it has to
    obey is not the task's: rows that belong to one another go in one transaction, and a failure on
    the last must leave none of the earlier ones behind. A task writing its own loop is a second
    place that can forget the commit, or forget the rollback.

    `merge` and never a dialect's upsert -- a read by primary key, then an insert or an update -- so
    one statement is written for both DSNs and a developer's SQLite file behaves like a
    deployment's Postgres. The whole row is replaced, so a caller carrying a column forward
    (a `created_time` that must not move) reads it before calling this.

    The transaction is the session's own: opened by the first statement and ended here, so anything
    else left uncommitted on that session commits with these. Hand it a session of its own.
    """
    for row in rows:
        session.merge(row)
    session.commit()
