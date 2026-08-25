"""DEFINITION · Engine, Registry and ServiceResult -- what a service takes and returns; no I/O.

The type is the engine's because every service names it in its signature; the reader that fills
one from files is ``edge/bootstrap.py``, because reading is the edge's job. A registry is instance
state: two in one process hold different implementations (Requirement 39).

**An ``Engine`` is what a run resolved to, not what it could resolve to.** It carries the pair, the
registry it came out of, the thresholds a stage reads instead of holding a number of its own (P25),
and the digest of every policy file that produced them, which is what makes two runs of one
configuration comparable (Requirement 45). It holds no clock and no path, and it opens
nothing -- I1 is the scan that says so. What it does hold is the **ports** the edge supplied, because
every service's signature is ``(engine, records)`` and a port has no other way to reach a stage:
``personal_data_verifier`` is layer two's interface and ``jury_panel`` is the panel's, never a
client this module builds.

**Both ports default to ``None`` and the two absences mean different things.** Layer two is a
*second* layer, so an engine without one still scans: ``pii_check`` runs its patterns and the record
says `unverified`. A jury without a panel has nothing to run at all, so ``jury`` refuses the run
rather than writing a key that says the panel agreed on nothing -- the field is optional here
because the type cannot express *required for one phase*, and the stage is where that is said.

**``ServiceResult`` is here because this is where a service's signature is written.** ``Engine``
is what a stage is handed and ``ServiceResult`` is what it hands back, and the two are one sentence:
``def pii_check(engine: Engine, records: Iterable[Record]) -> ServiceResult``. A module of its own
would hold one dataclass and forward it, which is P8's pass-through.

**The registry takes the name rather than reading it off the implementation.** The two axes share
``name``, ``version`` and ``Part`` and nothing else, so a ``Registrable`` protocol holding the first
of those would be a fourth shared thing this design says does not exist. ``edge/bootstrap.py`` is
the only caller (Requirement 38) and registers under the manifest's own name.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, final

from dataforce.errors import ConfigError
from dataforce.modalities import Modality
from dataforce.ports import JuryPanel, PersonalDataVerifier
from dataforce.profiles import Profile
from dataforce.record import Record


def _refuse_a_second(axis: str, registered: Mapping[str, Any], name: str) -> None:
    """Requirement 39: a second implementation of one name is a mistake, never an override.

    Replacing the first silently is how two runs of one configuration produce different records
    and nothing in either run says why.
    """
    if name in registered:
        raise ConfigError(f"{axis} {name!r} is registered; a second one is refused")


def _registered[Implementation](
    axis: str, registered: Mapping[str, Implementation], name: str
) -> Implementation:
    """The implementation under that name, or a `ConfigError` naming the ones there are."""
    if name not in registered:
        known = ", ".join(sorted(registered)) or "none"
        raise ConfigError(f"unknown {axis} {name!r}; registered: {known}")
    return registered[name]


@final
class Registry:
    """Every implementation a run may resolve, by axis and by name.

    Instance state and not a module-level dict (Requirement 39). A process-wide registry is a
    mutable global: the order two tests ran in becomes part of what the second one asserts, and a
    fake registered by one of them outlives it. Two registries here hold different implementations
    and neither can see the other's.

    The two axes are separate namespaces, because a name is only unique within the axis whose
    `config/<axis>/` directory it was read from.
    """

    def __init__(self) -> None:
        self._modalities: dict[str, Modality] = {}
        self._profiles: dict[str, Profile] = {}

    def register_modality(self, name: str, modality: Modality) -> None:
        """Add one modality under the name its manifest filename gave it."""
        _refuse_a_second("modality", self._modalities, name)
        self._modalities[name] = modality

    def register_profile(self, name: str, profile: Profile) -> None:
        """Add one profile under the name its manifest filename gave it."""
        _refuse_a_second("profile", self._profiles, name)
        self._profiles[name] = profile

    def modality(self, name: str) -> Modality:
        """The modality registered under that name; `ConfigError` listing the ones that are."""
        return _registered("modality", self._modalities, name)

    def profile(self, name: str) -> Profile:
        """The profile registered under that name; `ConfigError` listing the ones that are."""
        return _registered("profile", self._profiles, name)


@dataclass(frozen=True)
class Engine:
    """One resolved pair and what resolved it. Every service takes one, and it opens nothing."""

    modality: Modality  # the resolved modality: how content is read and shown
    profile: Profile  # the resolved profile: what an answer to this run's task is
    registry: Registry  # the implementations this run may resolve, held per instance
    thresholds: Mapping[str, Any]  # `params.yaml`: no stage holds a number
    policy_digests: Mapping[str, str]  # every policy file, by digest (Req 45)
    personal_data_verifier: PersonalDataVerifier | None = (
        None  # layer two; None runs layer one alone
    )
    jury_panel: JuryPanel | None = None  # the panel; None is `jury`'s `ConfigError`


@dataclass(frozen=True)
class ServiceResult:
    """What one service hands back: the bus, and anything the edge must persist.

    There is no third field. **The records are the report** -- anything corpus-level is a fold over
    them, computed at the edge when a human wants to read it (Requirement 44), and a `metrics` field
    here would be a second place to compute it and a first place to get it wrong.

    `side_output` is keyed by the stage that produced it, because that is what tells the edge where
    to write it: `pii_check`'s placeholder map is a file that is never committed, `publish`'s rows
    are the question store. The engine returns it and never writes it (Requirement 36).
    """

    records: tuple[Record, ...]  # as many out as went in, in order (Requirement 41)
    side_output: Mapping[str, Any] = field(  # by stage; what the edge must persist
        default_factory=dict
    )
