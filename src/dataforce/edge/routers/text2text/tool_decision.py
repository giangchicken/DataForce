"""ADAPTER · one APIRouter for tool_decision: a request body in, one part's answer out.

A handler is thin. It reads the body, calls one function in `services/tool_decision/`, and maps the
error; it names no stage sequence, and no response carries a part the handler does not own. The
record the store is posted is validated here, at the one boundary an outside body becomes a domain
value.

Which models answer is the caller's choice, not a declaration: `GET /models` lists what this
deployment serves, and each request names the ones it wants. A name with no config file is refused
before any model is called.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from dataforce.edge.served_models import served_models
from dataforce.edge.store import stored_row
from dataforce.errors import ConfigError
from dataforce.modalities.text2text.ai_review import (
    LLMReviewerVerdict,
    SFTReviewerVerdict,
)
from dataforce.modalities.text2text.ai_review.schema import (
    LLMModelConfig,
    SFTModelConfig,
)
from dataforce.modalities.text2text.data_quality import PersonalDataScan
from dataforce.modalities.text2text.data_quality.schema import VerifierModelConfig
from dataforce.services.tool_decision import (
    abnormal_report,
    duplicate_report,
    panel_verdict,
    personal_data_scan,
    reviewer_verdict,
    stored_record,
)

router = APIRouter(prefix="/text2text/tool-decision", tags=["tool_decision"])

PAGE = Path(__file__).resolve().parents[2] / "static" / "index.html"


class Sample(BaseModel):
    """One tool-calling sample, as it is posted.

    `extra="allow"` because a corpus carries keys this service does not read, and dropping them
    would make the stored row a lossy copy of what arrived.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="What the sample is called; the store's key.")
    messages: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The conversation, in order."
    )
    tools: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The tools the assistant was allowed to call."
    )
    label: Any = Field(
        default=None, description="The tool calls someone already assigned."
    )


class ScanRequest(Sample):
    """A sample, and the model ticked for layer two.

    `verifier_model` and not `verifier`: a record's keys already say what each reviewer *said*, so
    a request key naming which one to *ask* must not read like the answer.
    """

    verifier_model: str = Field(
        ..., description="Which served model confirms layer one's candidates."
    )


class ReviewRequest(Sample):
    """A sample, and the models ticked. Named apart from `llm` and `sft`, which hold answers."""

    jury_models: tuple[str, ...] = Field(
        default=(),
        description="Which served models sit on the panel. Empty asks no panel.",
    )
    sft_model: str | None = Field(
        default=None,
        description="Which served model is the finetuned reviewer, if any.",
    )


class Record(Sample):
    """A sample and what the review made of it. The body the store is posted.

    `messages`, `tools` and `label` are what arrived. The three `new_` keys are what ships: the
    human's edits applied, then every confirmed value replaced. `new_tools` is None where the human
    left the catalog alone -- an unmodified catalog has no new version to carry.
    """

    new_messages: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The conversation that ships, edited and redacted."
    )
    new_tools: tuple[Mapping[str, Any], ...] | None = Field(
        default=None,
        description="The catalog that ships, or None where it was not modified.",
    )
    new_label: Any = Field(
        default=None, description="The label that ships, edited and redacted."
    )
    personal_data: Mapping[str, Any] | None = Field(default=None)
    duplicate: None = Field(default=None)
    abnormal: None = Field(default=None)
    llm: Mapping[str, Any] | None = Field(default=None)
    sft: Mapping[str, Any] | None = Field(default=None)


class ReviewerVerdicts(BaseModel):
    """What each reviewer said. None where the request ticked no such model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm: LLMReviewerVerdict | None = Field(default=None)
    sft: SFTReviewerVerdict | None = Field(default=None)


class Stored(BaseModel):
    """What one row came to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str
    stored_at: Any


def refused(error: ConfigError) -> HTTPException:
    """A declaration this service cannot act on, as the status that says so."""
    return HTTPException(status_code=422, detail=str(error))


def checked_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """The names, once every one of them is a model this deployment serves.

    Raises `ConfigError` naming the ones that are not, before any model is called, so a caller
    learns which name was wrong rather than that something failed.
    """
    served = served_models()
    unserved = tuple(name for name in names if name not in served)
    if unserved:
        raise ConfigError(
            f"not served here: {', '.join(unserved)}. Served: {', '.join(served) or 'nothing'}"
        )
    return names


@router.get("/", summary="the flow, as a page", response_class=FileResponse)
def page() -> FileResponse:
    return FileResponse(PAGE, media_type="text/html")


@router.get("/models", summary="which models this deployment serves")
def models() -> tuple[str, ...]:
    return served_models()


@router.post("/data-quality/personal-data", summary="personal data in one sample")
async def personal_data(request: ScanRequest) -> PersonalDataScan | None:
    """`None` for as long as `scan` has a `pass` body. The type tightens when the body lands."""
    try:
        checked_names((request.verifier_model,))
        return await personal_data_scan(
            VerifierModelConfig(model=request.verifier_model), request.model_dump()
        )
    except ConfigError as error:
        raise refused(error) from error


@router.post("/data-quality/duplicate", summary="which samples this one repeats")
async def duplicate(sample: Sample) -> None:
    return await duplicate_report(sample.model_dump())


@router.post(
    "/data-quality/abnormal", summary="what the checks needing no opinion found"
)
async def abnormal(sample: Sample) -> None:
    return await abnormal_report(sample.model_dump())


@router.post("/ai-review", summary="what the reviewers say the label should be")
async def ai_review(request: ReviewRequest) -> ReviewerVerdicts:
    body = request.model_dump()
    try:
        checked_names(
            request.jury_models + ((request.sft_model,) if request.sft_model else ())
        )
        return ReviewerVerdicts(
            llm=await panel_verdict(
                [LLMModelConfig(model=name) for name in request.jury_models] or None,
                body,
            ),
            sft=await reviewer_verdict(
                SFTModelConfig(model=request.sft_model) if request.sft_model else None,
                body,
            ),
        )
    except ConfigError as error:
        raise refused(error) from error


@router.post("/records", summary="store one reviewed record")
def records(record: Record) -> Stored:
    try:
        return Stored(**stored_record(record.model_dump(), write=stored_row))
    except ConfigError as error:
        raise refused(error) from error
