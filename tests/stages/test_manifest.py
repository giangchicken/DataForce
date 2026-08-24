"""A declaration, parsed: what the type refuses, and what it keeps without reading.

Beside `test_record.py` and for the same reason -- a manifest is not a stage, but it is half of
what a stage is handed, and the engine is built out of two of them.

`Manifest` holds almost nothing, so what is worth proving is the three refusals: an unquoted
`version` (Requirement 40 -- YAML reads `version: 1` as an integer, and `1` and `1.0` are one
number and two versions), a key the reader did not route, and an edit under a run.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from dataforce.manifest import Manifest


def a_manifest(**overrides: Any) -> Manifest:
    """A modality's manifest, the way `edge/policy.py` will hand one over."""
    fields: dict[str, Any] = {
        "name": "text2text",
        "version": "1",
        "declarations": {"embedding": {"model": "a-static-embedder"}},
    }
    return Manifest(**{**fields, **overrides})


def test_a_modality_manifest_composes_with_no_modality() -> None:
    """Its own `name` is the pair, so there is nothing for `modality` to say."""
    assert a_manifest().modality is None


def test_a_profile_manifest_names_the_pair_it_composes_with() -> None:
    """The string a run is checked against; a different one hard-stops (Requirement 40)."""
    profile = a_manifest(name="tool_decision", modality="text2text")

    assert profile.modality == "text2text"


def test_an_unquoted_version_is_refused() -> None:
    """`version: 1` in YAML is an integer, and a version that arithmetic can touch is not one."""
    with pytest.raises(ValidationError):
        a_manifest(version=1)


def test_a_key_the_reader_did_not_route_is_refused() -> None:
    """An axis's own vocabulary belongs in `declarations`, not on the type both axes share."""
    with pytest.raises(ValidationError):
        a_manifest(embedding={"model": "a-static-embedder"})


def test_what_it_declares_is_kept_without_being_read() -> None:
    """The implementation that needs a key is the one that knows what it means."""
    declared = {"roles": {"target": "assistant"}, "a_key_no_code_knows": 7}

    assert a_manifest(declarations=declared).declarations == declared


def test_a_manifest_cannot_be_edited_under_a_run() -> None:
    """A declaration that changes mid-run is a run nobody can reproduce from its manifest."""
    manifest = a_manifest()

    with pytest.raises(ValidationError):
        manifest.version = "2"
