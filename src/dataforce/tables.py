"""shape · the one declarative base every task's tables hang off.

Here and not beside the engine, because a base is a noun: it declares that one `MetaData` knows
every task's tables and nothing about where those tables are or how one is reached. That is what
lets each profile's `schema.py` stay a `shape` -- a file that names the columns and imports nothing
that opens anything.

`edge/database.py` holds the other half, which is all of the reaching: the DSN, the engine and the
session.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The one declarative base every task's tables hang off, so one `MetaData` knows them all."""
