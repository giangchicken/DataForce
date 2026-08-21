"""DEFINITION · every shape this profile's data has: a tool, a catalog, an answer.

A **tool** is an OpenAI function object -- a name, one verbatim `description` carrying
all usage guidance, and a JSON Schema of parameters. That is the source of truth; the
catalog text a person reads is a rendering of it. A **catalog** is the tools one record
offers, in the order it offers them. An **answer** is an array of **calls**, and a call
is a name *and* the arguments it is called with: `ANSWER_SCHEMA` is the answer *type*,
which choosing this profile already settles, and `answer_schema_for` is one record's
answer *space*, built from its own catalog -- requirement 5's constraint, which the jury
hands straight to `complete_structured`, and which is why no stage validates an answer
against a catalog.

Nothing here is stored on a record. Requirement 71: the space is derived at the moment
one is needed, because the record already carries the catalog both the names and the
argument schemas come from, and a stored copy is a second thing that can disagree with
the first.

Shapes only, and all of them here rather than one per call site: a change to any is
then a visible decision about the others. Every conversion of them is `utils.py` --
rendering a catalog and reading it back, the OpenAI wire form, the fingerprint that
makes two records the same scenario. The distance between two answers and the consensus
of several are `answer.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ANSWER_SCHEMA", "Catalog", "Gap", "Tool", "answer_schema_for"]


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


# The answer *type*, which holds whatever record an answer is about: an array of calls,
# each a name and the arguments it is called with. `arguments` is optional because a
# tool that takes none is called with none -- requirement 72 counts two argument-less
# calls as agreeing, so absent and `{}` mean the same thing.
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "arguments": {"type": "object"},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}


def answer_schema_for(catalog: Catalog) -> dict[str, Any]:
    """One record's answer space: the calls its own catalog permits, and no others.

    `oneOf` per tool with the name as a single-value `const`, so a name and its
    arguments are constrained *together*: `SendStatement` carrying `LookupBalance`'s
    arguments is outside the space, which an `enum` of names beside a free-form
    argument object could not say. Each branch's `arguments` is that tool's own
    `parameters`, which the catalog already carries.

    Materialised where one is needed -- the jury's `complete_structured` call,
    pull-time validation of a human correction -- and persisted nowhere.

    An empty catalog permits exactly one answer, the empty array. Spelled `maxItems`
    because an empty `oneOf` is not a schema.
    """
    if not catalog.tools:
        return {"type": "array", "maxItems": 0}
    return {
        "type": "array",
        "items": {
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "name": {"const": tool.name},
                        "arguments": tool.parameters or {"type": "object"},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                }
                for tool in catalog.tools
            ]
        },
    }
