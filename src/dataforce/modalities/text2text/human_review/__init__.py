"""facade · the label that ships."""

from .decision_logic import DecisionLogic, MajorityDecision
from .schema import Annotation, Evidence, LabelDecision

__all__ = [
    "Annotation",
    "DecisionLogic",
    "Evidence",
    "LabelDecision",
    "MajorityDecision",
]
