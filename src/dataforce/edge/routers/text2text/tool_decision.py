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

from dataforce.edge.served_models import served_models
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
from dataforce.services.tool_decision import (
    abnormal_report,
    duplicate_report,
    personal_data_detect,
    personal_data_redact,
    personal_data_replace,
    tool_decision_llm_predict,
    tool_decision_sft_predict,
)

router = APIRouter(prefix="/text2text/tool-decision", tags=["tool_decision"])

PAGE = Path(__file__).resolve().parents[2] / "static" / "index.html"


class Sample(BaseModel):
    """One tool-calling sample, as it is posted.

    `extra="allow"` because a corpus carries keys this service does not read, and dropping them
    would make what is handed on a lossy copy of what arrived.
    """

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


class ScanRequest(Sample):
    """A sample, the language it is in, and the model ticked for layer two.

    `verifier_model` and not `verifier`: a record's keys already say what each reviewer *said*, so
    a request key naming which one to *ask* must not read like the answer.

    `language` is declared here rather than on `Sample` because the scan is the one endpoint that
    reads it today, and it is one of the two `agent_toolkit`'s scans know: a third value is a
    `KeyError` from inside the library, so the choice belongs in the schema a caller reads (`H-5`)
    rather than in a refusal they discover.
    """

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
    """A sample as the human left it, and the spans they handed back over it.

    `detected` is named apart from the sample's own keys on the same terms as the scan's two
    declarations: it is what a reviewer handed back about this request, not a key the corpus
    carries. The detect answer whole rather than its spans alone, because `review_text` is what
    the offsets index and therefore the only thing that says which value a placeholder stands for.
    """

    detected: PersonalDataDetected = Field(
        ..., description="The spans as the reviewer left them, in the text they index."
    )


class ReviewRequest(Sample):
    """A sample, the language it is in, and the models ticked.

    The model keys are named apart from `llm` and `sft`, which hold answers. `language` is
    declared here on the same terms as on the scan (Decision 17): it fills the jurors' prompt
    slot, and one of the two the scans know keeps the two requests asking in one vocabulary.
    There is no judge to tick: a tie between two tool calls is two different calls, and this task
    matches the calls rather than asking a model whether they mean the same (Decision 20).
    """

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
async def personal_data(request: ScanRequest) -> PersonalDataDetected:
    """What was found, or 422 where no model resolved or the language is not one it can scan.

    `language` and `verifier_model` are declarations about this request and not keys of the
    record, so the sample handed on is what the corpus carries.
    """
    try:
        checked_names((request.verifier_model,))
        return await personal_data_detect(
            PersonalDataCheckingConfig(
                verifier_model=VerifierModelConfig(model=request.verifier_model)
            ),
            request.model_dump(exclude={"language", "verifier_model"}),
            request.language,
        )
    except ConfigError as error:
        raise refused(error) from error


@router.post(
    "/data-quality/personal-data/replace", summary="replace the spans a reviewer left"
)
def personal_data_replacement(detected: PersonalDataDetected) -> PersonalDataReplaced:
    """The same shape back out of the reviewer's hands, and the copy that ships.

    A second call because a human ticks, edits and adds spans in between: what is replaced is
    what they handed back, not what the detectors claimed. No model is asked, so nothing here
    can be refused for a name this deployment does not serve.
    """
    return personal_data_replace(detected)


@router.post(
    "/data-quality/personal-data/redact",
    summary="the sample with every handed-back span's value replaced",
)
def personal_data_redaction(request: RedactRequest) -> dict[str, Any]:
    """The sample back with its placeholders in it, wherever a confirmed value occurred.

    The record's three `new_` keys come from here (Requirements 15, 16): the page holds what the
    human edited, this replaces over all of it, and the page composes the record out of the
    answer. Replacement is by value, so it reaches `messages` and `label`, which the review
    text's offsets cannot index.

    No model is asked, so nothing here can be refused for a name this deployment does not serve,
    and nothing is kept: the sample is read, copied and answered.
    """
    return personal_data_redact(
        request.detected, request.model_dump(exclude={"detected"})
    )


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
    """Both verdicts, or 422 for a declaration this deployment cannot act on.

    Two of those: a name it does not serve, and a finetuned reviewer at all while § *Open* stands.
    The language and the two model keys are declarations about this request and not keys of the
    record, so the sample handed on is what the corpus carries.
    """
    sample = request.model_dump(exclude={"language", "jury_models", "sft_model"})
    try:
        checked_names(
            request.jury_models + ((request.sft_model,) if request.sft_model else ())
        )
        # The finetuned reviewer is asked first, and the order is the point: while § *Open*
        # stands, a ticked one is a refusal, and a refusal raised after the panel has answered is
        # N model calls paid for and thrown away.
        sft = await tool_decision_sft_predict(
            SFTModelConfig(model=request.sft_model) if request.sft_model else None,
            sample,
            request.language,
        )
        return ReviewerVerdicts(
            llm=await tool_decision_llm_predict(
                [LLMModelConfig(model=name) for name in request.jury_models] or None,
                sample,
                request.language,
            ),
            sft=sft,
        )
    except ConfigError as error:
        raise refused(error) from error
