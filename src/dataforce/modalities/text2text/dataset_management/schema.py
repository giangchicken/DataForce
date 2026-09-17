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

    Each entry is one group's row keys. Groups rather than a flat list of keys, because dropping
    all but one of a group and opening a group to inspect both need to know which rows are one
    another's duplicate.
    """

    duplicate_content_same_label: tuple[tuple[str, ...], ...] = Field(
        default=(), description="Same content, same label: safe to drop one of them."
    )
    duplicate_content_diff_label: tuple[tuple[str, ...], ...] = Field(
        default=(), description="Same content, different label: one of them is wrong."
    )


class LabelSummary(Frozen):
    """What a corpus's labels come to, each figure beside the total it came out of.

    Counts and never a share: a share over nine rows and a share over nine thousand are different
    claims, so `total` travels with the rest rather than a percentage being worked out here. It is
    also what makes a corpus of no rows an answer rather than a division.

    **A label here is a sequence that may be absent, and nothing more.** Every figure is about that
    much, because that is all any text2text label has in common: what the entries *are* is the
    task's, so what the corpus offers and what it calls are answered where those words mean
    something, and are not fields a summarisation task would inherit with nothing to put in them.
    """

    total: int = Field(default=0, description="How many rows were read.")
    number_not_null_label: int = Field(
        default=0,
        description=(
            "How many of them answered at all. `()` and `None` are one reading -- no answer was "
            "needed -- so neither counts, and `total` less this is the no-answer share's numerator."
        ),
    )
    number_diff_label: int = Field(
        default=0,
        description=(
            "How many **distinct** answers the corpus holds, counted over the same canonical text "
            "the duplicate grouping compares by. Diversity: a thousand rows carrying nine answers "
            "between them is a corpus that teaches nine things."
        ),
    )
