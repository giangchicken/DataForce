"""adapter · one row per record, and the two calls that read and write it.

One table, keyed by the record's own id, holding the row as JSON and the time it landed. A record
posted twice is one record reviewed twice, so a second post replaces the row through
`Session.merge` -- a read by primary key then an insert or an update, which is why no
dialect-specific `insert` is reached for and why SQLite and Postgres are one adapter with two DSNs.

The cost of replacing, stated: the review the row used to hold is gone, with no trace it existed.

`document` is one JSON column rather than a column per part. The record's envelope is declared
nowhere but at the boundary that receives it, and a relational schema for it would make this table
that declaration -- in the layer furthest from where the record is built. A column is added when a
query needs one, and `E-1`'s known gap is why fewer of them is worth having: schema coupling never
shows up in the import graph.
"""

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Long enough for a digest-shaped id, short enough that a dialect with a length limit indexes it.
ID_LENGTH = 64

# The default is a file, for a developer who attached no database. A deployment names its own and
# never lands here -- `.gitignore` keeps the file out of the repository for that reason.
DATABASE_URL = "DATAFORCE_DATABASE_URL"
DEFAULT_DATABASE_URL = "sqlite+pysqlite:///dataforce.sqlite3"


class Base(DeclarativeBase):
    pass


class Record(Base):
    """One reviewed record, as the review left it."""

    __tablename__ = "record"

    record_id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def database_url() -> str:
    """Where the store is, or the developer's file where a deployment named nothing."""
    return os.environ.get(DATABASE_URL) or DEFAULT_DATABASE_URL


def open_session() -> Session:
    """One session against the declared database. The caller closes it."""
    return Session(create_engine(database_url(), future=True))


def stored_row(record_id: str, document: Mapping[str, Any]) -> Mapping[str, Any]:
    """The row as it landed. A second post under one id replaces the first."""
    landed = datetime.now(UTC)
    with open_session() as session:
        session.merge(
            Record(record_id=record_id, document=dict(document), stored_at=landed)
        )
        session.commit()
    return {"record_id": record_id, "stored_at": landed}


def latest_row(record_id: str) -> Mapping[str, Any] | None:
    """The document stored under one id, or None where nothing is."""
    with open_session() as session:
        found = session.get(Record, record_id)
        return dict(found.document) if found is not None else None
