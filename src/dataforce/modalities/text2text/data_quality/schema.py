"""shape · what the three checks are given and return, what a model answers, what a provider gets.

No module here opens a socket. The socket is the abstract method on each check's class, and
`profile/<task>/data_quality.py` is where it gets a body.
"""

from collections.abc import Callable, Mapping
from typing import Any, Literal

from agent_toolkit.string_utils import (
    email_detection_by_rules,
    name_detection_by_rules,
    otp_detection_by_rules,
    phone_number_detection_by_rules,
)
from pydantic import BaseModel, ConfigDict, Field

# What replacing left the text in. Every value is a state the copy ends in, so a reader of the
# field knows the outcome without knowing who decided it.
type PersonalDataReplacementOutcome = Literal["redacted", "reported", "withheld"]

# One rule scan: text and a language in, the values it claims out.
type RuleScan = Callable[[str, str], list[str]]

# The two `agent_toolkit` knows: its scans key their tables by this, so a third value is a
# `KeyError` from inside the library.
type Language = Literal["vi", "en"]

# The scans to pick from. A deployment's own `(class, function)` goes in the same tuple.
SCAN_FUNCTIONS: Mapping[str, tuple[str, RuleScan]] = {
    "EMAIL": ("EMAIL", email_detection_by_rules),
    "PHONE": ("PHONE", phone_number_detection_by_rules),
    "OTP": ("OTP", otp_detection_by_rules),
    "NAME": ("NAME", name_detection_by_rules),
}

# All four, in the order that settles a value two of them claim: the first to claim it keeps it.
SCANS: tuple[tuple[str, RuleScan], ...] = tuple(SCAN_FUNCTIONS.values())


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PiiLlmFinding(BaseModel):
    """One value the model detector found, in the key order the prompt asks it to write."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    reason: str = Field(
        default="",
        description="Why it is personal data, written before the value. Read, not carried.",
    )
    text: str = Field(
        default="", description="The value, copied character for character."
    )
    label: str = Field(default="", description="What the model says it is.")


class PiiLlmDetected(BaseModel):
    """What `pii_llm_detect.txt` asks for, and what `PiiLlmDetector` reads back."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    detected: tuple[PiiLlmFinding, ...] = Field(default=())


class PiiLlmSpanConfirmed(BaseModel):
    """One span the confirmation answered about, named by the id the prompt gave it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int = Field(default=0, description="Which span, as the prompt numbered it.")
    reason: str = Field(
        default="",
        description="Why, in the model's own words, and written before the verdict.",
    )
    confirmed: bool = Field(default=False, description="Whether it is personal data.")


class PiiLlmConfirmed(BaseModel):
    """What `pii_llm_confirm.txt` asks for: one answer per span it was shown."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    confirmed: tuple[PiiLlmSpanConfirmed, ...] = Field(default=())


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


class PersonalDataCheckingConfig(Frozen):
    """What one personal-data checker is configured with, for as long as it lives.

    Both detectors are built from it, so both exist before any record does.
    """

    verifier_model: VerifierModelConfig = Field(
        ..., description="Which model confirms the spans the detectors earn."
    )
    list_scan_functions: tuple[tuple[str, RuleScan], ...] = Field(
        default=SCANS,
        description="The rule scans to run, in the order that settles an overlap.",
    )


class PersonalDataCheckingInput(Frozen):
    """What one personal-data scan is given: one record, and what reading it needs."""

    sample: Mapping[str, Any] = Field(
        ..., description="The record as it arrived, with every key the corpus carries."
    )
    language: Language = Field(
        default="vi",
        description="What language the text is in; every scan and both model steps take it.",
    )


class PersonalDataSpan(Frozen):
    id: int = Field(
        ..., description="1-based, in span order. What the confirmation answers with."
    )
    # Code points, because that is what slicing `review_text` in Python counts. A reader counting
    # UTF-16 units -- a browser does -- reads a different string from the same two numbers.
    start: int = Field(
        ..., description="Code-point offset of the hit in `review_text`, inclusive."
    )
    end: int = Field(
        ...,
        description="Code-point offset of the hit's end in `review_text`, exclusive.",
    )
    personal_data_class: str = Field(
        ..., description="The typed class, which is what picks the placeholder."
    )
    placeholder: str = Field(
        ...,
        description="What stands in the text instead; the same value gets the same one.",
    )
    reason: str | None = Field(
        default=None,
        description="Why the confirmation says it is personal data. None where nothing asked.",
    )


class PersonalDataDetected(Frozen):
    """What detecting found: the frame of reference, and the spans standing in it.

    What a reviewer is shown, and what they hand back once they have ticked, edited or added a
    span. Nothing here is replaced yet -- replacing is the second call.
    """

    review_text: str = Field(
        ...,
        description="The combined input and output text shown for human review.",
    )
    claims: tuple[tuple[str, str], ...] = Field(
        default=(),
        description=(
            "`(class, value)` for every value the two detectors claimed, before the "
            "confirmation narrowed it. Carried because it is what `redacted` is measured "
            "against: a claim nothing replaced is a record held back, not a clean one."
        ),
    )
    spans: tuple[PersonalDataSpan, ...] = Field(
        default=(),
        description="Every hit that survived the confirmation, in the order it was found.",
    )


class PersonalDataReplaced(Frozen):
    """What replacing came to: the copy that ships, and how far it got."""

    redacted_text: str | None = Field(
        default=None,
        description=(
            "`review_text` copied, with every span's value replaced by its placeholder. "
            "None where there was nothing to replace, which is what `reported` means."
        ),
    )
    outcome: PersonalDataReplacementOutcome = Field(
        ...,
        description=(
            "`redacted`: every span it was given reads as its placeholder in the copy. "
            "`reported`: nothing to replace, because no span was handed over. `withheld`: "
            "replaced as far as the spans allowed, and held out of a release because "
            "something did not resolve."
        ),
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
