"""shape · what a text2text sample is on its way into a corpus, and what a corpus's labels come to.

Three samples, because a sample is three different things on the way in and each layer reads one of
them: `ScannedPersonalData` is what the scan and the redaction left behind as evidence,
`ShippedDatasetSample` is the three fields as they ship, and `DatasetSample` is what a dataset holds. The
envelope the thirteen keys arrive in is declared at the boundary that receives them and is not
here.

`ShippedDatasetSample` keeps its participle where `DatasetSample` could not, and the difference is that
nothing here *ships* one: *what ships* is the word the spec, the store and step 7 of the page all
use for the outgoing copy, so it names a kind and not a state something is waiting to enter. A
sample called stored and handed to a function that stores it is the other thing.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..data_quality.schema import PersonalDataDetected, PersonalDataReplacementOutcome


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StepNotRun(Exception):
    """A step the record needed did not run. Nothing is stored and nothing is repaired.

    The whole of it is the name: which step, and what about it, are the message the raise writes.
    Nothing here reads a message apart again, so a constructor that split it into two arguments
    would be this module doing work, and a `shape` holds nouns.

    The second exception in this codebase, and the reason `errors.py` holds only one: this is not
    something that went wrong *about* a record, which is a value on that record. It is a record
    that may not become one, and raising is what makes that unbypassable -- no `DatasetSample`
    exists for a document that failed, so nothing downstream can write one by forgetting to look.
    """


class ScannedPersonalData(PersonalDataDetected):
    """The record's `personal_data` key: what the scan found, and how far redacting it got.

    The detect answer as the page handed it back -- the spans say which values were confirmed and
    the text they index is the only place those values can be read from, which is what the
    precondition below needs -- plus the one thing the redaction knows and the spans do not.

    **The redacted copy itself is not in here.** It used to be, and it was the same text twice:
    the record already carries what ships under its three `new_` keys, and the precondition reads
    those rather than a copy alongside them. A second copy of a thing is a second thing to keep
    in step.

    Declared by inheriting the detect answer rather than restating its fields, so a span here and
    a span a reviewer edited cannot come to mean different things.
    """

    outcome: PersonalDataReplacementOutcome = Field(
        ...,
        description=(
            "How far the redaction got over what ships. Evidence and not a gate: the "
            "precondition below re-reads the confirmed values out of what was actually "
            "written, because a record saying it is clean is not a record that is."
        ),
    )


class ShippedDatasetSample(Frozen):
    """The three as they ship: the `new_` copy, or what arrived where no new version was made.

    What a buyer gets, before a profile says which part of it is `input` and which is `label`.
    Never what arrived -- that lives on in the record's own document and nowhere else, which is
    what makes a corpus built out of these exportable.
    """

    messages: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The conversation as it ships, in order."
    )
    tools: tuple[Mapping[str, Any], ...] = Field(
        default=(), description="The catalog as it ships."
    )
    label: tuple[Any, ...] | None = Field(
        default=None,
        description="The answer as it ships. `()` and `None` both mean no answer was needed.",
    )


class DatasetSample(Frozen):
    """One sample as a dataset holds it: what it ships as, what it answers, and what kind it is.

    **Not `StoredSample`**, which is what it was called and what it never is at the moment it
    exists: `build_sample` answers one *before* anything is written, and the thing it is handed to
    is `merge_tool_decision_db` -- storing a sample already called stored. A name may not
    claim a state the object is in for none of its life.

    The three are what any dataset needs of a sample, which is why they are the modality's: what
    goes in, what comes out, and what kind of sample it is. Which facets become columns, and which
    fall into a JSON note, is the profile's -- this shape is the same either way.
    """

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


class DatasetDuplicateGroups(Frozen):
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


class DatasetLabelSummary(Frozen):
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
