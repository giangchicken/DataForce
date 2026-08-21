"""The one shape that flows through every stage, and the vocabulary around it.

Each stage adds fields to a record and removes none, so this module holds the
parts of that shape no stage owns: the typed content parts, privacy spans, and
the annotation-UI control both contracts return.

Three things here could not be retrofitted without touching all fifteen stages,
which is why they are settled before the first stage exists: content is an
ordered list of typed parts rather than a string, non-text media is held by
reference and checksum rather than inlined, and `rid` is derived from the parts'
digests rather than from raw bytes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal, NewType, Protocol

from agent_toolkit.string_utils import compute_hash
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MEDIA_TYPES",
    "MediaPart",
    "Part",
    "Producer",
    "Record",
    "Source",
    "Span",
    "TextPart",
    "UIControl",
    "Versioned",
    "compute_rid",
    "stamp",
]

RID_LENGTH = 16
MEDIA_TYPES = frozenset({"image", "audio", "video"})

# A Label Studio labeling-config fragment. Distinct from str so the two halves of
# a composed config -- the modality's display control, the profile's answer
# control -- cannot be confused with arbitrary text.
UIControl = NewType("UIControl", str)


class TextPart(BaseModel):
    """Text, inline. The field is `type`, the word every provider's API uses."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    role: str
    text: str


class MediaPart(BaseModel):
    """Non-text content, by reference and checksum -- never inlined.

    Extra keys are allowed because per-modality metadata rides here: `duration_s`
    on audio, `transcript_part` where a transcript was split, frame geometry on
    video. What none of them may carry is the bytes.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["image", "audio", "video"]
    role: str
    uri: str
    sha256: str


Part = Annotated[TextPart | MediaPart, Field(discriminator="type")]


class Span(BaseModel):
    """One typed span over one content part -- the uniform privacy result shape.

    What the locator indexes is the modality's business: character offsets in
    text, a time range in audio, a box in a frame. The redaction stage, its
    report, its vault and its gate are written once against this shape.
    """

    model_config = ConfigDict(extra="forbid")

    part: int
    type: str
    locator: dict[str, Any]


class Source(BaseModel):
    """Which file this record came from, and where in it."""

    model_config = ConfigDict(extra="forbid")

    file_sha256: str
    offset: int
    ingested_at: str


class Producer(BaseModel):
    """Which code produced this record, as `name@version` on both axes."""

    model_config = ConfigDict(extra="forbid")

    modality: str
    profile: str


class Versioned(Protocol):
    """A named, versioned implementation. Both contracts are one."""

    name: str
    version: str


def stamp(modality: Versioned, profile: Versioned) -> Producer:
    """Record the resolved pair, so a run cannot silently change what made a dataset."""
    return Producer(
        modality=f"{modality.name}@{modality.version}",
        profile=f"{profile.name}@{profile.version}",
    )


def compute_rid(parts: Sequence[Part]) -> str:
    """Derive a record id from its content parts, in order.

    Order within a record is content -- a system turn and a user turn saying the
    same thing are not the same record -- while order *between* records is not, so
    re-ingesting a shuffled source yields byte-identical ids.

    Text contributes its text and media its checksum, so what an identity is made of
    is one rule whatever the modality that read the parts.
    """
    material = "\n".join(
        f"{p.type}:{p.role}:{p.text if isinstance(p, TextPart) else p.sha256}"
        for p in parts
    )
    return compute_hash(material, "sha256")[:RID_LENGTH]


class Record(BaseModel):
    """One record, at any point in the pipeline.

    Everything a later stage writes defaults to absent, because a stage adds
    fields and removes none: a `loaded.jsonl` row and a `curated.jsonl` row are
    the same type at two points in its life. The blocks later stages own are
    declared as mappings here and given their shape by the stage that fills them.
    """

    model_config = ConfigDict(extra="forbid")

    rid: str
    source: Source
    producer: Producer
    content: list[Part]

    answer_space: dict[str, Any] | None = None
    label: Any = None
    meta: dict[str, Any] = Field(default_factory=dict)

    parse_status: Literal["ok", "unparsed"] = "ok"
    failed_checks: list[str] = Field(default_factory=list)

    privacy: dict[str, Any] | None = None
    dup_cluster_id: str | None = None
    dup_cluster_size: int | None = None
    is_representative: bool | None = None
    group_key: str | None = None

    jury: dict[str, Any] | None = None
    triage: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    split: Literal["train", "val", "test"] | None = None
