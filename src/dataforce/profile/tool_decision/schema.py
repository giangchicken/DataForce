"""shape · this task's nouns: its three tables, and the bodies its routes answer with."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
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


class QueueState(StrEnum):
    """Where one imported sample has got to. A closed set, because a fourth is a design decision.

    `StrEnum` so the column stores the word and a reader of the table sees `waiting` rather than a
    number nothing explains -- the row outlives every process that wrote it, and the meaning has to
    travel with it.
    """

    WAITING = "waiting"
    DONE = "done"
    SKIPPED = "skipped"


class ToolDecisionQueuedSample(Base):
    """One raw sample, as the line it was imported from held it, and where it has got to.

    Raw and never corrected: what the reviewer changed belongs to `record`, and a queue holding
    corrected samples could not be walked a second time by anyone wanting to check the first walk.
    """

    __tablename__ = "tool_decision_queue"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    imported_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    walk_position: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False, index=True)


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
    # A level and not a yes: *arguable* is a matter of degree, and a reviewer forced to pick one
    # of two puts everything half-arguable on whichever side they lean. What the levels are is the
    # page's, like every other declared facet -- the column only says it is written as text.
    ambiguous: Mapped[str] = mapped_column(String, nullable=False)
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
            '`["domain"]["telesale"]` is how many samples are telesale. A facet held as a '
            "key in `notes` rather than as a column is counted here too, and a row written "
            "before that facet existed is counted under `none`. Each "
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


class QueuedSampleImport(BaseModel):
    """What one import came to.

    `unreadable` names lines by their number rather than counting them, because the answer a person
    needs from a failed import is *which line do I go and fix*, and a count is the one thing that
    cannot be acted on.
    """

    read: int = Field(..., description="Lines the file held, blank ones not counted.")
    imported: int = Field(
        ..., description="Lines that became a row waiting to be labelled."
    )
    already_held: int = Field(
        ..., description="Lines whose sample the queue already had, under the same key."
    )
    unreadable: tuple[int, ...] = Field(
        default=(),
        description="The 1-based numbers of the lines that were not JSON objects.",
    )


class SamplesNamed(BaseModel):
    """The same lines back, each carrying the name an import would have given it.

    **The one sample path that touches no database.** A sample pasted into the page is labelled
    where it is, so nothing writes a queue row for it -- but it still needs a name, because the
    key a record is stored under is its name and an anonymous sample cannot be stored at all.
    The name is the content's, so pasting a sample the corpus already holds lands on that row
    rather than beside it.

    `unreadable` names lines by their number for the same reason the import does: the answer a
    person needs is *which line do I go and fix*.
    """

    read: int = Field(..., description="Lines that were read, blank ones not counted.")
    samples: tuple[Mapping[str, Any], ...] = Field(
        default=(),
        description="Each line as it arrived, carrying `id` — its own if it had one.",
    )
    unreadable: tuple[int, ...] = Field(
        default=(),
        description="The 1-based numbers of the lines that were not JSON objects.",
    )


class QueuedSampleRow(BaseModel):
    """One line of the list a reviewer picks from.

    Not the whole sample: a list of three hundred would carry three hundred conversations, and what
    a person picks from is the first thing said and whether anybody has been here already.
    """

    key: str = Field(
        ..., description="The queue row's key, which is also the sample's name."
    )
    state: str = Field(..., description="One of `waiting`, `done`, `skipped`.")
    walk_position: int = Field(
        ..., description="Where it stands in the walk, counting from one."
    )
    preview: str = Field(
        default="",
        description=(
            "The opening turn, cut to a preview. Empty where the sample has no turns at all, "
            "which is a sample worth seeing in the list rather than hiding."
        ),
    )


class StoredSampleRow(BaseModel):
    """One line of the table a person reads the stored corpus by.

    The facets and not the sample: a page of three hundred rows would carry three hundred
    conversations, and what somebody scans a corpus for is which rows are short, which are
    arguable, and **which ones nothing could validate** -- a label naming a tool the catalog does
    not offer, or leaving out an argument the tool requires, is `schema_valid` false and is the
    one column here that says a row needs going back to.

    Read off `tool_decision_dataset` and never off `tool_decision_record`. The record table keeps
    what arrived, un-redacted, because that is what makes a review auditable; a route that served
    it would put a person's phone number on the screen of anyone who can open the page. What is
    in here is the copy that ships.
    """

    key: str = Field(..., description="The row's key, which is also the sample's name.")
    preview: str = Field(
        default="",
        description="The opening turn of the redacted copy, cut to a preview.",
    )
    language: str = Field(..., description="What language the sample is in.")
    domain: str = Field(..., description="Which domain the reviewer put it in.")
    ambiguous: str = Field(..., description="How arguable they said it is.")
    call_trigger: tuple[str, ...] = Field(
        default=(), description="What they said makes the call fire."
    )
    personal_data: tuple[str, ...] = Field(
        default=(), description="The classes actually redacted out of this row."
    )
    number_turns: int = Field(..., description="How many turns the conversation has.")
    number_label_tools: int = Field(
        ..., description="How many calls the label makes. Zero is an answer, not a gap."
    )
    number_provided_tools: int = Field(
        ..., description="How many tools the catalog offered."
    )
    schema_valid: bool = Field(
        ...,
        description=(
            "Whether every call the label makes names an offered tool and supplies its "
            "required arguments. False and `number_label_tools` zero together is a label that "
            "named a tool without calling it."
        ),
    )
    modified_time: datetime = Field(..., description="When this row was last written.")


class StoredSampleList(BaseModel):
    """A page of the stored corpus, and what the whole of it comes to."""

    samples: tuple[StoredSampleRow, ...] = Field(
        default=(), description="This page of rows, newest write first."
    )
    total: int = Field(..., description="How many rows the table holds in all.")


class StoredSample(BaseModel):
    """One stored row whole: the copy that ships, and every facet it is filed under."""

    key: str = Field(..., description="The row's key.")
    input: Mapping[str, Any] = Field(
        ..., description="`{messages, tools}` as they ship, redaction included."
    )
    label: tuple[Any, ...] | None = Field(
        default=None,
        description="The calls as they ship. `()` and `null` both mean no call was needed.",
    )
    facets: Mapping[str, Any] = Field(
        default_factory=dict,
        description=(
            "Every facet this row carries, by name -- the columns and the keys in `notes` "
            "together. Both, because a facet that is a key rather than a column is still "
            "something a person ticked, and answering only the columns made `direction` and "
            "`have_conversation_flow` write-only."
        ),
    )
    created_time: datetime = Field(..., description="When it was first stored.")
    modified_time: datetime = Field(..., description="When it was last written.")


class LabelChecked(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_valid: bool = Field(
        ...,
        description=(
            "Whether every call the label makes names an offered tool and supplies its "
            "required arguments. True is `faults` being empty and nothing else."
        ),
    )
    faults: tuple[str, ...] = Field(
        default=(),
        description=(
            "One sentence per broken call, naming it by its position in the label. Empty "
            "where the label validates."
        ),
    )


class QueuedSampleList(BaseModel):
    """A page of the queue, and what the whole of it comes to.

    The counts are of the whole queue and not of the page, because they answer *how much is left*
    and a page is an artefact of asking.
    """

    samples: tuple[QueuedSampleRow, ...] = Field(
        default=(), description="This page of rows."
    )
    waiting: int = Field(..., description="Rows nobody has labelled or skipped.")
    done: int = Field(..., description="Rows whose record was written.")
    skipped: int = Field(..., description="Rows a reviewer passed over.")


class QueuedSampleWaiting(BaseModel):
    """The next sample to label, and how much of the queue is left.

    The counts ship with the sample rather than from a route of their own: they are read in the
    same breath the sample is, and a second call would let the two disagree on screen.
    """

    sample: Mapping[str, Any] | None = Field(
        default=None, description="The raw sample, or `null` where nothing is waiting."
    )
    key: str | None = Field(
        default=None, description="The queue row's key, posted back to say it is done."
    )
    waiting: int = Field(..., description="Rows nobody has labelled or skipped.")
    done: int = Field(..., description="Rows whose record was written.")
    skipped: int = Field(..., description="Rows a reviewer passed over.")


class ToolDecisionDataStamp(NamedTuple):
    """What one write came to: the key both tables took, and the two times standing on it."""

    key: uuid.UUID
    created_time: datetime
    modified_time: datetime


class ToolDecisionSampleContent(NamedTuple):
    key: str
    input: Mapping[str, Any]
    label: Any
