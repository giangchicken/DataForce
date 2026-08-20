"""One raw item into one canonical record, from either shape.

The format itself is tested in `test_catalog.py`. What is here is what `adapt` decides:
identity, provenance, the answer space, what it keeps, and that a record read from a
`tools` array and one read from a rendered prompt come out the same.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dataforce.modalities.text import TEXT
from dataforce.profiles.tool_decision import TOOL_DECISION, adapter
from dataforce.profiles.tool_decision import catalog as cat
from dataforce.profiles.tool_decision.source import (
    LEGACY_SYSTEM_PROMPT,
    OPENAI_TOOLS,
    SourceContract,
    read_source_contract,
)
from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest
from dataforce.shared.record import Producer, Source, TextPart

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"
CATALOGS = FIXTURES / "catalogs"

PROVENANCE = {
    "source": {
        "file_sha256": "0" * 64,
        "offset": 3,
        "ingested_at": "2026-08-19T00:00:00Z",
    },
    "producer": {"modality": "text@1", "profile": "tool_decision@1"},
}

LEGACY = TOOL_DECISION.contract


def contract_for(shape: str) -> SourceContract:
    """The same declarations the manifest carries, with one shape swapped."""
    return read_source_contract(
        Manifest(
            name="probe",
            version="1",
            declared={
                "shape": shape,
                "roles": dict(LEGACY.roles),
                "label": {"at": LEGACY.label_key},
                "meta": dict(LEGACY.meta),
                "gold": {"from": LEGACY.gold_from},
            },
        )
    )


def legacy_records() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads(
        (FIXTURES / "records.json").read_text(encoding="utf-8")
    )
    return loaded


def canonical_records() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads(
        (FIXTURES / "canonical_records.json").read_text(encoding="utf-8")
    )
    return loaded


def sourced(raw: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {**raw, **extra, adapter.PROVENANCE_KEY: PROVENANCE}


def adapt_legacy(raw: dict[str, Any], **extra: Any) -> Any:
    item = sourced(raw, **extra)
    return adapter.adapt(item, TEXT.load(item), LEGACY)


# --- the two shapes agree ------------------------------------------------------


def test_the_canonical_shape_needs_no_parsing() -> None:
    raw = canonical_records()[0]
    item = sourced(raw)

    record = adapter.adapt(item, TEXT.load(item), contract_for(OPENAI_TOOLS))

    assert adapter.catalog_names(record) == [
        t["function"]["name"] for t in raw["tools"]
    ]
    assert cat.CATALOG_HEADER not in raw["messages"][0]["content"]


def test_both_shapes_give_the_same_catalog_for_the_same_tools() -> None:
    """The conversion is lossless, which is what makes the legacy shape a way in."""
    canonical = canonical_records()[0]
    tools = [
        cat.Tool(
            name=entry["function"]["name"],
            description=entry["function"].get("description", ""),
            parameters=entry["function"].get("parameters", {}),
        )
        for entry in canonical["tools"]
    ]
    as_legacy = {
        **canonical,
        "messages": [
            {"role": "system", "content": cat.build_system_prompt(tools)},
            *canonical["messages"][1:],
        ],
    }
    as_legacy.pop("tools")

    from_canonical = adapter.adapt(
        sourced(canonical), TEXT.load(sourced(canonical)), contract_for(OPENAI_TOOLS)
    )
    from_legacy = adapter.adapt(
        sourced(as_legacy),
        TEXT.load(sourced(as_legacy)),
        contract_for(LEGACY_SYSTEM_PROMPT),
    )

    assert from_canonical.answer_space == from_legacy.answer_space
    assert TOOL_DECISION.group_key(from_canonical) == TOOL_DECISION.group_key(
        from_legacy
    )


def test_an_item_with_no_tools_at_all_is_an_empty_catalog() -> None:
    raw = canonical_records()[0]
    item = sourced({**raw, "tools": []})

    record = adapter.adapt(item, TEXT.load(item), contract_for(OPENAI_TOOLS))

    assert adapter.catalog_names(record) == []


# --- identity -----------------------------------------------------------------


def test_rid_does_not_depend_on_position_in_the_file() -> None:
    raw = legacy_records()[0]

    assert adapt_legacy(raw).rid == adapt_legacy(raw, idx=9999).rid


def test_rid_changes_when_a_turn_changes() -> None:
    raw = legacy_records()[0]
    item = sourced(raw)
    parts = TEXT.load(item)
    other = [*parts[:1], TextPart(role="user", text="một câu khác"), *parts[2:]]

    assert (
        adapter.adapt(item, parts, LEGACY).rid != adapter.adapt(item, other, LEGACY).rid
    )


# --- the answer space and the group key ---------------------------------------


def test_the_answer_space_is_this_record_s_own_catalog() -> None:
    record = adapt_legacy(legacy_records()[0])
    expected = cat.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    )

    assert record.answer_space is not None
    assert record.answer_space["items"]["enum"] == list(expected.names)
    assert adapter.catalog_names(record) == record.answer_space["items"]["enum"]


def test_records_sharing_a_catalog_share_a_fingerprint() -> None:
    names = cat.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    ).names

    assert adapter.catalog_fingerprint(names) == adapter.catalog_fingerprint(
        list(names)
    )


def test_a_different_catalog_gets_a_different_fingerprint() -> None:
    eight = cat.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    ).names
    twenty = cat.catalog_to_tools(
        (CATALOGS / "twenty_tools.txt").read_text(encoding="utf-8")
    ).names

    assert adapter.catalog_fingerprint(eight) != adapter.catalog_fingerprint(twenty)


def test_the_fingerprint_is_order_sensitive() -> None:
    """Two orderings of one tool set are two prompts, so they are two scenarios."""
    names = cat.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    ).names

    assert adapter.catalog_fingerprint(names) != adapter.catalog_fingerprint(
        names[::-1]
    )


# --- what it keeps ------------------------------------------------------------


@pytest.mark.parametrize("raw", legacy_records(), ids=lambda raw: str(raw["idx"]))
def test_adapt_preserves_meta_verbatim(raw: dict[str, Any]) -> None:
    """All 22 observed key-sets, and every value in them, unchanged."""
    record = adapt_legacy(raw)

    for key, value in raw["meta"].items():
        assert record.meta[key] == value
    assert record.label == raw["meta"]["label"]


def test_the_fixtures_cover_every_observed_key_set_and_cardinality() -> None:
    records = legacy_records()
    key_sets = {tuple(sorted(raw["meta"])) for raw in records}

    assert len(key_sets) == 22
    assert {len(raw["meta"]["label"]) for raw in records} == {0, 1, 2, 3}


def test_a_field_the_adapter_does_not_understand_survives_it() -> None:
    record = adapt_legacy(legacy_records()[0], some_future_field="keep me")

    assert record.meta["some_future_field"] == "keep me"
    assert record.meta["idx"] == legacy_records()[0]["idx"]


def test_the_canonical_shape_keeps_its_tools_so_they_can_be_read() -> None:
    """The names go to the answer space; the descriptions are what an annotator reads."""
    raw = canonical_records()[0]
    item = sourced(raw)

    record = adapter.adapt(item, TEXT.load(item), contract_for(OPENAI_TOOLS))

    assert record.meta["tools"] == raw["tools"]
    assert TOOL_DECISION.readable_catalog(record).startswith("[Lookup00_0a]")


def test_a_legacy_record_has_no_catalog_to_re_render() -> None:
    """Its turns already carry one, so rendering a second would show it twice."""
    assert TOOL_DECISION.readable_catalog(adapt_legacy(legacy_records()[0])) == ""


# --- provenance ---------------------------------------------------------------


def test_provenance_is_required_so_an_unsourced_record_cannot_be_built() -> None:
    raw = legacy_records()[0]

    with pytest.raises(ConfigError, match="load stage"):
        adapter.adapt(raw, TEXT.load(sourced(raw)), LEGACY)


def test_the_provenance_key_is_not_itself_kept_as_metadata() -> None:
    record = adapt_legacy(legacy_records()[0])

    assert adapter.PROVENANCE_KEY not in record.meta
    assert record.source == Source(**PROVENANCE["source"])
    assert record.producer == Producer(**PROVENANCE["producer"])


def test_a_record_with_no_answer_space_is_named_rather_than_read_blindly() -> None:
    record = adapt_legacy(legacy_records()[0])

    with pytest.raises(ConfigError, match="not adapted"):
        adapter.catalog_names(record.model_copy(update={"answer_space": None}))


# --- the contract itself ------------------------------------------------------


def test_an_undeclared_shape_is_refused_by_name() -> None:
    with pytest.raises(ConfigError, match="is not one of"):
        read_source_contract(
            Manifest(
                name="probe",
                version="1",
                declared={
                    "shape": "guess",
                    "roles": {"target": "assistant"},
                    "label": {"at": "label"},
                    "meta": {},
                },
            )
        )


def test_an_undeclared_role_or_field_says_what_is_declared() -> None:
    with pytest.raises(ConfigError, match="no role declared"):
        LEGACY.role_name("narrator")
    with pytest.raises(ConfigError, match="no source field declared"):
        LEGACY.field_name("vibe")


def test_a_missing_label_key_names_the_manifest_and_the_key() -> None:
    """A hand-edited manifest gets an error naming both, not a bare KeyError."""
    with pytest.raises(ConfigError, match=r"probe: label.at is not declared"):
        read_source_contract(
            Manifest(
                name="probe",
                version="1",
                declared={
                    "shape": "legacy_system_prompt",
                    "roles": {"target": "assistant"},
                    "label": {},
                    "meta": {},
                },
            )
        )


def test_an_undeclared_target_role_fails_when_the_contract_is_read() -> None:
    """Not once per record: the restating turn is resolved up front."""
    with pytest.raises(ConfigError, match="no role declared for 'target'"):
        read_source_contract(
            Manifest(
                name="probe",
                version="1",
                declared={
                    "shape": "legacy_system_prompt",
                    "roles": {"instruction": "system"},
                    "label": {"at": "label"},
                    "meta": {},
                },
            )
        )


def test_the_label_is_read_from_the_declared_meta_field() -> None:
    assert LEGACY.label_key == "label"
    assert LEGACY.read_label({"meta": {"label": ["a"]}}) == ["a"]
    assert LEGACY.read_label({"meta": {}}) is None
    assert LEGACY.read_label({}) is None


def test_the_restating_turn_is_the_target_and_is_not_declared_twice() -> None:
    """`roles.target` already names the turn the answer is restated in."""
    assert LEGACY.restating_role == LEGACY.role_name("target") == "assistant"
