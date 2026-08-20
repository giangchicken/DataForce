"""Resolution by name: what a run may select, and what it may not."""

from __future__ import annotations

import pytest
from conftest import CONFIG, PARAMS, FakeTextModality, FreeTextProfile, SetProfile

from dataforce import api
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import stamp
from dataforce.shared.registry import Registry


def test_a_registered_modality_resolves_by_name(modality: object) -> None:
    registry = Registry()
    registry.register_modality(modality)

    assert registry.modality("fake_text") is modality
    assert "fake_text" in registry.modality_names()


def test_an_unregistered_modality_names_what_is_registered(modality: object) -> None:
    registry = Registry()
    registry.register_modality(modality)

    with pytest.raises(ConfigError, match="fake_text"):
        registry.modality("audio")


def test_an_empty_registry_says_so() -> None:
    with pytest.raises(ConfigError, match="none"):
        Registry().profile("tool_decision")


def test_registering_a_second_implementation_of_one_name_is_refused(
    modality: object,
) -> None:
    registry = Registry()
    registry.register_modality(modality)

    with pytest.raises(ConfigError, match="already registered"):
        registry.register_modality(type(modality)())


def test_something_that_is_not_a_modality_is_refused_with_the_member_list() -> None:
    class NotOne:
        name = "not_one"
        version = "1"

    with pytest.raises(ConfigError, match="personal_data_detectors"):
        Registry().register_modality(NotOne())  # type: ignore[arg-type]


def test_a_registered_profile_resolves_by_name() -> None:
    registry = Registry()
    profile = SetProfile()
    registry.register_profile(profile)

    assert registry.profile("fake_tools") is profile
    assert "fake_tools" in registry.profile_names()


def test_something_that_is_not_a_profile_is_refused_with_the_member_list() -> None:
    """The only thing registration checks. The five profile rules are the author's."""

    class NotOne:
        name = "not_one"
        version = "1"

    with pytest.raises(ConfigError, match="answer_schema"):
        Registry().register_profile(NotOne())  # type: ignore[arg-type]


def test_registering_a_second_implementation_of_one_profile_name_is_refused() -> None:
    registry = Registry()
    registry.register_profile(SetProfile())

    with pytest.raises(ConfigError, match="already registered"):
        registry.register_profile(SetProfile())


def test_a_profile_with_no_defensible_consensus_is_still_selectable() -> None:
    """Returning None from `vote_consensus` bars the optional tier, not the profile."""
    registry = Registry()
    registry.register_profile(FreeTextProfile())

    assert registry.profile("fake_free_text").name == "fake_free_text"


def test_two_registries_in_one_process_hold_different_implementations() -> None:
    """Why registration is instance state, on both axes at once.

    One process may serve two configurations, and neither registry may resolve a
    name the other registered. This is what the deleted autouse fixture had to
    guarantee by snapshotting and restoring two module-level dicts.
    """
    one, other = Registry(), Registry()
    one.register_profile(SetProfile())
    one.register_modality(FakeTextModality())
    other.register_profile(FreeTextProfile())

    assert one.profile_names() == ["fake_tools"]
    assert other.profile_names() == ["fake_free_text"]
    assert other.modality_names() == []
    with pytest.raises(ConfigError, match="fake_tools"):
        other.profile("fake_tools")


def test_every_profile_the_composition_root_registers_has_its_modality() -> None:
    """A profile declaring a modality nobody registered is a run that cannot start.

    Folded in from `tests/conformance/test_registered_profiles.py`: the composition
    root is what a run resolves through, so that is what this registers from -- and
    since E6 that root is `api.open_engine`, which is what every caller enters by.
    """
    registry = api.open_engine(
        profile="tool_decision", config_root=CONFIG, params=PARAMS
    ).registry

    assert registry.profile_names(), "the composition root registered no profile"
    for name in registry.profile_names():
        declared = registry.profile(name).modality
        assert registry.modality(declared).name == declared


def test_a_profile_and_modality_that_disagree_hard_stop() -> None:
    registry = Registry()
    registry.register_profile(SetProfile())

    assert registry.profile("fake_tools", modality="fake_text").name == "fake_tools"
    with pytest.raises(ConfigError, match="composes with modality 'fake_text'"):
        registry.profile("fake_tools", modality="audio")


def test_the_resolved_pair_is_stamped_with_both_versions(modality: object) -> None:
    registry = Registry()
    registry.register_modality(modality)
    registry.register_profile(SetProfile())

    producer = stamp(registry.modality("fake_text"), registry.profile("fake_tools"))
    assert producer.modality == "fake_text@1"
    assert producer.profile == "fake_tools@1"
