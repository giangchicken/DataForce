"""DEFINITION · the annotation flow: four phases over fifteen stages, named once.

These four names are the vocabulary the whole tree is arranged by. `pipeline/<phase>/`
holds the stages of one phase, `core/artifacts/<phase>.py` says what that phase's
artifacts must contain, and `profiles/<name>/<phase>.py` says what that phase asks of a
profile. Before this module they were four string literals repeated across three
places and a table in a document, and a name repeated in four places is a name that can
disagree with itself.

The stage range is part of what a phase is here, not decoration: a phase module states
its range in its own docstring and a guard checks the statement against this. A second
guard checks *this* against the core spec's stage table, so the document stays the
source and this stays a copy that cannot drift from it.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PHASES", "Phase"]


@dataclass(frozen=True)
class Phase:
    """One phase of the flow: its name, and the first and last stage it covers.

    Inclusive at both ends, because that is how the stage table reads and how a
    docstring states it -- `stages 0-4`, not `stages 0-5`.
    """

    name: str
    first_stage: int
    last_stage: int


PHASES: tuple[Phase, ...] = (
    Phase("data_quality", 0, 4),
    Phase("ai_review", 5, 6),
    Phase("human_review", 7, 11),
    Phase("release", 12, 14),
)
