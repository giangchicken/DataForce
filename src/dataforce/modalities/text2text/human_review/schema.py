"""DEFINITION · what an annotation says, and what the label ends as."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ai_review.schema import LLMReviewerVerdict, SFTReviewerVerdict

type Answer = tuple[Any, ...]

# What happened to the label. `unvalidated` is not `original`: one means people looked and the
# label survived, the other means nobody looked. Collapsing them makes the one number this
# service exists to produce — how much of the corpus a human validated — unreadable.
type Status = Literal["original", "corrected", "unresolved", "unvalidated"]


class Annotation(BaseModel):
    """One person's answer about one sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    annotator_id: str = Field(..., description="Who answered.")
    verdict: str | None = Field(
        ...,
        description=(
            "Which of the offered verdicts they chose. None where the annotation "
            "chose none — there is no answer to record."
        ),
    )
    corrected_label: Answer | None = Field(
        default=None,
        description=(
            "What they proposed instead. None both where they proposed nothing and "
            "where what they proposed did not parse, so a verdict of *wrong* does "
            "not guarantee one."
        ),
    )
    note: str | None = Field(default=None, description="Free text; never parsed.")
    submitted_at: datetime = Field(..., description="When they submitted it.")


class Evidence(BaseModel):
    """Everything the decision is allowed to read. What a custom rule is handed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Answer = Field(
        default=(),
        description="The label the sample arrived with; the thing in question.",
    )
    annotations: tuple[Annotation, ...] = Field(
        default=(), description="One per person, already folded to their latest answer."
    )
    panel: LLMReviewerVerdict | None = Field(
        default=None, description="What the LLM panel said, where it ran."
    )
    sft: SFTReviewerVerdict | None = Field(
        default=None, description="What the finetuned reviewer said, where it ran."
    )
    endorsing_verdict: str = Field(
        default="correct",
        description=(
            "Which verdict value means *the label as it stands is right*. A parameter "
            "because the wording belongs to whoever wrote the question."
        ),
    )


class LabelDecision(BaseModel):
    """The label that ships, and how it was decided."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Status = Field(
        ..., description="Whether people looked, and what they concluded."
    )
    label: Answer = Field(
        default=(), description="The final label. This is what ships."
    )
    confidence: float = Field(
        ...,
        description="How much the people who looked agreed, 0 to 1. 0.0 where nobody did.",
    )
    validators: tuple[str, ...] = Field(
        default=(), description="Who decided it. Empty where nobody did."
    )
    decided_at: datetime | None = Field(
        default=None,
        description=(
            "The last annotator's clock, not this module's. None where nobody "
            "answered — there is no honest value to invent."
        ),
    )


@dataclass(frozen=True)
class ReturnedAnnotation:
    """One person's answer as the annotation tool holds it, before it is read as a verdict."""

    annotation_id: str
    task_id: str
    annotator_id: str
    result: tuple[Mapping[str, Any], ...]  # the control values, verbatim
    was_skipped: bool
    submitted_at: str
