"""facade · one router per task."""

from .tool_decision import router as tool_decision_router

__all__ = ["tool_decision_router"]
