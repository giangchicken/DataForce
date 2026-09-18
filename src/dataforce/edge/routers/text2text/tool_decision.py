"""adapter · one APIRouter for tool_decision: a request body in, one part's answer out."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from dataforce.edge.database import db
from dataforce.edge.served_models import check_served_models, list_served_models
from dataforce.errors import ConfigError
from dataforce.modalities.text2text.ai_review import (
    LLMReviewerVerdict,
    SFTReviewerVerdict,
)
from dataforce.modalities.text2text.ai_review.schema import (
    LLMModelConfig,
    SFTModelConfig,
)
from dataforce.modalities.text2text.data_quality import (
    PersonalDataCheckingConfig,
    PersonalDataDetected,
    PersonalDataReplaced,
)
from dataforce.modalities.text2text.data_quality.schema import (
    Language,
    VerifierModelConfig,
)
from dataforce.modalities.text2text.dataset_management import StepNotRun
from dataforce.profile.tool_decision.sample_building import (
    ToolDecisionSampleBuilding,
    count_by_facet,
    count_by_pair,
    count_total_samples,
    merge_tool_decision_db,
    select_sample_contents,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionDatasetStatistics,
    ToolDecisionSample,
)
from dataforce.services.tool_decision import (
    build_dataset_statistics,
    detect_personal_data,
    predict_tool_decision_by_llm,
    predict_tool_decision_by_sft,
    redact_personal_data,
    replace_personal_data,
    report_abnormalities,
    report_duplicates,
)

router = APIRouter(prefix="/text2text/tool-decision", tags=["tool_decision"])

PAGE = Path(__file__).resolve().parents[2] / "static" / "index.html"


class Sample(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="What the sample is called.")
    messages: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The conversation, in order."
    )
    tools: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The tools the assistant was allowed to call."
    )
    label: Any = Field(
        default=None, description="The tool calls someone already assigned."
    )


class PersonalDataScanRequest(Sample):
    language: Language = Field(
        default="vi",
        description=(
            "What language the conversation is in; every rule scan and both model steps are "
            "handed it. `vi` is Vietnamese, which this corpus is in."
        ),
    )
    verifier_model: str = Field(
        ..., description="Which served model confirms layer one's candidates."
    )


class RedactRequest(Sample):
    detected: PersonalDataDetected = Field(
        ..., description="The spans as the reviewer left them, in the text they index."
    )


class ReviewRequest(Sample):
    language: Language = Field(
        default="vi",
        description=(
            "What language the conversation is in; the jurors' prompt is handed it. `vi` is "
            "Vietnamese, which this corpus is in."
        ),
    )
    jury_models: tuple[str, ...] = Field(
        default=(),
        description="Which served models sit on the panel. Empty asks no panel.",
    )
    sft_model: str | None = Field(
        default=None,
        description="Which served model is the finetuned reviewer, if any.",
    )


class ReviewedSample(Sample):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    label: tuple[Any, ...] | None = Field(
        default=None, description="The tool calls someone already assigned."
    )
    new_messages: tuple[Mapping[str, Any], ...] | None = Field(
        default=None, description="The conversation as it ships, redaction included."
    )
    new_tools: tuple[Mapping[str, Any], ...] | None = Field(
        default=None,
        description="The catalog as it ships, where a new version was made.",
    )
    new_label: tuple[Any, ...] | None = Field(
        default=None, description="The calls as they ship."
    )
    personal_data: Mapping[str, Any] | None = Field(
        default=None,
        description=(
            "What step 2 found and step 5 replaced, as one object. `null` is nobody having "
            "scanned it, which is the refusal § *The precondition* names first."
        ),
    )
    duplicate: Any = Field(default=None, description="What step 3 answered.")
    abnormal: Any = Field(default=None, description="What step 4 answered.")
    llm: Mapping[str, Any] | None = Field(
        default=None, description="What the jury said, where one was asked."
    )
    sft: Mapping[str, Any] | None = Field(
        default=None,
        description="What the finetuned reviewer said, where one was asked.",
    )
    declared_facets: Mapping[str, Any] = Field(
        default_factory=dict,
        alias="class",
        description=(
            "The **declared** facets only, as the reviewer ticked them: a person's claims are "
            "part of what the review answered and there is nowhere else for them to arrive. "
            "The derived ones are computed at write time and are never posted."
        ),
    )


class RecordStored(BaseModel):
    """What the route says once a record has landed in both tables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        ...,
        description=(
            "The key both tables took, derived from the posted `id` so that the same name "
            "posted twice replaces one sample rather than making a second."
        ),
    )
    created_time: datetime = Field(
        ..., description="When this sample was first stored. It never moves."
    )
    modified_time: datetime = Field(
        ...,
        description=(
            "When this write happened. Equal to `created_time` on a first post, later on "
            "every repost -- which is how the page can say landed or replaced."
        ),
    )


