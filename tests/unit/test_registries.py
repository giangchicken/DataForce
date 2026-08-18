"""Resolution by name: what a run may select, and what it may not."""

from __future__ import annotations

import pytest
from conftest import FreeTextProfile, NaNProfile, SetProfile, WobblyConsensusProfile

from dataforce.modalities import registry as modalities
from dataforce.profiles import registry as profiles
from dataforce.shared.errors import ConfigError, ConformanceError
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


def test_a_profile_is_conformance_checked_at_registration() -> None:
    report = profiles.register(SetProfile())
    assert report.ok
    assert not report.barred_from_consensus_tier
    assert profiles.report_for("fake_tools") is report


def test_a_profile_whose_delta_is_not_a_metric_never_becomes_selectable() -> None:
    with pytest.raises(ConformanceError, match="delta_is_a_metric"):
        profiles.register(NaNProfile())
    assert "fake_nan" not in profiles.names()


def test_a_profile_whose_consensus_wobbles_is_rejected() -> None:
    with pytest.raises(ConformanceError, match="not deterministic"):
        profiles.register(WobblyConsensusProfile())


def test_a_profile_with_no_defensible_consensus_is_supported_and_recorded() -> None:
    report = profiles.register(FreeTextProfile())
    assert report.ok
    assert report.barred_from_consensus_tier
    assert profiles.get("fake_free_text").name == "fake_free_text"


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
