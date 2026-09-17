"""adapter · the DSN, the engine, the session, and the one base every task's tables hang off.

**No table is declared here.** Which tables exist is the profile's, and each profile's own
`schema.py` hangs them off `Base`, so one `MetaData` knows them all. There are no migrations:
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
from sqlalchemy.orm import DeclarativeBase, Session

# The one variable a deployment names its database in. Read here and nowhere else.
DSN_VARIABLE = "DATAFORCE_DATABASE_URL"


class Base(DeclarativeBase):
    """The one declarative base every task's tables hang off, so one `MetaData` knows them all."""


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

    def cached_engine(self) -> Engine | None:
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
        engine = self.cached_engine()
        if engine is None:
            return None
        return Session(engine)


store = Database(DSN_VARIABLE)
