"""shape · what the two reviewers return, and the two sockets they answer through.

`LLMReviewerAnswer` is what a model said before anything decides whether it is usable;
`LLMReviewerVote` and `SFTReviewerVerdict` are what this package concluded about that.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class LLMReviewerAnswer(Frozen):
    """What a juror's prompt asks it for, in the key order it asks for them.

    Both keys are required: an answer missing either is a model that did not answer.
    `label` arrives as the array the prompt asked for, or as text where it asked
    for text; a vote holds it as one string either way, and what turns the one into the other is
    the task's, not this file's.
    """

    reason: str = Field(..., description="Why, for the human who reads a disagreement.")
    label: str | list[Any] = Field(
        ...,
        description="What it answered: the array the prompt asked for, or text already.",
    )


class LLMReviewerVote(Frozen):
    model_name: str = Field(..., description="Which juror produced this vote.")
    reason: str = Field(..., description="Why, for the human who reads a disagreement.")
    label: str = Field(..., description="Its own answer.")


class LLMReviewerVerdict(Frozen):
    votes: tuple[LLMReviewerVote, ...] = Field(
        default=(), description="One entry per juror that answered."
    )
    label_agreement: float = Field(
        default=0.0,
        description="Share of votes that say what the label says, 0 to 1. 0.0 where none did.",
    )
    consensus: str | None = Field(
        default=None,
        description=(
            "The one answer the panel is taken to have given. None where it gave none "
            "defensibly -- which is not the same as an empty answer."
        ),
    )


class SFTReviewerVerdict(Frozen):
    model_name: str = Field(..., description="Which model answered.")
    label: str = Field(..., description="Its own answer.")
    confidence: float = Field(..., description="How sure it is, 0 to 1.")


class LLMModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    model_name: str = Field(..., alias="model", description="Which model answers.")
    base_url: str | None = Field(
        default=None,
        description=(
            "Where it answers. None leaves it to `config/model/<model name>.json`, or to "
            "the environment where that file names neither."
        ),
    )
    api_key: str | None = Field(
        default=None,
        description="What authenticates the call, on the same terms as `base_url`.",
    )
    settings: Mapping[str, Any] = Field(
        default_factory=dict,
        description="What the provider is handed on top of the three, forwarded untouched.",
    )


class SFTModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    model_name: str = Field(..., alias="model", description="Which model answers.")
    base_url: str | None = Field(
        default=None,
        description=(
            "Where it answers. None leaves it to `config/model/<model name>.json`, or to "
            "the environment where that file names neither."
        ),
    )
    api_key: str | None = Field(
        default=None,
        description="What authenticates the call, on the same terms as `base_url`.",
    )
    settings: Mapping[str, Any] = Field(
        default_factory=dict,
        description="What the provider is handed on top of the three, forwarded untouched.",
    )
