"""TOOL · create_app(), and one include_router per endpoint."""

import logging

from agent_toolkit.logging import configure_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ai_review_router, data_quality_router, human_review_router


def create_app(*, cors_origins: tuple[str, ...] = ("*",)) -> FastAPI:
    """The app: three endpoints, and the two routes that answer for the app itself."""
    configure_logging(level=logging.INFO)
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

    for router in (data_quality_router, ai_review_router, human_review_router):
        app.include_router(router)
    return app


app = create_app()
