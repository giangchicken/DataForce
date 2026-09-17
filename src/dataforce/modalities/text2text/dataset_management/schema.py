"""shape · what a stored text2text sample is, and the duplicate groups over a corpus."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoredSample(Frozen):
    """One kept row, before a profile's tables turn it into columns."""

    input: Mapping[str, Any] = Field(
        ..., description="What a sample of this task ships as."
    )
    label: tuple[Any, ...] | None = Field(
        ...,
        description="The label as it ships. `()` and `None` both mean no answer was needed.",
    )
    facets: Mapping[str, Any] = Field(
        ...,
        description="Facet name to value. Which of them are columns is the profile's.",
    )


class DuplicateGroups(Frozen):
    """The same input carried by more than one row, split by whether the labels agree.

    Each entry is one input's digest, so a group of three rows is one entry.
    """

    duplicate_content_same_label: tuple[str, ...] = Field(
        default=(), description="Same content, same label: safe to drop one of them."
    )
    duplicate_content_diff_label: tuple[str, ...] = Field(
        default=(), description="Same content, different label: one of them is wrong."
    )
