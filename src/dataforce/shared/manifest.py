"""What an implementation *is*, declared rather than assigned.

A modality and a profile each stamp their `name@version` onto every record they touch,
through `producer`. That makes the version a claim about how a dataset was made, and a
claim edited as a class attribute is one no review ever sees. So identity is a line in
`config/<axis>/<name>.yaml`, next to the other things about an implementation that are
declarations and not behaviour: which modality a profile composes with, which prompts
it asks, what its source is shaped like, and what that source's field names mean.

The file's own name is the identity, checked against the `name` inside it, so a manifest
cannot be copied to a new file and left claiming to be the old one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_yaml

from dataforce.shared.errors import ConfigError

__all__ = ["AXES", "CONFIG", "Manifest", "load", "names"]

CONFIG = Path("config")
AXES = ("modalities", "profiles")


@dataclass(frozen=True)
class Manifest:
    """One implementation's declaration. `declared` is the rest of the file, verbatim."""

    name: str
    version: str
    declared: Mapping[str, Any]

    def require(self, key: str) -> Any:
        """One declared value, or an error naming what the file does hold."""
        try:
            return self.declared[key]
        except KeyError:
            raise ConfigError(
                f"{self.name}: nothing declares {key!r}; the manifest holds "
                f"{sorted(self.declared)}"
            ) from None


def _text(manifest: Mapping[str, Any], key: str, where: Path) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"{where}: {key} must be a non-empty string, got {value!r} -- "
            "an unquoted version in YAML is a number, and a version is not a number"
        )
    return value


def load(axis: str, name: str, *, root: Path = CONFIG) -> Manifest:
    """One implementation's manifest, by axis and name."""
    if axis not in AXES:
        raise ConfigError(f"no such axis {axis!r}; there are two: {list(AXES)}")
    path = root / axis / f"{name}.yaml"
    if not path.is_file():
        raise ConfigError(
            f"no manifest at {path}; {axis} declared here: {names(axis, root=root)}"
        )
    declared = read_yaml(path) or {}
    if not isinstance(declared, Mapping):
        raise ConfigError(
            f"{path}: a manifest is a mapping, got {type(declared).__name__}"
        )
    declared_name = _text(declared, "name", path)
    if declared_name != name:
        raise ConfigError(
            f"{path} declares the name {declared_name!r}; a manifest's filename is "
            "its identity, so the two cannot disagree"
        )
    return Manifest(
        name=declared_name,
        version=_text(declared, "version", path),
        declared={key: value for key, value in declared.items() if key != "name"},
    )


def names(axis: str, *, root: Path = CONFIG) -> list[str]:
    """Every implementation declared on one axis."""
    folder = root / axis
    return (
        sorted(path.stem for path in folder.glob("*.yaml")) if folder.is_dir() else []
    )
