"""The two contracts are closed sets, and a change to either is a decision.

The expected member sets are written out here rather than imported, so adding a
method to a protocol fails this test instead of quietly updating the thing it is
compared against.
"""

from __future__ import annotations

from typing import Any

from dataforce.modalities.base import Modality
from dataforce.profiles.base import Profile

MODALITY_MEMBERS = frozenset(
    {"name", "version", "load", "embed", "privacy_detectors", "display_control"}
)

PROFILE_MEMBERS = frozenset(
    {
        "name",
        "version",
        "modality",
        "answer_schema",
        "adapt",
        "delta",
        "consensus",
        "validity_checks",
        "question",
        "answer_control",
        "group_key",
        "export",
    }
)


def test_a_modality_supplies_four_things_and_nothing_else() -> None:
    assert set(Modality.__protocol_attrs__) == MODALITY_MEMBERS
    assert len(MODALITY_MEMBERS - {"name", "version"}) == 4


def test_the_profile_contract_is_closed() -> None:
    assert set(Profile.__protocol_attrs__) == PROFILE_MEMBERS


def test_a_profile_declares_the_modality_it_composes_with() -> None:
    assert "modality" in Profile.__protocol_attrs__


def test_the_contracts_do_not_overlap_beyond_name_and_version() -> None:
    """Neither axis may drift into the other's job."""
    assert MODALITY_MEMBERS & PROFILE_MEMBERS == {"name", "version"}


def test_an_implementation_missing_a_member_is_not_one(profile: Any) -> None:
    assert isinstance(profile, Profile)

    class Incomplete:
        name = "incomplete"
        version = "1"
        modality = "fake_text"
        answer_schema: dict[str, Any] = {"type": "string"}

    assert not isinstance(Incomplete(), Profile)
