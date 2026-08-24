"""DEFINITION · the Profile protocol; Answer, AnswerConfig and LabelCheck, opaque.

Fourteen members, closed. The three named types are aliases here and concrete pydantic models in
an implementation's ``schema.py`` (Requirement 47). This module imports no implementation of its
own axis (I16).
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from dataforce.record import Part, Record

# Opaque on purpose, for the reason `modalities/base.py` states: the base names the type so a
# signature can use it, and `tool_decision/schema.py` says what is inside one. `Answer` is the
# sharpest case -- what an answer *is* is the whole of what a profile declares, so a base that
# described one would have picked the task for every profile after this one.
type Answer = Any
type AnswerConfig = Any
type LabelCheck = Any


class Profile(Protocol):
    """One dataset task: what an answer is, how two answers differ, what makes one invalid."""

    name: str  # "tool_decision" -- from the manifest filename
    version: str  # stamped into every record's provenance; a string, never a number
    modality: str  # the pair this profile composes with; a mismatch hard-stops

    def answer_schema(self, record: Record) -> dict[str, Any]:
        """This record's permitted answers: `oneOf` per offered tool. Never persisted."""
        ...

    def answer_config(self) -> AnswerConfig:
        """How an answer is controlled: cardinality ceiling, argument handling."""
        ...

    def build_record(self, item: Mapping[str, Any], parts: Sequence[Part]) -> Record:
        """One source item into one record. The only place a source shape is read."""
        ...

    def label_checks(self) -> list[LabelCheck]:
        """The checks that need no opinion, each named for the defect it finds."""
        ...

    def answer_distance(self, a: Answer, b: Answer) -> float:
        """δ: 0.0 identical, 1.0 unrelated. Name-first, soft over arguments. `δ(∅, ∅) = 0`."""
        ...

    def vote_consensus(self, votes: Sequence[Answer], record: Record) -> Answer | None:
        """The panel's answer; `[]` where it agreed on none; None where none is defensible."""
        ...

    def question_text(self, record: Record) -> str:
        """What an annotator is asked, in their language. No model output may appear in it."""
        ...

    def answer_from_response(
        self, result: Sequence[Mapping[str, Any]], record: Record
    ) -> Answer | None:
        """The corrected answer out of one annotation's control values; None if it does not
        validate. Called only where the verdict is `incorrect`. The inverse of the capture half."""
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
