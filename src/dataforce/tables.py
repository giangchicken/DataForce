"""shape · the one declarative base every task's tables hang off."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The one declarative base every task's tables hang off, so one `MetaData` knows them all."""
