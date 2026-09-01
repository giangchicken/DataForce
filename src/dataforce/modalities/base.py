"""DEFINITION · the Modality protocol; Detector, opaque.

Five members, closed. The named type is an alias here and a concrete pydantic model in an
implementation's ``schema.py`` (Requirement 47). This module imports no implementation of its own
axis (I16) -- that is what keeps the protocol a protocol.

**No member emits an annotation tool's markup** (Requirement 31). How a conversation is *shown* is
Label Studio's config grammar, and this axis reads content rather than speaking to the tool that
displays it; a ``Part`` already carries ``role`` and ``text``, so the adapter that owns the tool
composes the fragment from ``record.content`` and asks this protocol for nothing. That is what lets a
modality be added without a page layout in it.

**The identity is prefixed, and that is what lets one object be both axes.** A profile is a module
inside a concept and says so by subclassing it (§ *The two axes*), so one instance answers this
protocol and ``Profile`` at once -- and a bare ``name`` on both would be one attribute where a record
needs two. ``modality_name`` and ``profile_name`` cannot collapse, which is what keeps
``Branch(modality=…, profile=…)`` able to say which concept read a record and which module answered
it. The two protocols stay separate for the same reason: this one is about reading content and that
one is about answering, and a modality member may not answer for a profile one.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from dataforce.record import Part

# Opaque on purpose. The base names this type so a member's signature can say what it takes and
# returns; what is inside one is `text2text/schema.py`'s to say. Naming the model here is the
# import I16 forbids, and describing it here would make the protocol a description of its single
# implementation.
type Detector = Any


class Modality(Protocol):
    """One input→output pair: how its content is read, embedded and scanned."""

    modality_name: str  # "text2text" -- the manifest filename, never a class body
    modality_version: (
        str  # stamped into every record's provenance; a string, never a number
    )

    def content_parts(self, item: Mapping[str, Any]) -> list[Part]:
        """One source item's turns, as ordered parts. Text verbatim, media by reference."""
        ...

    def embedding(self, parts: Sequence[Part]) -> list[float]:
        """A vector for near-duplicate grouping, from the model the manifest names."""
        ...

    def personal_data_detectors(self) -> list[Detector]:
        """The high-recall first layer: one scan per class of personal data."""
        ...
