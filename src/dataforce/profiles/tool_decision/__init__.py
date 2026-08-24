"""façade · the tool_decision profile; its shapes are schema.py and its conversions utils.py.

What a composition root needs to register this profile, and nothing else. The shapes in `schema.py`
are not re-exported: a stage reads a `LabelCheck` or an `AnswerConfig` structurally because
`pipeline/` may not import this package at all (I2), and forwarding them would make that import
look permitted.
"""

from dataforce.profiles.tool_decision.utils import ToolDecision

__all__ = ["ToolDecision"]
