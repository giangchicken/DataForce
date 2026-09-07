"""DEFINITION · what one person's answer says, in this package's words and the tool's."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

type Answer = tuple[Any, ...]


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


@dataclass(frozen=True)
class ReturnedAnnotation:
    """One person's answer as the annotation tool holds it, before it is read as a verdict."""

    annotation_id: str
    task_id: str
    annotator_id: str
    result: tuple[Mapping[str, Any], ...]  # the control values, verbatim
    was_skipped: bool
    submitted_at: str
