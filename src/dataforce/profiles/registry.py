"""Profiles by name: what a run may select, and what it may not.

One thing happens here that happens nowhere else. A profile's declared modality is
checked against the one the run asked for: a mismatched pair is a configuration
error, never coerced, because coercing it would produce a dataset whose provenance
says something untrue.

Registration checks nothing else. The five properties the pipeline assumes of a
profile are stated in the core spec's § *Rules a profile must satisfy* for the
author to follow and to prove in the profile's own tests -- see that section for
what going unchecked costs.
"""

from __future__ import annotations

from dataforce.profiles.base import Profile
from dataforce.shared.errors import ConfigError

__all__ = ["get", "names", "register"]

_REGISTRY: dict[str, Profile] = {}


def register(profile: Profile) -> None:
    """Make one profile selectable by name."""
    if not isinstance(profile, Profile):
        raise ConfigError(
            f"{profile!r} is not a Profile; it must provide "
            f"{sorted(Profile.__protocol_attrs__)}"
        )
    existing = _REGISTRY.get(profile.name)
    if existing is not None and existing is not profile:
        raise ConfigError(
            f"profile {profile.name!r} is already registered as {existing!r}"
        )
    _REGISTRY[profile.name] = profile


def get(name: str, *, modality: str | None = None) -> Profile:
    """One profile by name, optionally asserting the modality it composes with."""
    try:
        profile = _REGISTRY[name]
    except KeyError:
        raise ConfigError(
            f"unknown profile {name!r}; registered: {names() or ['none']}"
        ) from None

    declared = profile.modality
    if modality is not None and declared != modality:
        raise ConfigError(
            f"profile {name!r} composes with modality {declared!r}, "
            f"but the run asked for {modality!r}"
        )
    return profile


def names() -> list[str]:
    return sorted(_REGISTRY)
