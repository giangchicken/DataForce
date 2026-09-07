"""shape · what the three checks return, and what each one's provider is handed.

No module here opens a socket. The socket is the abstract method on each check's class, and
`profile/<task>/data_quality.py` is where it gets a body.
"""

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

type Decision = Literal["redacted", "reported", "withheld"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PersonalDataSpan(Frozen):
    start: int = Field(..., description="Character offset of the hit, inclusive.")
    end: int = Field(..., description="Character offset of the hit's end, exclusive.")
    personal_data_class: str = Field(
        ..., description="The typed class, which is what picks the placeholder."
    )
    placeholder: str = Field(
        ...,
        description="What stands in the text instead; the same value gets the same one.",
    )


class PersonalDataScan(Frozen):
    review_text: str = Field(
        ...,
        description="The combined input and output text shown for human review.",
    )
    redacted_text: str | None = Field(
        default=None,
        description=(
            "`review_text` copied, with every confirmed value replaced by its placeholder. "
            "None where nothing was rewritten, which is what `reported` means."
        ),
    )
    decision: Decision = Field(
        ...,
        description=(
            "`redacted`: rewritten and every hit confirmed. `reported`: left alone, "
            "redaction off. `withheld`: rewritten as far as layer two confirmed, and "
            "held out of a release because something was not."
        ),
    )
    spans: tuple[PersonalDataSpan, ...] = Field(
        default=(), description="Every hit, in the order the scan found it."
    )


class DuplicateGroups(Frozen):
    duplicate_content_same_label: tuple[str, ...] = Field(
        default=(), description="Same content, same label: safe to drop one of them."
    )
    duplicate_content_diff_label: tuple[str, ...] = Field(
        default=(), description="Same content, different label: one of them is wrong."
    )


class EmbedderModelConfig(BaseModel):
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


class VerifierModelConfig(BaseModel):
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
