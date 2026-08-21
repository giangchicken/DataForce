"""DEFINITION · every shape this profile's data has: a source contract, a tool, a
catalog, an answer.

A **source contract** is what one corpus calls things, as its own manifest declares them,
so no module below spells a field name belonging to one file. That is the difference
between reading a second source and adding a branch: a field called `llm_model` is a fact
about one file, and a module that names it has quietly become a module about that file.

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
reading the contract out of a manifest, rendering a catalog and reading it back, the
OpenAI wire form, the hash that makes two records the same scenario, and the distance
between two answers, which is here rather than in a phase module because three stages in
two phases compute it. The consensus of several answers is `ai_review.py`, because one
stage asks for it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from dataforce.core.errors import ConfigError

__all__ = [
    "ANSWER_SCHEMA",
    "LEGACY_SYSTEM_PROMPT",
    "OPENAI_TOOLS",
    "SHAPES",
    "Catalog",
    "SourceContract",
    "Tool",
    "answer_schema_for",
]


# The catalog is data, in a `tools` array. Nothing parses a prompt.
OPENAI_TOOLS = "openai_tools"
# No `tools` key: the catalog is rendered into the instruction turn. What the first
# corpus holds, so it is read once on the way in and converted.
LEGACY_SYSTEM_PROMPT = "legacy_system_prompt"
SHAPES = (OPENAI_TOOLS, LEGACY_SYSTEM_PROMPT)

TOOLS_KEY = "tools"


# The answer is stated twice in a source like this one: once as a field, and once as
# the content of the turn the model is trained to produce. The second place is not
# declared, because `roles.target` already names that turn -- the target role *is*
# where the answer is restated, and a second key saying so could disagree with it.
TARGET = "target"


@dataclass(frozen=True)
class SourceContract:
    """One source's shape and vocabulary, as its manifest declares them."""

    name: str
    shape: str
    roles: Mapping[str, Any]
    label_key: str
    meta: Mapping[str, str]
    gold_from: str

    def role_name(self, part: str) -> str:
        """What this source calls one of the pipeline's roles."""
        try:
            named = self.roles[part]
        except KeyError:
            raise ConfigError(
                f"{self.name}: no role declared for {part!r}; "
                f"declared: {sorted(self.roles)}"
            ) from None
        return str(named[0] if isinstance(named, list) else named)

    def field_name(self, meaning: str) -> str:
        """What this source calls one of the fields the pipeline reads."""
        try:
            return self.meta[meaning]
        except KeyError:
            raise ConfigError(
                f"{self.name}: no source field declared for {meaning!r}; "
                f"declared: {sorted(self.meta)}"
            ) from None

    def read_label(self, raw: Mapping[str, Any]) -> Any:
        """The answer, from the meta field this source states it in."""
        meta = raw.get("meta")
        return meta.get(self.label_key) if isinstance(meta, Mapping) else None

    @property
    def restating_role(self) -> str:
        """The turn that restates the answer: the target, by definition."""
        return self.role_name(TARGET)


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
