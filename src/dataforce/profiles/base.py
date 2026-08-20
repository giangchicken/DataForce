"""Axis 2: what an answer is.

Everything the pipeline does with disagreement -- cohesion, corpus conflict, the
four triage buckets, Krippendorff's alpha, adjudication, juror calibration -- is
expressible in three of the members below: the answer type, `delta`, and
`consensus`. That is why the core can be generic without being a framework.

`answer_schema` may be built per record: a profile whose answer space depends on
the record returns a schema closed over it. The jury passes it straight to
`complete_structured`, which is why answer-space validation is not pipeline code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from dataforce.shared.record import Part, Record, UIControl, Versioned

__all__ = ["Answer", "Profile"]

# Whatever this profile says an answer is: a set of tool names, one class label, a
# list of spans, an ordering, a string. Only the profile may look inside one.
Answer = Any


@runtime_checkable
class Profile(Versioned, Protocol):
    modality: str
    answer_schema: dict[str, Any]

    def adapt(self, raw: Any, parts: list[Part]) -> Record:
        """Turn a raw source item and its parts into a canonical record.

        Preserves every field it does not own: what looks like noise now is what
        a later question turns out to need.
        """
        ...

    def delta(self, a: Answer, b: Answer) -> float:
        """Distance between two answers. A metric -- rule 1, proved by the profile.

        `delta(a, a) == 0`, symmetric, in `[0, 1]`, never NaN -- including on the
        empty answer, which for some corpora is a third of the records. Nothing
        here checks it: see the core spec's § *Rules a profile must satisfy* for
        why, and for what a profile that breaks it costs.
        """
        ...

    def consensus(self, answers: list[Answer]) -> Answer | None:
        """One answer from several, deterministically.

        A profile with no defensible consensus -- free-text generation is the
        honest example -- returns None for every input, including unanimous input.
        That is a declaration rather than a failure of rule 2: it bars the profile
        from the optional consensus tier and nothing else. Triage still works on
        such a profile, because triage needs only `delta`.
        """
        ...

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        """Checks a record either passes or provably fails, by name.

        Provably: no judgment. If telling right from wrong needs a person, it is
        an annotation task, not a validity check.
        """
        ...

    def question(self, record: Record, focus: str) -> str:
        """One focused, answerable question about this record."""
        ...

    def answer_control(self, record: Record) -> UIControl:
        """The annotation-UI control that *captures* an answer.

        The other half of a composed config. Constrained to this record's answer
        space wherever the UI can express it, and asserted again at pull time.
        """
        ...

    def group_key(self, record: Record) -> str:
        """What makes two records the same scenario, so they cannot straddle a split.

        A field that is unique per record is not a group key, and saying so is the
        profile's job -- with a measurement, not an assumption.
        """
        ...

    def export(self, record: Record) -> dict[str, Any]:
        """One training example, in the shape this profile's trainer expects."""
        ...
