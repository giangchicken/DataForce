"""wiring · create_app(): the config resolver, one router, and the app's own route."""

import logging

from agent_toolkit.logging import configure_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import tool_decision_router
from .served_models import register_resolver


def create_app(*, cors_origins: tuple[str, ...] = ("*",)) -> FastAPI:
    """The app: one task's router, and the route that answers for the app itself."""
    configure_logging(level=logging.INFO)
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
    return app


app = create_app()
