"""Resolution by name: what a run may select, and what it may not."""

from __future__ import annotations

import pytest
from conftest import FreeTextProfile, SetProfile

from dataforce.cli import _register_implementations
from dataforce.modalities import registry as modalities
from dataforce.profiles import registry as profiles
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import stamp


def test_a_registered_modality_resolves_by_name(modality: object) -> None:
    modalities.register(modality)
    assert modalities.get("fake_text") is modality
    assert "fake_text" in modalities.names()


def test_an_unregistered_modality_names_what_is_registered(modality: object) -> None:
    modalities.register(modality)
    with pytest.raises(ConfigError, match="fake_text"):
        modalities.get("audio")


def test_an_empty_registry_says_so() -> None:
    with pytest.raises(ConfigError, match="none"):
        profiles.get("tool_decision")


def test_registering_a_second_implementation_of_one_name_is_refused(
    modality: object,
) -> None:
    modalities.register(modality)
    with pytest.raises(ConfigError, match="already registered"):
        modalities.register(type(modality)())


def test_something_that_is_not_a_modality_is_refused_with_the_member_list() -> None:
    class NotOne:
        name = "not_one"
        version = "1"

    with pytest.raises(ConfigError, match="privacy_detectors"):
        modalities.register(NotOne())  # type: ignore[arg-type]


def test_a_registered_profile_resolves_by_name() -> None:
    profile = SetProfile()
    profiles.register(profile)

    assert profiles.get("fake_tools") is profile
    assert "fake_tools" in profiles.names()


def test_something_that_is_not_a_profile_is_refused_with_the_member_list() -> None:
    """The only thing registration checks. The five profile rules are the author's."""

    class NotOne:
        name = "not_one"
        version = "1"

    with pytest.raises(ConfigError, match="answer_schema"):
        profiles.register(NotOne())  # type: ignore[arg-type]


def test_registering_a_second_implementation_of_one_profile_name_is_refused() -> None:
    profiles.register(SetProfile())
    with pytest.raises(ConfigError, match="already registered"):
        profiles.register(SetProfile())


def test_a_profile_with_no_defensible_consensus_is_still_selectable() -> None:
    """Returning None from `consensus` bars the optional tier, not the profile."""
    profiles.register(FreeTextProfile())

    assert profiles.get("fake_free_text").name == "fake_free_text"


def test_every_profile_the_composition_root_registers_has_its_modality() -> None:
    """A profile declaring a modality nobody registered is a run that cannot start.

    Folded in from `tests/conformance/test_registered_profiles.py`: the composition
    root is what a run resolves through, so that is what this registers from.
    """
    _register_implementations()

    assert profiles.names(), "the composition root registered no profile"
    for name in profiles.names():
        declared = profiles.get(name).modality
        assert modalities.get(declared).name == declared


def test_a_profile_and_modality_that_disagree_hard_stop() -> None:
    profiles.register(SetProfile())
    assert profiles.get("fake_tools", modality="fake_text").name == "fake_tools"
    with pytest.raises(ConfigError, match="composes with modality 'fake_text'"):
        profiles.get("fake_tools", modality="audio")


def test_the_resolved_pair_is_stamped_with_both_versions(modality: object) -> None:
    modalities.register(modality)
    profiles.register(SetProfile())
    producer = stamp(modalities.get("fake_text"), profiles.get("fake_tools"))
    assert producer.modality == "fake_text@1"
    assert producer.profile == "fake_tools@1"
