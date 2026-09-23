"""adapter · the database this deployment writes to, what it answers the edge, and the one write
every task makes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from agent_toolkit.logging import get_logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from dataforce.tables import Base

logger = get_logger(__name__)

DEFAULT_STORE_FILE = "dataforce.sqlite3"


class Database:
    def __init__(self, database_url: str | None = None) -> None:
        declared = (database_url or "").strip()
        self.database_url = make_url(
            declared or f"sqlite+pysqlite:///{Path.cwd() / DEFAULT_STORE_FILE}"
        )
        self.lock = Lock()
        self.engine: Engine | None = None
        self.built: URL | None = None

    def describe(self) -> str:
        dialect = self.database_url.get_backend_name()
        held = self.database_url.database
        if dialect == "sqlite":
            return Path(held or ":memory:").name
        return f"{dialect} · {self.database_url.host or 'local'}/{held or '?'}"

    def check_database_exists(self) -> bool:
        held = self.database_url.database
        if self.database_url.get_backend_name() != "sqlite" or held in (
            None,
            ":memory:",
        ):
            return True
        return Path(str(held)).exists()

    def open_engine(self) -> Engine:
        with self.lock:
            if self.engine is None or self.built != self.database_url:
                if self.engine is not None:
                    self.engine.dispose()
                self.engine = create_engine(self.database_url)
                self.built = self.database_url
            return self.engine

    def check_url(self) -> None:
        engine = self.open_engine()
        if not self.check_database_exists():
            engine.dispose()
        Base.metadata.create_all(engine)

    def open_session(self) -> Session:
        self.check_url()
        return Session(self.open_engine())


db = Database()


@asynccontextmanager
async def check_database_on_startup(app: FastAPI) -> AsyncIterator[None]:
    try:
        db.check_url()
    except SQLAlchemyError as unreachable:
        logger.error(
            "store_unreachable",
            extra={
                "describes": db.describe(),
                "error": f"{type(unreachable).__name__}: {unreachable}",
            },
        )
    yield


def refuse_database_fault(request: Request, fault: Exception) -> JSONResponse:
    logger.error(
        "store_unusable",
        extra={
            "describes": db.describe(),
            "asked": request.url.path,
            "error": type(fault).__name__,
            "said": str(getattr(fault, "orig", "")),
        },
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                f"{db.describe()} did not answer. Its tables are made on the way in, so this is"
                " not a table that went missing: the database itself could not be reached, or will"
                " not let this service write."
            )
        },
    )


def merge_rows(session: Session, *rows: object) -> None:
    for row in rows:
        session.merge(row)
    session.commit()
