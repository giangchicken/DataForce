"""wiring · create_app(): the config resolver, one router, the app's own route, and the UI.

The labelling UI is mounted here and nowhere else. `wiring` is the one layer allowed to know both
the API and the thing that calls it, and one process serving both is what lets a labeller open a
URL and start with nothing installed but the service (Decision 22).
"""

import logging
from pathlib import Path

from agent_toolkit.logging import configure_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .events import structured_events
from .routers import tool_decision_router
from .served_models import register_resolver

# Inside the package, because `[tool.hatch.build.targets.wheel]` ships every file under
# `src/dataforce` and nothing beside it -- a UI at `src/ui/` would be missing from an install.
UI = Path(__file__).resolve().parent.parent / "ui"


def create_app(*, cors_origins: tuple[str, ...] = ("*",)) -> FastAPI:
    """The app: one task's router, and the route that answers for the app itself."""
    # The library's own records to stderr, as it formats them; this codebase's to stdout as
    # events (`H-6`).
    configure_logging(level=logging.INFO)
    structured_events(level=logging.INFO)
    register_resolver()
    app = FastAPI(
        title="DataForce",
        summary="the parts of a labelling process, each reachable on its own",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", summary="is the process up")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(tool_decision_router)
    # `html=True` so `/ui/` answers the directory's `index.html`; the three files are served as
    # they are written, because there is no build step to serve the output of (Decision 22).
    app.mount("/ui", StaticFiles(directory=UI, html=True), name="ui")
    return app


app = create_app()
