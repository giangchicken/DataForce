"""adapter · the DSN, the engine, the session, and the one write every task makes.

**No table is declared here, and neither is the base.** Which tables exist is the profile's, and
each profile's own `schema.py` hangs them off the `Base` in `dataforce/tables.py` -- a `shape`,
which is what lets those files stay shapes too. There are no migrations:
`create_all` only ever *creates*, so changing a column on a database that already holds rows is a
statement somebody writes by hand.

**There is no default DSN.** Unset or empty means *no store*: `open_session()` answers `None` and
nothing raises, because the labelling flow works with nothing attached and a fallback file would
make that state unreachable.

**Times are this deployment's own, written naive.** No conversion on the way in or out, so both
dialects hand back the value they were given. The cost is that a row's instant is only readable by
someone who knows where the deployment runs; UTC is the change to make the day a second region
reads the same corpus, and not before.
"""

import os
from threading import Lock

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

# The one variable a deployment names its database in. Read here and nowhere else.
DSN_VARIABLE = "DATAFORCE_DATABASE_URL"


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

    def open_engine(self) -> Engine | None:
        """One engine for the process, built on first use. `None` where no DSN is declared.

        Whitespace is nothing declared: a variable set to a blank line in a compose file is the
        same absence as an unset one. A DSN that has changed releases the pool the old one held,
        which is what makes the cache safe for a test pointing at a new file per case.
        """
        url = os.environ.get(self.variable, "").strip()
        if not url:
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

    def open_session(self) -> Session | None:
        """A session on the declared database, or `None` where there is none to open.

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