class ReviewerVerdicts(BaseModel):
    """What each reviewer said. None where the request ticked no such model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm: LLMReviewerVerdict | None = Field(default=None)
    sft: SFTReviewerVerdict | None = Field(default=None)


@router.get("/", summary="the flow, as a page", response_class=FileResponse)
def get_page() -> FileResponse:
    return FileResponse(PAGE, media_type="text/html")


@router.get("/models", summary="which models this deployment serves")
def get_models() -> tuple[str, ...]:
    return list_served_models()


@router.post("/data-quality/personal-data", summary="personal data in one sample")
async def post_personal_data(request: PersonalDataScanRequest) -> PersonalDataDetected:
    """What was found, or 422 where no model resolved or the language is not one it can scan.

    `language` and `verifier_model` are declarations about this request and not keys of the
    record, so the sample handed on is what the corpus carries.
    """
    try:
        check_served_models((request.verifier_model,))
        return await detect_personal_data(
            PersonalDataCheckingConfig(
                verifier_model=VerifierModelConfig(model=request.verifier_model)
            ),
            request.model_dump(exclude={"language", "verifier_model"}),
            request.language,
        )
    except ConfigError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/data-quality/personal-data/replace", summary="replace the spans a reviewer left"
)
def post_personal_data_replacement(
    detected: PersonalDataDetected,
) -> PersonalDataReplaced:
    return replace_personal_data(detected)


@router.post(
    "/data-quality/personal-data/redact",
    summary="the sample with every handed-back span's value replaced",
)
def post_personal_data_redaction(request: RedactRequest) -> dict[str, Any]:
    return redact_personal_data(
        request.detected, request.model_dump(exclude={"detected"})
    )


@router.post("/data-quality/duplicate", summary="which samples this one repeats")
async def post_duplicate(sample: Sample) -> None:
    return await report_duplicates(sample.model_dump())


@router.post(
    "/data-quality/abnormal", summary="what the checks needing no opinion found"
)
async def post_abnormal(sample: Sample) -> None:
    return await report_abnormalities(sample.model_dump())


@router.post("/ai-review", summary="what the reviewers say the label should be")
async def post_ai_review(request: ReviewRequest) -> ReviewerVerdicts:
    """Both verdicts, or 422 for a declaration this deployment cannot act on.

    Two of those: a name it does not serve, and a finetuned reviewer at all while § *Open* stands.
    The language and the two model keys are declarations about this request and not keys of the
    record, so the sample handed on is what the corpus carries.
    """
    sample = request.model_dump(exclude={"language", "jury_models", "sft_model"})
    try:
        check_served_models(
            request.jury_models + ((request.sft_model,) if request.sft_model else ())
        )
        # The finetuned reviewer is asked first, and the order is the point: while § *Open*
        # stands, a ticked one is a refusal, and a refusal raised after the panel has answered is
        # N model calls paid for and thrown away.
        sft = await predict_tool_decision_by_sft(
            SFTModelConfig(model=request.sft_model) if request.sft_model else None,
            sample,
            request.language,
        )
        return ReviewerVerdicts(
            llm=await predict_tool_decision_by_llm(
                [LLMModelConfig(model=name) for name in request.jury_models] or None,
                sample,
                request.language,
            ),
            sft=sft,
        )
    except ConfigError as error:
        # A declaration this service cannot act on, as the status that says so.
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/records", summary="one reviewed sample, into both tables")
def post_record(review: ReviewedSample) -> RecordStored:
    session = db.open_session()
    if session is None:
        raise HTTPException(
            status_code=503, detail=f"no database attached: set {db.variable}"
        )
    document = review.model_dump(by_alias=True)
    try:
        sample = ToolDecisionSampleBuilding().build_sample(document)
    except StepNotRun as refusal:
        raise HTTPException(status_code=422, detail=str(refusal)) from refusal
    unanswered = [
        facet for facet in ToolDecisionSample.FACETS if sample.facets.get(facet) is None
    ]
    if unanswered:
        raise HTTPException(
            status_code=422,
            detail=f"tick every declared facet: {', '.join(unanswered)} went unanswered",
        )
    with session:
        stored = merge_tool_decision_db(session, document, sample)
    return RecordStored(
        id=str(stored.key),
        created_time=stored.created_time,
        modified_time=stored.modified_time,
    )


@router.get(
    "/records/stats",
    summary="what the labelled dataset holds, counted when it is asked",
)
def get_dataset_statistics() -> ToolDecisionDatasetStatistics:
    session = db.open_session()
    if session is None:
        raise HTTPException(
            status_code=503, detail=f"no database attached: set {db.variable}"
        )
    with session:
        return build_dataset_statistics(
            sample_totals=count_total_samples(session),
            counted_distribution_by_facet=count_by_facet(session),
            # The two variables the grid is taken over, named at the read. The field that reports
            # it is named for this pair, and so is the parameter: cross a different two and the
            # keyword stops matching, which is what makes the change impossible to make quietly.
            counted_pairs_of_domain_and_call_trigger=count_by_pair(
                session, "domain", "call_trigger"
            ),
            sample_contents=select_sample_contents(session),
        )
