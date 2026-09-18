"""shape · this task's nouns: its two tables, and the body its statistics answer with."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar, NamedTuple

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

# The module and not the package door: a facade resolves to everything behind it, and behind
# this one is `logic` as well -- which `shape` may not reach (`H-8`).
from dataforce.modalities.text2text.dataset_management.schema import (
    DatasetDuplicateGroups,
    DatasetLabelSummary,
)
from dataforce.tables import Base


class ToolDecisionRecord(Base):
    """The review, whole and unaltered. The evidence for trusting the other table."""

    __tablename__ = "tool_decision_record"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ToolDecisionSample(Base):
    """What a buyer gets: the input and the label as the review left them, and the facets.

    Every column is computed from the `record` row of the same key, so this table can be dropped
    and rebuilt at any time and nothing else writes to it.
    """

    __tablename__ = "tool_decision_dataset"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    # `{messages, tools}` -- the turns and the catalog together, because a tool call is a call
    # against a catalog and a label stored apart from one is a label nothing can check.
    input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    label: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    language: Mapped[str] = mapped_column(String, nullable=False)
    personal_data: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    call_trigger: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    number_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    number_label_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    number_provided_tools: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    FACETS: ClassVar[tuple[str, ...]] = (
        "language",
        "personal_data",
        "ambiguous",
        "domain",
        "call_trigger",
        "number_turns",
        "number_label_tools",
        "number_provided_tools",
        "schema_valid",
    )

    notes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ToolDecisionDatasetStatistics(BaseModel):
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
    label_summary: DatasetLabelSummary = Field(
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
    duplicate_groups: DatasetDuplicateGroups = Field(
        ...,
        description="The same input under more than one row key, split by whether the labels agree.",
    )


class ToolDecisionDataStamp(NamedTuple):
    """What one write came to: the key both tables took, and the two times standing on it."""

    key: uuid.UUID
    created_time: datetime
    modified_time: datetime


class ToolDecisionSampleContent(NamedTuple):
    """One sample's content under its key: what goes in, and what comes out.

    The two columns a buyer is sold, without the nine facets that describe them -- which is exactly
    what every measurement over the corpus reads and nothing more.

    Declared rather than answered as a bare triple, because the reading happens two layers from the
    query: `services/` is handed these and takes the key, the input and the label off each one, and
    a bare tuple would have it doing that by position -- four times, at a distance, with the column
    order of a `SELECT` as the only thing holding it together.
    """

    key: str
    input: Mapping[str, Any]
    label: Any
