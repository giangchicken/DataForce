"""DEFINITION · what an answer to this profile looks like, at both levels.

The profile-level schema is the shape of any answer this profile produces: an array of
tool names. One record's answer space is that shape drawn from the record's own
catalog, and the `enum` is requirement 5's constraint -- the jury hands it straight to
`complete_structured`, which is why no stage validates an answer against a catalog.

Shapes only, and both of them here rather than one here and one at a call site: a
change to either is then a visible decision about the other. What the pipeline
*computes* from an answer -- the distance between two, the consensus of several, the
training example one becomes -- is `answer.py`.
"""

from __future__ import annotations

from typing import Any

from dataforce.profiles.tool_decision.tool_schema import Catalog

__all__ = ["ANSWER_SCHEMA", "answer_space"]

# What the profile declares as its `answer_schema`, so the shape holds whatever record
# an answer is about.
ANSWER_SCHEMA: dict[str, Any] = {"type": "array", "items": {"type": "string"}}


def answer_space(catalog: Catalog) -> dict[str, Any]:
    """One record's answer space: `ANSWER_SCHEMA`, closed over its own catalog."""
    return {"type": "array", "items": {"type": "string", "enum": list(catalog.names)}}
