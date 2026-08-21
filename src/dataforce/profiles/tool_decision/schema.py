"""DEFINITION · every shape this profile's data has: a tool, a catalog, an answer.

A **tool** is an OpenAI function object -- a name, one verbatim `description` carrying
all usage guidance, and a JSON Schema of parameters. That is the source of truth; the
catalog text a person reads is a rendering of it. A **catalog** is the tools one record
offers, in the order it offers them. An **answer** is an array of names drawn from that
catalog: `ANSWER_SCHEMA` is the shape of any answer this profile produces, and
`answer_space` is one record's, with its own catalog as the `enum` -- requirement 5's
constraint, which the jury hands straight to `complete_structured`, and which is why no
stage validates an answer against a catalog.

Shapes only, and all of them here rather than one per call site: a change to any is
then a visible decision about the others. Every conversion of them is `utils.py` --
rendering a catalog and reading it back, the OpenAI wire form, the fingerprint that
makes two records the same scenario. The distance between two answers and the consensus
of several are `answer.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ANSWER_SCHEMA", "Catalog", "Gap", "Tool", "answer_space"]


@dataclass(frozen=True)
class Gap:
    """Something the text implies that the schema could not be given.

    The parser's own account of what it could not recover. A format reader that returns
    less than it was given and says nothing is the failure `utils.py` is arranged
    against.
    """

    tool: str
    parameter: str | None
    kind: str
    evidence: str


@dataclass(frozen=True)
class Tool:
    """One tool, in OpenAI function-calling form."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def properties(self) -> dict[str, Any]:
        props: dict[str, Any] = self.parameters.get("properties") or {}
        return props

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(self.parameters.get("required") or ())


@dataclass(frozen=True)
class Catalog:
    """The tools one record offers, in the order the record offers them."""

    tools: tuple[Tool, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    @property
    def is_empty(self) -> bool:
        return not self.tools


# What the profile declares as its `answer_schema`, so the shape holds whatever record
# an answer is about.
ANSWER_SCHEMA: dict[str, Any] = {"type": "array", "items": {"type": "string"}}


def answer_space(catalog: Catalog) -> dict[str, Any]:
    """One record's answer space: `ANSWER_SCHEMA`, closed over its own catalog."""
    return {"type": "array", "items": {"type": "string", "enum": list(catalog.names)}}
