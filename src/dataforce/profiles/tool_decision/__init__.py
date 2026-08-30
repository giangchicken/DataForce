"""façade · the tool_decision profile; the object a composition root registers.

What a composition root needs to register this profile, and nothing else. The shapes in `schema.py`
are not re-exported: a stage reads a `LabelCheck` or an `AnswerConfig` structurally because
`pipeline/` may not import this package at all (I2), and forwarding them would make that import
look permitted.

The modules beside `schema.py` are named for what they produce -- `answers.py`, `annotations.py`,
`records.py`, `profile.py` -- and none of them is a name anything above this line needs.
"""

from dataforce.profiles.tool_decision.profile import ToolDecision

__all__ = ["ToolDecision"]
