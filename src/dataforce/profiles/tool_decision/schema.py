"""DEFINITION · the tool_decision shapes: a call, an answer, and what constrains one.

The types ``profiles/base.py`` refuses to name (Requirement 47), plus the one that constrains them.
``AnswerConfig`` and ``LabelCheck`` are aliases for ``Any`` there and are these shapes here; ``Call``
is the model an ``Answer`` is made of; ``Tool`` is what a record's own catalog turns into, and it is
here rather than in ``record.py`` because a catalog is a *permitted answer's* shape and what an answer
is is the whole of what a profile declares.

**There is deliberately no ``Answer`` in this module.** ``base.Answer`` is the opaque alias every
member's signature uses, and what actually crosses the boundary is ``record.StoredAnswer``. A second
``Answer`` here -- ``tuple[Call, ...]``, the parsed form -- meant one word naming two shapes inside one
axis, so a reader following Requirement 47 got the wrong type for all four operations. The parsed
form is ``Calls``, which is what ``calls_in`` returns and what it says.

**An answer is a set of calls, and a call is a name and its arguments.** ``SendStatement`` alone
cannot distinguish ``ky: "thang_nay"`` from ``ky: "thang_truoc"``, and a dataset that cannot
distinguish them teaches a model that the argument does not matter. The empty answer -- call
nothing -- is a member of the type rather than a missing value, which is why ``Answer`` is a tuple
and never ``None``: *the panel agreed to call nothing* and *the panel produced nothing defensible*
are two values, and ``vote_consensus`` returns each of them.

**What crosses the axis boundary is the record's shape, not this one.** A stage hands
``record.label`` or a ``JurorVote.answer`` straight to ``answer_distance``, and a stage may not
import this module (I2), so every member of the implementation takes and returns
``record.StoredAnswer`` -- a tuple of plain dicts -- and parses it into these models on the way in.
``Call`` is what makes that parse a validation rather than a dictionary lookup.
"""

from collections.abc import Callable
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from dataforce.record import Record


class Call(BaseModel):
    """One tool call: which tool, and with what."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description=(
            "Which tool is called. δ weighs this first, and it is the half a dynamic "
            "choice list keeps an annotator from mistyping."
        ),
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "What it is called with, keyed as the tool's own `parameters` declares. "
            "Empty is a real answer: a tool that takes nothing is called with nothing."
        ),
    )


# An answer as this profile reads one: a set of calls, at most one per tool name. A tuple because a
# set of models is not JSON and the record stores this as an array; the *at most one per name* half
# is `label_names_one_tool_twice`'s to enforce, because a multiset would force δ to pairwise-match
# two calls to one tool and silently pick a pairing no juror proposed.
type Calls = tuple[Call, ...]


class Tool(BaseModel):
    """One entry of a record's own catalog: what could have been called, and with what."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description="The tool's name, which is what a call's `name` must be one of.",
    )
    description: str = Field(
        default="",
        description="What it does, in the source's words. What an annotator reads.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "This tool's own JSON Schema for its arguments, including which of them "
            "are `required`. What `answer_schema` constrains a call's arguments with."
        ),
    )


class AnswerConfig(BaseModel):
    """What a question permits and what collects the answer: the capture half of the config.

    It carried `control` and `max_calls` too, copied off the manifest, and nothing ever read
    either: every consumer of the ceiling reads the profile's own attribute, and the surface is
    declared so that composition can *refuse* a manifest naming a control these tags do not
    implement. A field with no reader is a guess (`ports.py`), so they were deleted rather than
    kept for a reader that might arrive -- whichever one does can add the field back with itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdicts: tuple[str, ...] = Field(
        ...,
        description=(
            "The permitted answers to a question. The record does not name them "
            "(Decision 22); this is where they are declared."
        ),
    )
    tags: str = Field(
        ...,
        description=(
            "The Label Studio fragment this half contributes: the verdict, and the "
            "correction gated behind it. Community tags only (Requirement 52)."
        ),
    )
    data: dict[str, Any] = Field(
        ...,
        description=(
            "The task-payload keys this half *owns*: `tool_names`, as the objects a "
            "dynamic choice list reads. Per record, because the catalog is, which is "
            "why a static `<Choice>` list cannot express it (Requirement 52)."
        ),
    )
    endorsing_verdict: str = Field(
        ...,
        description=(
            "Which of `verdicts` says the label as it stands is right. `curate` reads "
            "it rather than naming a value, so a fourth verdict stays one directory's "
            "edit (Decision 22); every other verdict leaves the label to a correction."
        ),
    )


class LabelCheck(NamedTuple):
    """One named defect the label can carry, and the predicate that finds it.

    Named for the defect rather than for the test, so a failure reads as what is wrong with the
    record. Every one of the five is provable by counting: no person decides any of them, which is
    what makes them `data_quality`'s and not `human_review`'s.
    """

    name: str  # the defect it finds; `params.invalid_counts` declares its count
    defect_in: Callable[[Record], bool]  # True when this record's label has that defect
