"""ADAPTER · tasks out, annotations back, idempotent in both directions.

Label Studio is the store. It already holds tasks and annotations, so nothing here keeps a second
copy — idempotence comes from asking the project what it has rather than from a table of our own.
"""

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from dataforce.modalities.text2text.human_review.schema import (
    Annotation,
    ReturnedAnnotation,
)

# The one payload key a task is found by again. A task carrying it is a task we posted.
SAMPLE_ID = "sample_id"


class SyncCounts(BaseModel):
    """What one push came to."""

    posted: int = Field(..., description="Tasks the project did not already hold.")
    already_held: int = Field(..., description="Tasks it did, so nothing was posted.")
    task_ids: dict[str, str] = Field(
        default_factory=dict, description="The tool's task id, by `sample_id`."
    )


def client() -> Any:
    """The Label Studio client this deployment declared.

    The import is here rather than at the top: `label-studio-sdk` is an extra, and importing it at
    module load would make an install without it fail at startup rather than at this one route.
    """
    try:
        from label_studio_sdk.client import LabelStudio
    except ImportError as missing:
        raise RuntimeError(
            "label-studio-sdk is not installed; it is the extra this route needs"
        ) from missing
    url = os.environ.get("LABEL_STUDIO_URL", "")
    key = os.environ.get("LABEL_STUDIO_API_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "LABEL_STUDIO_URL and LABEL_STUDIO_API_KEY name the instance and the key; "
            "neither is defaulted, because a default would post transcripts somewhere nobody chose"
        )
    return LabelStudio(base_url=url, api_key=key)  # type: ignore[no-untyped-call]


def held_by(tool: Any, project_id: str) -> dict[str, str]:
    """The task id the project already holds, by `sample_id`. What makes a re-push a no-op."""
    held: dict[str, str] = {}
    for task in tool.tasks.list(project=int(project_id)):
        data = getattr(task, "data", None) or {}
        sample_id = data.get(SAMPLE_ID)
        if sample_id:
            held[str(sample_id)] = str(task.id)
    return held


def published(project_id: str, samples: Sequence[Mapping[str, Any]]) -> SyncCounts:
    """Post every sample the project does not already hold, and report both counts."""
    tool = client()
    held = held_by(tool, project_id)
    posted = 0
    for sample in samples:
        sample_id = str(sample[SAMPLE_ID])
        if sample_id in held:
            continue
        created = tool.tasks.create(project=int(project_id), data=dict(sample))
        held[sample_id] = str(created.id)
        posted += 1
    return SyncCounts(posted=posted, already_held=len(samples) - posted, task_ids=held)


def returned(tool: Any, task_id: str) -> list[ReturnedAnnotation]:
    """Every annotation the tool holds on one task, as this package's own small value."""
    return [
        ReturnedAnnotation(
            annotation_id=str(one.id),
            task_id=str(task_id),
            annotator_id=str(getattr(one, "completed_by", "") or ""),
            result=tuple(getattr(one, "result", ()) or ()),
            was_skipped=bool(getattr(one, "was_cancelled", False)),
            submitted_at=str(getattr(one, "updated_at", "") or ""),
        )
        for one in tool.annotations.list(int(task_id))
    ]


def submitted(stamp: str) -> datetime:
    """The tool's clock, or now where it reported none. No part of this service holds one."""
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return datetime.now(UTC)


def as_annotation(returned_one: ReturnedAnnotation) -> Annotation | None:
    """One returned annotation as a verdict, a correction and a note.

    **The only place the annotation tool's control shape is read.** A skipped annotation is not a
    verdict and comes back as None: the person saw it and declined, which is a different fact from
    an answer.
    """
    if returned_one.was_skipped:
        return None
    values: dict[str, Any] = {}
    for control in returned_one.result:
        name = str(control.get("from_name", ""))
        value = control.get("value", {})
        if isinstance(value, Mapping):
            picked = value.get("choices") or value.get("text")
            values[name] = picked[0] if isinstance(picked, list) and picked else picked
    correction = values.get("corrected_label")
    return Annotation(
        annotator_id=returned_one.annotator_id,
        verdict=values.get("verdict"),
        corrected_label=tuple(correction) if isinstance(correction, list) else None,
        note=values.get("note"),
        submitted_at=submitted(returned_one.submitted_at),
    )


def annotations_for(project_id: str) -> dict[str, list[Annotation]]:
    """Every annotation the project holds, by `sample_id`."""
    tool = client()
    answers: dict[str, list[Annotation]] = {}
    for sample_id, task_id in held_by(tool, project_id).items():
        read = [as_annotation(one) for one in returned(tool, task_id)]
        answers[sample_id] = [one for one in read if one is not None]
    return answers
