"""A resolved run: one modality, one profile, and the policy that chose them.

This is the composition root -- the one place a concrete implementation is named.
Everything under `modalities/`, `profiles/`, `pipeline/` and `shared/` is handed
already-parsed declarations, so it works from any working directory; turning the
committed files into those declarations happens here, once, at the top.

The policy paths are why an `Engine` is an object rather than a pair of arguments.
Every run records the SHA-256 of each file it read, and that is what replaces DVC's
declared dependencies as the thing that makes a number attributable to a run.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dataforce.declared.manifest import manifest_path, read_manifest
from dataforce.declared.prompts import prompt_path, read_prompt
from dataforce.declared.thresholds import max_answer_cardinality
from dataforce.modalities.base import Modality
from dataforce.modalities.text import MANIFEST_NAME as TEXT_MANIFEST
from dataforce.modalities.text import TextModality
from dataforce.profiles.base import Profile
from dataforce.profiles.tool_decision import MANIFEST_NAME as TOOL_DECISION_MANIFEST
from dataforce.profiles.tool_decision import ToolDecisionProfile
from dataforce.shared.record import Record
from dataforce.shared.registry import Registry

__all__ = [
    "PROMPTS_DIR",
    "Engine",
    "build_records",
    "open_engine",
    "text_modality",
    "tool_decision_profile",
]

# Where templates live under a config root. A `prompt_version` is the path below this.
PROMPTS_DIR = "prompts"


@dataclass(frozen=True)
class Engine:
    """One resolved pair, the registry it resolved through, and what it read."""

    modality: Modality
    profile: Profile
    registry: Registry
    # Every policy file this engine read. `artifacts.run_manifest` digests them,
    # which is also why they are paths here and not digests: computing one needs a
    # file reader, and the reader is the layer that persists things.
    policy: tuple[Path, ...]

    @property
    def producer(self) -> dict[str, str]:
        """Both axes as `name@version`, the way an artifact records them."""
        return {
            "modality": f"{self.modality.name}@{self.modality.version}",
            "profile": f"{self.profile.name}@{self.profile.version}",
        }


def text_modality(*, config_root: Path) -> TextModality:
    """The `text` modality, from the manifest that declares what it is."""
    return TextModality(
        read_manifest(manifest_path("modalities", TEXT_MANIFEST, root=config_root))
    )


def tool_decision_profile(*, config_root: Path, params: Path) -> ToolDecisionProfile:
    """The `tool_decision` profile, with the question template and ceiling it declares."""
    declared = read_manifest(
        manifest_path("profiles", TOOL_DECISION_MANIFEST, root=config_root)
    )
    return ToolDecisionProfile(
        declared,
        question_template=read_prompt(
            declared.require("prompts")["question"], root=config_root / PROMPTS_DIR
        ),
        ceiling=max_answer_cardinality(params=params),
    )


def open_engine(
    *,
    profile: str,
    modality: str | None = None,
    config_root: Path,
    params: Path,
) -> Engine:
    """Resolve one pair by name, or refuse to.

    Both axes are built and registered, then resolved through the registry -- so an
    unknown name and a pair that does not compose both fail here, with the messages
    registration already gives, and before anything opens a source file.

    `modality` is an assertion rather than a choice: a profile declares which one it
    composes with, and naming a different one is the hard stop. Leaving it out takes
    the profile at its word, which is what a command with no `--modality` does.
    """
    registry = Registry()
    built = tool_decision_profile(config_root=config_root, params=params)
    registry.register_modality(text_modality(config_root=config_root))
    registry.register_profile(built)

    # Resolving before reading the prompt path is what makes a mismatched pair fail
    # with the registry's message rather than a missing-file one.
    resolved = registry.profile(profile, modality=modality)
    composed = resolved.modality
    return Engine(
        modality=registry.modality(composed),
        profile=resolved,
        registry=registry,
        policy=(
            manifest_path("modalities", composed, root=config_root),
            manifest_path("profiles", profile, root=config_root),
            prompt_path(built.question_prompt, root=config_root / PROMPTS_DIR),
            params,
        ),
    )


def build_records(
    engine: Engine, raw_items: Iterable[Mapping[str, Any]]
) -> Iterator[Record]:
    """Every raw item as a canonical record, through the resolved pair.

    No path is named and no file is opened: raw mappings in, records out. What a raw
    item must already carry -- its provenance among it -- is the profile's contract,
    and stamping that off a source file is stage 0's job.
    """
    for raw in raw_items:
        yield engine.profile.build_record(raw, engine.modality.content_parts(raw))
