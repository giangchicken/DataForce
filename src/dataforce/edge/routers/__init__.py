"""façade · one router per endpoint."""

from .ai_review import router as ai_review_router
from .data_quality import router as data_quality_router
from .text2text.tool_decision import router as human_review_router

__all__ = ["ai_review_router", "data_quality_router", "human_review_router"]
