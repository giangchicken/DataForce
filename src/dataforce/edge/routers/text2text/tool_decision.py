"""adapter · one APIRouter for tool_decision: a request body in, one part's answer out.

A handler is thin. It reads the body, calls one function in `services/tool_decision/`, and maps the
error; it names no stage sequence, and no response carries a part the handler does not own.

There is no route that stores anything: the record the labelling UI assembles is posted nowhere
until the store is written, which waits for the flow to be finished (spec § *Out of Scope*). The
redaction route reads a sample and answers a copy of it; it keeps neither.

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
from dataforce.modalities.text2text.dataset_management import (
    DuplicateGroups,
    LabelSummary,
    calculate_duplicates,
)
from dataforce.profile.tool_decision.label_statistics import (
    count_tool_calls,
    list_offered_tools,
)
from dataforce.profile.tool_decision.schema import (
    count_by_facet,
    count_by_pair,
    count_rows,
    select_dataset_rows,
)
from dataforce.services.tool_decision import (
    create_joint_distribution_matrix,
    describe_labels,
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


class ReviewerVerdicts(BaseModel):
    """What each reviewer said. None where the request ticked no such model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm: LLMReviewerVerdict | None = Field(default=None)
    sft: SFTReviewerVerdict | None = Field(default=None)


class CorpusStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_totals: Mapping[str, int] = Field(
        ...,
        description=(
            "Table name, to how many samples it holds. The two agree -- both tables hold "
            "the same samples and differ by what is in them -- and a run where they do "
            "not is a bug rather than a figure."
        ),
    )
    counted_distribution_by_facet: Mapping[str, Mapping[str, int]] = Field(
        ...,
        description=(
            "One distribution per facet, over **every** row of `dataset`: a facet name, "
            "then each value it holds, then how many samples carry that value -- "
            '`["domain"]["telesale"]` is how many samples are telesale. Each '
            "distribution adds up to `sample_totals`, and *counted* is in the name "
            "because these are counts and never shares. The value is written as text, "
            "because a JSON object has no other kind of key. A set-valued facet is keyed "
            "by the whole set -- which combinations occur -- and "
            "`counted_distribution_by_domain_and_call_trigger` is "
            "where the values inside one are counted apart."
        ),
    )
    counted_distribution_by_domain_and_call_trigger: Mapping[str, Mapping[str, int]] = (
        Field(
            ...,
            description=(
                "The pair distribution the per-facet one cannot give: rows keyed by `domain`, "
                "columns by `call_trigger`, and how many samples are both. Every value one axis "
                "carries crossed with every value the other does, so a pair no sample makes reads "
                "`0` and the zeros are the finding. The axes are what the corpus **carries**: a "
                "value nobody has ticked yet has no cell, because the tickable list lives with the "
                "page, and crossing this against it is the page's arithmetic. A sample triggered "
                "two ways is in two cells, so the cells may sum past the row count."
            ),
        )
    )
    label_summary: LabelSummary = Field(
        ...,
        description=(
            "How many rows answered at all out of how many, and how many distinct answers "
            "they hold between them. How many rows make each number of calls is "
            "`counted_distribution_by_facet` at `number_label_tools`."
        ),
    )
    number_tools_offered: int = Field(
        ...,
        description=(
            "How many distinct tools the catalogs put in front of the model. Not "
            "`len(tool_call_counts)`: a label may name a tool it was never offered, and "
            "that is a broken row rather than an offer. Here and not in `label_summary`, "
            "because that shape is one every text2text task shares and not every one of "
            "them has tools at all."
        ),
    )
    tool_call_counts: Mapping[str, int] = Field(
        ...,
        description=(
            "Tool name, to how many calls the corpus's labels make to it. A tool offered "
            "and never called stays here at `0` -- **the zeros are the finding**, a tool "
            "the corpus cannot teach -- and the tail is the other half: two tools carrying "
            "most of the calls trains a model that knows two tools."
        ),
    )
    duplicate_groups: DuplicateGroups = Field(
        ...,
        description="The same input under more than one row key, split by whether the labels agree.",
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


@router.post(
    "/data-quality/personal-data/replace", summary="replace the spans a reviewer left"
)
def post_personal_data_replacement(
    detected: PersonalDataDetected,
) -> PersonalDataReplaced:
    """The same shape back out of the reviewer's hands, and the copy that ships.

    A second call because a human ticks, edits and adds spans in between: what is replaced is
    what they handed back, not what the detectors claimed. No model is asked, so nothing here
    can be refused for a name this deployment does not serve.
    """
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


@router.get("/records/stats", summary="what the corpus holds, counted when it is asked")
def get_corpus_stats() -> CorpusStatistics:
    session = db.open_session()
    if session is None:
        raise HTTPException(
            status_code=503, detail=f"no database attached: set {db.variable}"
        )
    with session:
        rows = select_dataset_rows(session)
        labels = [label for _, _, label in rows]
        catalogs = [one_input.get("tools") or () for _, one_input, _ in rows]
        return CorpusStatistics(
            sample_totals=count_rows(session),
            counted_distribution_by_facet=count_by_facet(session),
            counted_distribution_by_domain_and_call_trigger=(
                create_joint_distribution_matrix(
                    count_by_pair(session, "domain", "call_trigger")
                )
            ),
            label_summary=describe_labels(labels),
            number_tools_offered=len(list_offered_tools(catalogs)),
            tool_call_counts=count_tool_calls(labels, catalogs),
            duplicate_groups=calculate_duplicates(
                [key for key, _, _ in rows],
                [one_input for _, one_input, _ in rows],
                labels,
            ),
        )
