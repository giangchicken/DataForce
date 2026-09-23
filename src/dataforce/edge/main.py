"""wiring · create_app(): the config resolver, one router, the app's own route, and the UI."""

import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

import uvicorn
from agent_toolkit.logging import configure_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import DBAPIError
from starlette.responses import Response

from .database import check_database_on_startup, refuse_database_fault
from .events import install_structured_events
from .routers import tool_decision_router
from .served_models import register_resolver

UI = Path(__file__).resolve().parent.parent / "ui"


class RevalidatedFiles(StaticFiles):
    """The page, served so that a reload is a reload.

    `no-cache` is *ask before you use it*, not *do not keep it*: the browser still holds the file
    and still gets a `304` off the `ETag` `StaticFiles` already answers, so the cost is one
    conditional request per file. Without it a browser is free to serve an ES module out of its
    own cache for as long as its heuristic likes, and an edit to `ui/` is then a change nobody on
    the page can see -- which is a bug report about the page and a measurement about the cache.

    One override and not two: `file_response` is where the 304 is decided as well as the 200, so
    the header lands on whichever of them comes back.
    """

    def file_response(self, *taken: Any, **named: Any) -> Response:
        answer = super().file_response(*taken, **named)
        answer.headers["cache-control"] = "no-cache"
        return answer


DEFAULT_PORT = 8000


def create_app(*, cors_origins: tuple[str, ...] = ("*",)) -> FastAPI:
    """The app: one task's router, and the route that answers for the app itself."""

    configure_logging(level=logging.INFO)
    install_structured_events(level=logging.INFO)
    register_resolver()
    app = FastAPI(
        title="DataForce",
        summary="the parts of a labelling process, each reachable on its own",
        lifespan=check_database_on_startup,
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

    app.add_exception_handler(DBAPIError, refuse_database_fault)
    app.include_router(tool_decision_router)

    app.mount("/ui", RevalidatedFiles(directory=UI, html=True), name="ui")
    return app


app = create_app()


def serve() -> None:
    reading = ArgumentParser(
        prog="dataforce", description="Serve the labelling UI and its API."
    )
    reading.add_argument("--port", type=int, default=DEFAULT_PORT)
    reading.add_argument(
        "--reload",
        action="store_true",
        help="restart on a source change, while editing",
    )
    asked = reading.parse_args()
    uvicorn.run("dataforce.edge.main:app", port=asked.port, reload=asked.reload)
