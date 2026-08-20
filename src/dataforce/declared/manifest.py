"""One implementation's manifest, read off disk.

The file's own name is the identity, checked against the `name` inside it, so a manifest
cannot be copied to a new file and left claiming to be the old one. What a manifest
holds once read is `shared/manifest.py`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from agent_toolkit.file_utils import read_yaml

from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest

__all__ = ["AXES", "manifest_path", "names", "read_manifest"]

AXES = ("modalities", "profiles")


def _text(manifest: Mapping[str, object], key: str, where: Path) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"{where}: {key} must be a non-empty string, got {value!r} -- "
            "an unquoted version in YAML is a number, and a version is not a number"
        )
    return value


def manifest_path(axis: str, name: str, *, root: Path) -> Path:
    """Where one implementation's manifest is, whether or not anything is there.

    Public because a run has to record the SHA-256 of every policy file it read, and
    assembling that path in a second place is how the two would drift apart.
    """
    if axis not in AXES:
        raise ConfigError(f"no such axis {axis!r}; there are two: {list(AXES)}")
    return root / axis / f"{name}.yaml"


def read_manifest(axis: str, name: str, *, root: Path) -> Manifest:
    """One implementation's manifest, by axis and name."""
    path = manifest_path(axis, name, root=root)
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


def names(axis: str, *, root: Path) -> list[str]:
    """Every implementation declared on one axis."""
    folder = root / axis
    return (
        sorted(path.stem for path in folder.glob("*.yaml")) if folder.is_dir() else []
    )
