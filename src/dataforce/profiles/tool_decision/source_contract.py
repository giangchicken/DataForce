"""DEFINITION · a source contract: what this corpus calls things, from its manifest.

Every corpus-specific name the profile reads arrives through here, so no module spells
one. That is the difference between reading a second source and adding a branch: a
field called `llm_model` is a fact about one file, and a module that names it has
quietly become a module about that file.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest

__all__ = [
    "LEGACY_SYSTEM_PROMPT",
    "OPENAI_TOOLS",
    "SHAPES",
    "SourceContract",
    "read_source_contract",
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


def _declared(manifest: Manifest, key: str, inner: str) -> Any:
    """One value out of a mapping the manifest declares, or an error naming both keys."""
    block = manifest.require(key)
    if not isinstance(block, Mapping) or inner not in block:
        raise ConfigError(
            f"{manifest.name}: {key}.{inner} is not declared; {key} holds "
            f"{sorted(block) if isinstance(block, Mapping) else block!r}"
        )
    return block[inner]


def read_source_contract(manifest: Manifest) -> SourceContract:
    """One source's contract, from its manifest. Every missing key names itself."""
    shape = manifest.require("shape")
    if shape not in SHAPES:
        raise ConfigError(
            f"{manifest.name}: shape {shape!r} is not one of {list(SHAPES)}"
        )
    gold = manifest.declared.get("gold") or {}
    contract = SourceContract(
        name=manifest.name,
        shape=shape,
        roles=manifest.require("roles"),
        label_key=_declared(manifest, "label", "at"),
        meta=manifest.require("meta"),
        gold_from=gold.get("from", ""),
    )
    # so an undeclared target role fails here rather than once per record
    if not contract.restating_role:
        raise ConfigError(f"{manifest.name}: roles.{TARGET} is declared empty")
    return contract
