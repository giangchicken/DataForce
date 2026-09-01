"""DEFINITION · the Profile protocol; Answer, AnswerConfig and LabelCheck, opaque.

Fifteen members, closed. The three named types are aliases here and concrete pydantic models in
an implementation's ``schema.py`` (Requirement 47). This module imports no implementation of its
own axis (I16).

**``modality`` was the sixteenth and is gone, because the containment is a base class now.** It
declared *which concept this profile composes with* as a string off the profile's own manifest, and
an implementation subclassing its concept (§ *The two axes*) inherits ``modality_name`` from it
instead -- one attribute, one writer, and one that cannot disagree with the object that actually read
the content. The manifest key it came from stays: ``modality:`` is what tells the composition root
which manifest to open, and ``edge/bootstrap.py`` still reads it there.

**The identity is prefixed for the same reason.** One instance answers this protocol and
``Modality`` at once, so a bare ``name`` on both would be one attribute where a record needs two.
The two protocols stay separate: this one is about what an answer is, that one about how content is
read, and inheritance may not let a member of one answer for the other.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from dataforce.record import Part, Provenance, Record

# Opaque on purpose, for the reason `modalities/base.py` states: the base names the type so a
# signature can use it, and `tool_decision/schema.py` says what is inside one. `Answer` is the
# sharpest case -- what an answer *is* is the whole of what a profile declares, so a base that
# described one would have picked the task for every profile after this one.
type Answer = Any
type AnswerConfig = Any
type LabelCheck = Any


@dataclass(frozen=True)
class AnnotationResponse:
    """What one annotation said, decoded by the profile that composed the controls it came from.

    Concrete here rather than opaque, which is the opposite of the three aliases above: what an
    *answer* is belongs to the profile, and what an annotation *says* is the same three things for
    every profile there could be -- a chosen verdict, a correction where the verdict was that the
    label is wrong, and free text. Only the second of the three is the profile's own vocabulary,
    and it is typed ``Answer`` for exactly that reason. ``ports.JurorAnswer`` is the same shape of
    thing on the other side of the engine: a small value carrying what one respondent said.

    **The two ``None``s do not mean the same thing.** A ``verdict`` of ``None`` is an annotation
    that answered nothing this profile offers -- there is no answer to record. A
    ``corrected_value`` of ``None`` is either *no correction was called for* or *the correction did
    not validate*, and Requirement 49 says the second is never coerced into something that does.
    The store keeps the control values verbatim, so what a person actually typed survives either
    way; what the record carries is the conclusion.
    """

    verdict: (
        str | None
    )  # which of `answer_config().verdicts`; None if the annotation chose none
    corrected_value: (
        Answer | None
    )  # the correction, where one was called for and it validates
    note: str | None  # the annotator's free text, verbatim; never parsed


class Profile(Protocol):
    """One dataset task: what an answer is, how two answers differ, what makes one invalid."""

    profile_name: str  # "tool_decision" -- from the manifest filename
    profile_version: (
        str  # stamped into every record's provenance; a string, never a number
    )

    def answer_schema(self, record: Record) -> dict[str, Any]:
        """This record's permitted answers: `oneOf` per offered tool. Never persisted."""
        ...

    def answer_config(self, record: Record) -> AnswerConfig:
        """The capture half: the fragment that collects an answer, and the task data it owns.

        Takes the record because half of what it returns is per record: the catalog an annotator
        chooses from is this record's, and a Label Studio project holds
        one config for every task in it, so the names travel as *data* and not as markup."""
        ...

    def build_record(
        self, item: Mapping[str, Any], parts: Sequence[Part], provenance: Provenance
    ) -> Record:
        """One source item into one record. The only place a source shape is *validated*."""
        ...

    def label_checks(self) -> list[LabelCheck]:
        """The checks that need no opinion, each named for the defect it finds."""
        ...

    def redact_label(self, label: Answer, replacements: Mapping[str, str]) -> Answer:
        """The label with every value `pii_check` replaced in the content replaced too."""
        ...

    def answer_distance(self, a: Answer, b: Answer) -> float:
        """δ: 0.0 identical, 1.0 unrelated. Name-first, soft over arguments. `δ(∅, ∅) = 0`."""
        ...

    def answer_is_permitted(self, answer: Answer, record: Record) -> bool:
        """Does this answer belong to this record's answer space: the schema, and what it
        cannot say. `answer_schema` materialises the space and a schema cannot express *at most
        one call per tool name*, so the member is the whole question and not the schema alone."""
        ...

    def vote_consensus(self, votes: Sequence[Answer], record: Record) -> Answer | None:
        """The panel's answer; `[]` where it agreed on none; None where none is defensible."""
        ...

    def question_text(self, record: Record) -> str:
        """What an annotator is asked, in their language. No model output may appear in it."""
        ...

    def annotation_response(
        self, result: Sequence[Mapping[str, Any]], record: Record
    ) -> AnnotationResponse:
        """What one annotation said: its verdict, its correction where it validates, its note.

        The inverse of the capture half, and the whole of it -- the half emits three controls, so
        its inverse answers for three. **The only place an annotation tool's shape is read**
        (Requirement 49), the way `build_record` is the only place a source shape is read."""
        ...

    def jury_slots(self, record: Record) -> Mapping[str, Any]:
        """What the jury prompt's slots are filled with. The template is policy's, not this."""
        ...

    def scenario_hash(self, record: Record) -> str:
        """What must not straddle a split -- two records of one scenario share it."""
        ...

    def training_example(self, record: Record) -> Mapping[str, Any]:
        """The record in the shape a trainer expects."""
        ...
