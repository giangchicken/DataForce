"""Both axes by name, so no stage ever imports one.

Registration is the point where a run's provenance is fixed: the resolved
implementation's `name@version` goes onto every artifact it touches, which is
what stops a dataset silently changing the code that made it.

One thing happens here that happens nowhere else. A profile's declared modality is
checked against the one the run asked for: a mismatched pair is a configuration
error, never coerced, because coercing it would produce a dataset whose provenance
says something untrue.

Registration checks nothing else. The five properties the pipeline assumes of a
profile are stated in the core spec's § *Rules a profile must satisfy* for the
author to follow and to prove in the profile's own tests -- see that section for
what going unchecked costs.

The state is per instance and not per process, so two registries holding different
implementations can coexist. That is what one process serving two configurations
needs, and it is why registration takes objects and names no implementation itself.

Here rather than in `core/` because `api/engine.py` is the only thing that builds one,
and a module with one caller is that caller's code. It is also the only module that
imported both axes' contracts from inside the engine, so the move leaves `core/`
knowing nothing about either axis.
"""

from __future__ import annotations

from dataforce.core.errors import ConfigError
from dataforce.modalities.base import Modality
from dataforce.profiles.base import Profile

__all__ = ["Registry"]


class Registry:
    """What one run may select, on both axes."""

    def __init__(self) -> None:
        self._modalities: dict[str, Modality] = {}
        self._profiles: dict[str, Profile] = {}

    def register_modality(self, modality: Modality) -> None:
        """Make one modality selectable. Idempotent for the same object."""
        if not isinstance(modality, Modality):
            raise ConfigError(
                f"{modality!r} is not a Modality; it must provide "
                f"{sorted(Modality.__protocol_attrs__)}"
            )
        existing = self._modalities.get(modality.name)
        if existing is not None and existing is not modality:
            raise ConfigError(
                f"modality {modality.name!r} is already registered as {existing!r}"
            )
        self._modalities[modality.name] = modality

    def register_profile(self, profile: Profile) -> None:
        """Make one profile selectable by name."""
        if not isinstance(profile, Profile):
            raise ConfigError(
                f"{profile!r} is not a Profile; it must provide "
                f"{sorted(Profile.__protocol_attrs__)}"
            )
        existing = self._profiles.get(profile.name)
        if existing is not None and existing is not profile:
            raise ConfigError(
                f"profile {profile.name!r} is already registered as {existing!r}"
            )
        self._profiles[profile.name] = profile

    def modality(self, name: str) -> Modality:
        """One modality by name."""
        try:
            return self._modalities[name]
        except KeyError:
            raise ConfigError(
                f"unknown modality {name!r}; "
                f"registered: {self.modality_names() or ['none']}"
            ) from None

    def profile(self, name: str, *, modality: str | None = None) -> Profile:
        """One profile by name, optionally asserting the modality it composes with."""
        try:
            found = self._profiles[name]
        except KeyError:
            raise ConfigError(
                f"unknown profile {name!r}; "
                f"registered: {self.profile_names() or ['none']}"
            ) from None

        declared = found.modality
        if modality is not None and declared != modality:
            raise ConfigError(
                f"profile {name!r} composes with modality {declared!r}, "
                f"but the run asked for {modality!r}"
            )
        return found

    def modality_names(self) -> list[str]:
        """Every modality registered here."""
        return sorted(self._modalities)

    def profile_names(self) -> list[str]:
        """Every profile registered here."""
        return sorted(self._profiles)
