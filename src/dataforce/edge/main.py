"""wiring · create_app(): the config resolver, one router, the app's own route, and the UI.

The labelling UI is mounted here and nowhere else. `wiring` is the one layer allowed to know both
the API and the thing that calls it, and one process serving both is what lets a labeller open a
URL and start with nothing installed but the service.

**The tables are made here, at startup.** This is the only layer that has both the engine and every
profile's tables in front of it -- importing the router is what registers them on `Base` -- and
doing it at startup rather than on the way to an engine is what leaves `edge/database.py` able to
open one and find the database as it really is. `create_all` only ever *creates*, so it is safe to
run against a database that already holds rows, and it is what makes an install nobody configured
able to take the first record.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from agent_toolkit.logging import configure_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dataforce.tables import Base

from .database import db
from .events import install_structured_events
from .routers import tool_decision_router
from .served_models import register_resolver

# Inside the package, because `[tool.hatch.build.targets.wheel]` ships every file under
# `src/dataforce` and nothing beside it -- a UI at `src/ui/` would be missing from an install.
UI = Path(__file__).resolve().parent.parent / "ui"


@asynccontextmanager
async def make_tables(app: FastAPI) -> AsyncIterator[None]:
    """Every declared table, made on the attached database before the first request.

    Nothing happens where the store is turned off, which is the state the review runs in: the
    labelling flow works with nowhere to put the result, so a startup that cannot reach a database
    is not a startup that should fail.
    """
    engine = db.open_engine()
    if engine is not None:
        Base.metadata.create_all(engine)
    yield


def create_app(*, cors_origins: tuple[str, ...] = ("*",)) -> FastAPI:
    """The app: one task's router, and the route that answers for the app itself."""

    configure_logging(level=logging.INFO)
    install_structured_events(level=logging.INFO)
    register_resolver()
    app = FastAPI(
        title="DataForce",
        summary="the parts of a labelling process, each reachable on its own",
        lifespan=make_tables,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", summary="is the process up")
    def get_health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(tool_decision_router)

    app.mount("/ui", StaticFiles(directory=UI, html=True), name="ui")
    return app


app = create_app()
