"""One implementation's manifest, read off disk.

The file's own name is the identity, checked against the `name` inside it, so a manifest
cannot be copied to a new file and left claiming to be the old one. What a manifest
holds once read is `shared/manifest.py`.

Two functions rather than one because a run has to record the SHA-256 of every policy
file it read: locating a manifest and parsing one are separate steps, so the path is a
value the caller holds and hands to the reader, rather than something assembled a second
time from the axis and the name.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from agent_toolkit.file_utils import read_yaml

from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest

__all__ = ["AXES", "manifest_path", "read_manifest"]

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
    """One implementation's manifest file, or a ConfigError naming the ones that are."""
    if axis not in AXES:
        raise ConfigError(f"no such axis {axis!r}; there are two: {list(AXES)}")
    path = root / axis / f"{name}.yaml"
    if not path.is_file():
        declared = sorted(found.stem for found in (root / axis).glob("*.yaml"))
        raise ConfigError(f"no manifest at {path}; {axis} declared here: {declared}")
    return path


def read_manifest(path: Path) -> Manifest:
    """What one manifest declares, by the path `manifest_path` located."""
    declared = read_yaml(path) or {}
    if not isinstance(declared, Mapping):
        raise ConfigError(
            f"{path}: a manifest is a mapping, got {type(declared).__name__}"
        )
    name = _text(declared, "name", path)
    if name != path.stem:
        raise ConfigError(
            f"{path} declares the name {name!r}; a manifest's filename is "
            "its identity, so the two cannot disagree"
        )
    return Manifest(
        name=name,
        version=_text(declared, "version", path),
        declared={key: value for key, value in declared.items() if key != "name"},
    )
