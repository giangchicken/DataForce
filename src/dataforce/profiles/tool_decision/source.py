"""What the source is shaped like and what its own field names mean, read from the manifest.

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

__all__ = ["LEGACY_SYSTEM_PROMPT", "OPENAI_TOOLS", "SHAPES", "SourceContract"]

# The catalog is data, in a `tools` array. Nothing parses a prompt.
OPENAI_TOOLS = "openai_tools"
# No `tools` key: the catalog is rendered into the instruction turn. What the first
# corpus holds, so it is read once on the way in and converted.
LEGACY_SYSTEM_PROMPT = "legacy_system_prompt"
SHAPES = (OPENAI_TOOLS, LEGACY_SYSTEM_PROMPT)

TOOLS_KEY = "tools"


@dataclass(frozen=True)
class SourceContract:
    """One source's shape and vocabulary, as its manifest declares them."""

    shape: str
    roles: Mapping[str, Any]
    label_at: tuple[str, ...]
    label_restated_in: str
    meta: Mapping[str, str]
    gold_from: str

    @classmethod
    def of(cls, manifest: Manifest) -> SourceContract:
        shape = manifest.require("shape")
        if shape not in SHAPES:
            raise ConfigError(
                f"{manifest.name}: shape {shape!r} is not one of {list(SHAPES)}"
            )
        label = manifest.require("label")
        gold = manifest.declared.get("gold") or {}
        return cls(
            shape=shape,
            roles=manifest.require("roles"),
            label_at=tuple(label["at"].split(".")),
            label_restated_in=label["restated_in"],
            meta=manifest.require("meta"),
            gold_from=gold.get("from", ""),
        )

    def role(self, part: str) -> str:
        """What this source calls one of the pipeline's roles."""
        try:
            named = self.roles[part]
        except KeyError:
            raise ConfigError(
                f"no role declared for {part!r}; declared: {sorted(self.roles)}"
            ) from None
        return str(named[0] if isinstance(named, list) else named)

    def field(self, meaning: str) -> str:
        """What this source calls one of the fields the pipeline reads."""
        try:
            return self.meta[meaning]
        except KeyError:
            raise ConfigError(
                f"no source field declared for {meaning!r}; declared: {sorted(self.meta)}"
            ) from None

    def label_of(self, raw: Mapping[str, Any]) -> Any:
        """The answer, from wherever this source states it."""
        found: Any = raw
        for step in self.label_at:
            if not isinstance(found, Mapping):
                return None
            found = found.get(step)
        return found

    @property
    def renders_the_catalog_into_the_prompt(self) -> bool:
        return self.shape == LEGACY_SYSTEM_PROMPT
