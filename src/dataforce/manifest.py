"""DEFINITION · Manifest -- one axis's declaration, already parsed.

Identity comes from the manifest's filename and never from a class body (Requirement 40).

**One type for both axes**, because both files answer the same three questions -- who am I, which
version am I, and what do I declare -- and only the last one differs. Splitting it would give two
types with two fields in common and one consumer each, which is a split AGENTS.md asks not to
make until a second consumer needs half of it.

**What each axis declares stays a mapping.** ``embedding`` is the modality's, ``roles``, ``label``
and ``answer_control`` are the profile's, and typing them here would put the profile's vocabulary
in a module the modality also imports -- the leakage Requirement 47 keeps out of ``base.py``. The
implementation that reads a key is the one that knows what it means.

Reading the file is the edge's (``edge/policy.py``): the filename is the identity, and only
something holding a path can see a filename. This type is what it returns, and an engine can be
built by handing one over with no filesystem anywhere near it.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Manifest(BaseModel):
    """One ``config/<axis>/<name>.yaml``, parsed, with its filename as its identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description=(
            "The identity, taken from the filename. The `name:` key inside the file "
            "must agree with it, and the reader is what checks that."
        ),
    )
    version: str = Field(
        ...,
        description=(
            "Stamped into every record's provenance, so it is a string and not a "
            "number: `1` and `1.0` are the same number and two different versions."
        ),
    )
    modality: str | None = Field(
        default=None,
        description=(
            "The pair a profile composes with; a run naming a different one raises. "
            "Null on a modality's own manifest, whose `name` is that pair."
        ),
    )
    declarations: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Everything else the file says, verbatim and unread: the axis "
            "implementation that needs a key is the one that knows what it means."
        ),
    )
