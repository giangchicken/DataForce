"""Axis 1: how content is read. Four members, and nothing more.

A modality knows how to turn a raw source item into typed parts, how to embed
those parts so near-duplicates can be found, where personal data is in them, and
how to show them to an annotator. It knows nothing about what an answer is, which
is why adding one does not multiply the profiles that already exist.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, runtime_checkable

from dataforce.shared.record import Part, Record, Span, UIControl, Versioned

__all__ = ["Detector", "Modality"]

# One detector over a record's parts. High recall is the job here; precision is
# the verifier's, in the stage. The result shape is uniform across modalities so
# that the redaction stage, its report, its vault and its gate are written once.
Detector = Callable[[list[Part]], list[Span]]


@runtime_checkable
class Modality(Versioned, Protocol):
    def load(self, raw: Any) -> list[Part]:
        """Turn one raw source item into ordered, typed content parts."""
        ...

    def embed(self, parts: list[Part]) -> Sequence[float]:
        """Turn content into a vector, for near-duplicate detection only."""
        ...

    def privacy_detectors(self) -> list[Detector]:
        """The high-recall detectors this kind of content needs."""
        ...

    def display_control(self, record: Record) -> UIControl:
        """The annotation-UI control that *displays* a record.

        Half of a composed config. A modality never emits the control that
        captures an answer -- that half belongs to the profile.
        """
        ...
