"""adapter · one APIRouter for tool_decision: a request body in, one part's answer out."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

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
    PersonalDataRedacted,
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
    count_queued_states,
    count_total_samples,
    mark_queued_sample,
    merge_tool_decision_db,
    name_queued_sample,
    queue_tool_decision_samples,
    select_next_queued_sample,
    select_queued_sample,
    select_queued_samples,
    select_sample_contents,
    select_stored_sample,
    select_stored_samples,
)
from dataforce.profile.tool_decision.schema import (
    LabelChecked,
    QueuedSampleImport,
    QueuedSampleList,
    QueuedSampleWaiting,
    QueueState,
    SamplesNamed,
    StoredSample,
    StoredSampleList,
    ToolDecisionDatasetStatistics,
    ToolDecisionSample,
)
from dataforce.services.tool_decision import (
    build_dataset_statistics,
    check_label_calls,
    detect_personal_data,
    list_personal_data_classes,
    number_personal_data_spans,
    predict_tool_decision_by_llm,
    predict_tool_decision_by_sft,
    read_queued_samples,
    redact_personal_data,
    report_abnormalities,
    report_duplicates,
)

router = APIRouter(prefix="/text2text/tool-decision", tags=["tool_decision"])

PAGE = Path(__file__).resolve().parents[2] / "static" / "index.html"


class Sample(BaseModel):
    """One sample as a route receives it. **The name is optional, because a raw line has none.**

    A corpus line is `{messages, tools, label}` -- nothing writes an `id` into one -- and the only
    thing in this service that reads a sample's name is the key a record is stored under. Every
    other route here scans, replaces or votes on the text and never looks at it, so demanding one
    made a raw line unscannable for a field nobody was going to use. The one route that needs it
    asks for it itself, in a sentence.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = Field(
        default=None,
        description=(
            "What the sample is called. Absent on a raw line; `/samples/named` answers the "
            "name an import would give one, and that name is what a record is stored under."
        ),
    )
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


