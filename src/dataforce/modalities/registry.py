"""Modalities by name, so no stage ever imports one.

Registration is the point where a run's provenance is fixed: the resolved
implementation's `name@version` goes onto every artifact it touches, which is
what stops a dataset silently changing the code that made it.
"""

from __future__ import annotations

from dataforce.modalities.base import Modality
from dataforce.shared.errors import ConfigError

__all__ = ["get", "names", "register"]

_REGISTRY: dict[str, Modality] = {}


def register(modality: Modality) -> None:
    """Make one modality selectable. Idempotent for the same object."""
    if not isinstance(modality, Modality):
        raise ConfigError(
            f"{modality!r} is not a Modality; it must provide "
            f"{sorted(Modality.__protocol_attrs__)}"
        )
    existing = _REGISTRY.get(modality.name)
    if existing is not None and existing is not modality:
        raise ConfigError(
            f"modality {modality.name!r} is already registered as {existing!r}"
        )
    _REGISTRY[modality.name] = modality


def get(name: str) -> Modality:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ConfigError(
            f"unknown modality {name!r}; registered: {names() or ['none']}"
        ) from None


def names() -> list[str]:
    return sorted(_REGISTRY)
