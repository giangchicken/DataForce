"""Profiles by name, conformance-checked at registration.

Two things happen here that happen nowhere else. A profile is put through the
conformance suite before it can be selected, so a profile whose `delta` is not a
metric fails now rather than after a jury run. And a profile's declared modality
is checked against the one the run asked for: a mismatched pair is a
configuration error, never coerced, because coercing it would produce a dataset
whose provenance says something untrue.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataforce.profiles import conformance
from dataforce.profiles.base import Profile
from dataforce.shared.errors import ConfigError, ConformanceError

__all__ = ["Registration", "get", "names", "register", "report_for"]


@dataclass(frozen=True)
class Registration:
    profile: Profile
    report: conformance.ConformanceReport


_REGISTRY: dict[str, Registration] = {}


def register(profile: Profile) -> conformance.ConformanceReport:
    """Check one profile and make it selectable. Returns what the suite found."""
    if not isinstance(profile, Profile):
        raise ConfigError(
            f"{profile!r} is not a Profile; it must provide "
            f"{sorted(Profile.__protocol_attrs__)}"
        )
    existing = _REGISTRY.get(profile.name)
    if existing is not None and existing.profile is not profile:
        raise ConfigError(
            f"profile {profile.name!r} is already registered as {existing.profile!r}"
        )

    report = conformance.run(profile)
    if not report.ok:
        failed = "; ".join(f"{check.name}: {check.detail}" for check in report.failures)
        raise ConformanceError(
            f"profile {profile.name!r} fails conformance -- {failed}"
        )

    _REGISTRY[profile.name] = Registration(profile=profile, report=report)
    return report


def get(name: str, *, modality: str | None = None) -> Profile:
    """One profile by name, optionally asserting the modality it composes with."""
    try:
        registration = _REGISTRY[name]
    except KeyError:
        raise ConfigError(
            f"unknown profile {name!r}; registered: {names() or ['none']}"
        ) from None

    declared = registration.profile.modality
    if modality is not None and declared != modality:
        raise ConfigError(
            f"profile {name!r} composes with modality {declared!r}, "
            f"but the run asked for {modality!r}"
        )
    return registration.profile


def report_for(name: str) -> conformance.ConformanceReport:
    """What the suite found for a registered profile, including whether it is
    barred from the optional consensus tier."""
    get(name)  # so an unknown name fails the same way here as everywhere else
    return _REGISTRY[name].report


def names() -> list[str]:
    return sorted(_REGISTRY)