class SpanRequest(Sample):
    claimed: tuple[tuple[str, str], ...] = Field(
        default=(),
        description=(
            "`(class, value)` for every value the reviewer left on the table -- the ones they "
            "kept and the ones they typed -- in the order they are read in, which is the shape "
            "`PersonalDataDetected.claims` comes back in. **Ordered, and not an object**: where "
            "two values start at one offset the order settles which is numbered first, and a "
            "JSON object of them is one a client can reorder without meaning to. **No offset is "
            "sent** -- where each value stands, how many times and which `<CLASS_N>` it gets are "
            "what this route answers."
        ),
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


class StoreAttached(BaseModel):
    attached: bool = Field(..., description="Whether there is a database at all.")
    describes: str | None = Field(
        default=None,
        description="The database, named: a file name, or a dialect, host and name.",
    )
    variable: str = Field(
        ...,
        description="The variable that names it, for a message that says what to set.",
    )


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


@router.get(
    "/data-quality/personal-data/classes",
    summary="what a value may be said to be",
)
def get_personal_data_classes() -> tuple[str, ...]:
    """The scans' own classes, so a caller picking one picks from the list that numbers them."""
    return list_personal_data_classes()


@router.post(
    "/data-quality/personal-data/spans",
    summary="where these values stand in the text, numbered as the scan numbers them",
)
def post_personal_data_spans(request: SpanRequest) -> PersonalDataDetected:
    """The same answer the scan gives, over the values a reviewer left rather than a model's.

    No model and no database: the two pure functions the scan ends with, so a page may ask on
    every tick. `claimed` is a declaration about this request and not a key of the record, so the
    sample handed on is what the corpus carries.
    """
    return number_personal_data_spans(
        request.model_dump(exclude={"claimed"}),
        {value: personal_data_class for personal_data_class, value in request.claimed},
    )


@router.post(
    "/data-quality/personal-data/redact",
    summary="the record with every handed-back span's value replaced, and how it reads",
)
def post_personal_data_redaction(request: RedactRequest) -> PersonalDataRedacted:
    return redact_personal_data(
        request.detected, request.model_dump(exclude={"detected"})
    )


@router.post(
    "/data-quality/label",
    summary="whether this label is callable against its own catalog",
)
def post_label_check(sample: Sample) -> LabelChecked:
    return check_label_calls(sample.label, sample.tools)


@router.post("/data-quality/duplicate", summary="which samples this one repeats")
async def post_duplicate(sample: Sample) -> None:
    return await report_duplicates(sample.model_dump())


@router.post(
    "/data-quality/abnormal", summary="what the checks needing no opinion found"
)
async def post_abnormal(sample: Sample) -> None:
    return await report_abnormalities(sample.model_dump())


@router.post(
    "/samples/named",
    summary="the same lines, each under the name an import would give it",
)
def post_named_samples(
    lines: Annotated[bytes, Body(media_type="application/x-ndjson")],
) -> SamplesNamed:
    try:
        text = lines.decode("utf-8")
    except UnicodeDecodeError as unreadable:
        raise HTTPException(
            status_code=422, detail=f"what was pasted is not UTF-8: {unreadable}"
        ) from unreadable
    samples, refused = read_queued_samples(text)
    return SamplesNamed(
        read=len(samples) + len(refused),
        samples=tuple(named for _, named in map(name_queued_sample, samples)),
        unreadable=refused,
    )


@router.post("/ai-review", summary="what the reviewers say the label should be")
async def post_ai_review(request: ReviewRequest) -> ReviewerVerdicts:
    sample = request.model_dump(exclude={"language", "jury_models", "sft_model"})
    try:
        check_served_models(
            request.jury_models + ((request.sft_model,) if request.sft_model else ())
        )
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
        raise HTTPException(status_code=422, detail=str(error)) from error


def open_store() -> Session:
    session = db.open_session()
    if session is None:
        raise HTTPException(
            status_code=503, detail=f"no database attached: set {db.variable}"
        )
    return session


@router.post(
    "/queue/import", summary="a file of raw samples, as rows waiting to be labelled"
)
def post_queue_import(
    lines: Annotated[bytes, Body(media_type="application/x-ndjson")],
) -> QueuedSampleImport:
    """One JSON object per line. Re-importing a file imports nothing the second time."""
    session = open_store()
    try:
        text = lines.decode("utf-8")
    except UnicodeDecodeError as unreadable:
        raise HTTPException(
            status_code=422, detail=f"the file is not UTF-8: {unreadable}"
        ) from unreadable
    samples, refused = read_queued_samples(text)
    with session:
        imported, already_held = queue_tool_decision_samples(session, samples)
    return QueuedSampleImport(
        read=len(samples) + len(refused),
        imported=imported,
        already_held=already_held,
        unreadable=refused,
    )


def describe_queue(session: Session) -> QueuedSampleWaiting:
    waiting = select_next_queued_sample(session)
    counted = count_queued_states(session)
    return QueuedSampleWaiting(
        sample=None if waiting is None else dict(waiting[1]),
        key=None if waiting is None else str(waiting[0]),
        waiting=counted[QueueState.WAITING],
        done=counted[QueueState.DONE],
        skipped=counted[QueueState.SKIPPED],
    )


@router.get("/store", summary="which database a record would land in")
def get_store() -> StoreAttached:
    return StoreAttached(
        attached=db.open_engine() is not None,
        describes=db.describe(),
        variable=db.variable,
    )


@router.get("/queue", summary="the samples in the queue, to pick from")
def get_queue(limit: int = 200, offset: int = 0) -> QueuedSampleList:
    """A page of the queue in walk order, every state included.

    `limit` is capped rather than trusted: a corpus is as large as somebody's file, and one request
    asking for all of it is one response nobody can render.
    """
    session = open_store()
    with session:
        counted = count_queued_states(session)
        return QueuedSampleList(
            samples=select_queued_samples(
                session, min(max(limit, 1), 1000), max(offset, 0)
            ),
            waiting=counted[QueueState.WAITING],
            done=counted[QueueState.DONE],
            skipped=counted[QueueState.SKIPPED],
        )


@router.get("/queue/next", summary="the next sample to label, and how much is left")
def get_queue_next() -> QueuedSampleWaiting:
    """An empty queue answers an empty sample, not an error: nothing is wrong with being done."""
    session = open_store()
    with session:
        return describe_queue(session)


@router.get("/queue/{key}", summary="one queued sample, picked out of the list")
def get_queued_sample(key: uuid.UUID) -> QueuedSampleWaiting:
    """Whatever state it is in: picking a row already labelled is asking to look at it again."""
    session = open_store()
    with session:
        found = select_queued_sample(session, key)
        if found is None:
            raise HTTPException(status_code=404, detail=f"no queued sample under {key}")
        counted = count_queued_states(session)
        return QueuedSampleWaiting(
            sample=found,
            key=str(key),
            waiting=counted[QueueState.WAITING],
            done=counted[QueueState.DONE],
            skipped=counted[QueueState.SKIPPED],
        )


@router.post("/queue/{key}/skip", summary="pass this one over, and take the next")
def post_queue_skip(key: uuid.UUID) -> QueuedSampleWaiting:
    """The row stays, in the state that says it was passed over, and the next one comes back."""
    session = open_store()
    with session:
        if not mark_queued_sample(session, key, QueueState.SKIPPED):
            raise HTTPException(status_code=404, detail=f"no queued sample under {key}")
        session.commit()
        return describe_queue(session)


@router.post("/records", summary="one reviewed sample, into both tables")
def post_record(
    review: ReviewedSample, queue_key: uuid.UUID | None = None
) -> RecordStored:
    session = open_store()
    if review.id is None:
        # In a sentence, not as a validation list: a body FastAPI could not read answers with the
        # whole sample echoed back inside it, and *which field* disappears into the echo. This is
        # the one route where the name is load-bearing, so it says so and says where to get one.
        raise HTTPException(
            status_code=422,
            detail=(
                "this sample has no name, and its name is the key the row is stored under. "
                "Ask /samples/named for one, or import the line and label it from the queue."
            ),
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
        if queue_key is not None and not mark_queued_sample(
            session, queue_key, QueueState.DONE
        ):
            raise HTTPException(
                status_code=404, detail=f"no queued sample under {queue_key}"
            )
        stored = merge_tool_decision_db(session, document, sample)
    return RecordStored(
        id=str(stored.key),
        created_time=stored.created_time,
        modified_time=stored.modified_time,
    )


@router.get("/records", summary="the stored corpus, a page at a time")
def get_stored_samples(limit: int = 100, offset: int = 0) -> StoredSampleList:
    session = open_store()
    with session:
        return StoredSampleList(
            samples=select_stored_samples(
                session, min(max(limit, 1), 1000), max(offset, 0)
            ),
            total=count_total_samples(session)[ToolDecisionSample.__tablename__],
        )


@router.get(
    "/records/stats",
    summary="what the labelled dataset holds, counted when it is asked",
)
def get_dataset_statistics() -> ToolDecisionDatasetStatistics:
    session = open_store()
    with session:
        return build_dataset_statistics(
            sample_totals=count_total_samples(session),
            counted_distribution_by_facet=count_by_facet(session),
            counted_pairs_of_domain_and_call_trigger=count_by_pair(
                session, "domain", "call_trigger"
            ),
            sample_contents=select_sample_contents(session),
        )


@router.get("/records/{key}", summary="one stored sample, as it ships")
def get_stored_sample(key: uuid.UUID) -> StoredSample:
    session = open_store()
    with session:
        found = select_stored_sample(session, key)
        if found is None:
            raise HTTPException(status_code=404, detail=f"no stored sample under {key}")
        return found
