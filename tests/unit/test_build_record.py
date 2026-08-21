"""One raw item into one canonical record, from either shape.

The format itself is tested in `test_catalog_format.py`. What is here is what
`build_record` decides:
identity, provenance, the answer space it derives rather than stores, what it keeps,
and that a record read from a `tools` array and one read from a rendered prompt come
out the same.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TEXT, TOOL_DECISION
from pydantic import ValidationError

from dataforce.core.errors import ConfigError
from dataforce.core.manifest import Manifest
from dataforce.core.record import Producer, Record, Source, TextPart
from dataforce.profiles.tool_decision import build_record, utils
from dataforce.profiles.tool_decision.source_contract import (
    LEGACY_SYSTEM_PROMPT,
    OPENAI_TOOLS,
    SourceContract,
    read_source_contract,
)

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
    return {**raw, **extra, build_record.PROVENANCE_KEY: PROVENANCE}


def build_legacy(raw: dict[str, Any], **extra: Any) -> Any:
    item = sourced(raw, **extra)
    return build_record.build_record(item, TEXT.content_parts(item), LEGACY)


# --- the two shapes agree ------------------------------------------------------


def test_the_canonical_shape_needs_no_parsing() -> None:
    raw = canonical_records()[0]
    item = sourced(raw)

    record = build_record.build_record(
        item, TEXT.content_parts(item), contract_for(OPENAI_TOOLS)
    )

    assert utils.catalog_names(record, contract_for(OPENAI_TOOLS)) == [
        t["function"]["name"] for t in raw["tools"]
    ]
    assert utils.CATALOG_HEADER not in raw["messages"][0]["content"]


def test_both_shapes_give_the_same_catalog_for_the_same_tools() -> None:
    """The conversion is lossless, which is what makes the legacy shape a way in."""
    canonical = canonical_records()[0]
    tools = utils.openai_to_tools(canonical["tools"]).tools
    as_legacy = {
        **canonical,
        "messages": [
            {"role": "system", "content": utils.build_system_prompt(tools)},
            *canonical["messages"][1:],
        ],
    }
    as_legacy.pop("tools")

    from_canonical = build_record.build_record(
        sourced(canonical),
        TEXT.content_parts(sourced(canonical)),
        contract_for(OPENAI_TOOLS),
    )
    from_legacy = build_record.build_record(
        sourced(as_legacy),
        TEXT.content_parts(sourced(as_legacy)),
        contract_for(LEGACY_SYSTEM_PROMPT),
    )

    # Each record is read under the contract it was built under. Before C2 the names
    # were stored on the record, so one profile object could read both shapes; now the
    # shape says where to look, and a run declares one source and therefore one shape.
    assert utils.catalog_names(
        from_canonical, contract_for(OPENAI_TOOLS)
    ) == utils.catalog_names(from_legacy, contract_for(LEGACY_SYSTEM_PROMPT))
    assert build_record.scenario_hash(
        from_canonical, contract_for(OPENAI_TOOLS)
    ) == build_record.scenario_hash(from_legacy, contract_for(LEGACY_SYSTEM_PROMPT))


def test_an_item_with_no_tools_at_all_is_an_empty_catalog() -> None:
    raw = canonical_records()[0]
    item = sourced({**raw, "tools": []})

    record = build_record.build_record(
        item, TEXT.content_parts(item), contract_for(OPENAI_TOOLS)
    )

    assert utils.catalog_names(record, contract_for(OPENAI_TOOLS)) == []


# --- identity -----------------------------------------------------------------


def test_rid_does_not_depend_on_position_in_the_file() -> None:
    raw = legacy_records()[0]

    assert build_legacy(raw).rid == build_legacy(raw, idx=9999).rid


def test_rid_changes_when_a_turn_changes() -> None:
    raw = legacy_records()[0]
    item = sourced(raw)
    parts = TEXT.content_parts(item)
    other = [*parts[:1], TextPart(role="user", text="một câu khác"), *parts[2:]]

    assert (
        build_record.build_record(item, parts, LEGACY).rid
        != build_record.build_record(item, other, LEGACY).rid
    )


# --- the answer space, derived rather than stored ------------------------------


def test_a_record_carries_no_answer_space_field_at_all() -> None:
    """Requirement 71. The catalog is already on the record; a copy of it is not.

    Asserted on the model rather than on one instance, because the point is that
    there is nowhere for a second copy to disagree from the first.
    """
    assert "answer_space" not in Record.model_fields

    record = build_legacy(legacy_records()[0])

    with pytest.raises(ValidationError):
        Record.model_validate({**record.model_dump(), "answer_space": {}})


def test_the_answer_space_is_derived_from_this_record_s_own_catalog() -> None:
    record = build_legacy(legacy_records()[0])
    expected = utils.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    )

    assert utils.catalog_names(record, LEGACY) == list(expected.names)

    space = TOOL_DECISION.answer_schema_for(record)
    named = [
        branch["properties"]["name"]["const"] for branch in space["items"]["oneOf"]
    ]
    assert named == list(expected.names)


def test_records_sharing_a_catalog_share_a_fingerprint() -> None:
    names = utils.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    ).names

    assert utils.catalog_hash(names) == utils.catalog_hash(list(names))


def test_a_different_catalog_gets_a_different_fingerprint() -> None:
    eight = utils.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    ).names
    twenty = utils.catalog_to_tools(
        (CATALOGS / "twenty_tools.txt").read_text(encoding="utf-8")
    ).names

    assert utils.catalog_hash(eight) != utils.catalog_hash(twenty)


def test_the_fingerprint_is_order_sensitive() -> None:
    """Two orderings of one tool set are two prompts, so they are two scenarios."""
    names = utils.catalog_to_tools(
        (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8")
    ).names

    assert utils.catalog_hash(names) != utils.catalog_hash(names[::-1])


# --- what it keeps ------------------------------------------------------------


@pytest.mark.parametrize("raw", legacy_records(), ids=lambda raw: str(raw["idx"]))
def test_adapt_preserves_meta_verbatim(raw: dict[str, Any]) -> None:
    """All 22 observed key-sets, and every value in them, unchanged."""
    record = build_legacy(raw)

    for key, value in raw["meta"].items():
        assert record.meta[key] == value
    assert record.label == raw["meta"]["label"]


def test_the_fixtures_cover_every_observed_key_set_and_cardinality() -> None:
    records = legacy_records()
    key_sets = {tuple(sorted(raw["meta"])) for raw in records}

    assert len(key_sets) == 22
    assert {len(raw["meta"]["label"]) for raw in records} == {0, 1, 2, 3}


def test_a_field_the_builder_does_not_understand_survives_it() -> None:
    record = build_legacy(legacy_records()[0], some_future_field="keep me")

    assert record.meta["some_future_field"] == "keep me"
    assert record.meta["idx"] == legacy_records()[0]["idx"]


def test_the_canonical_shape_keeps_its_tools_so_they_can_be_read() -> None:
    """The names go to the answer space; the descriptions are what an annotator reads."""
    raw = canonical_records()[0]
    item = sourced(raw)

    record = build_record.build_record(
        item, TEXT.content_parts(item), contract_for(OPENAI_TOOLS)
    )

    assert record.meta["tools"] == raw["tools"]
    assert TOOL_DECISION.readable_catalog(record).startswith("[Lookup00_0a]")


def test_a_legacy_record_has_no_catalog_to_re_render() -> None:
    """Its turns already carry one, so rendering a second would show it twice."""
    assert TOOL_DECISION.readable_catalog(build_legacy(legacy_records()[0])) == ""


# --- provenance ---------------------------------------------------------------


def test_provenance_is_required_so_an_unsourced_record_cannot_be_built() -> None:
    raw = legacy_records()[0]

    with pytest.raises(ConfigError, match="load stage"):
        build_record.build_record(raw, TEXT.content_parts(sourced(raw)), LEGACY)


def test_the_provenance_key_is_not_itself_kept_as_metadata() -> None:
    record = build_legacy(legacy_records()[0])

    assert build_record.PROVENANCE_KEY not in record.meta
    assert record.source == Source(**PROVENANCE["source"])
    assert record.producer == Producer(**PROVENANCE["producer"])


def test_a_canonical_record_whose_tools_went_missing_is_empty_not_an_exception() -> (
    None
):
    """`empty_catalog` is a quarantine for triage, and it is the one that reports this.

    There is no longer a "record built by another profile" error to raise, because
    there is no field whose absence would mean that -- the catalog is read from the
    record's own content, and content that offers nothing offers nothing.
    """
    record = build_legacy(legacy_records()[0])
    stripped = record.model_copy(update={"meta": {}, "content": []})

    assert utils.catalog_names(stripped, contract_for(OPENAI_TOOLS)) == []


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
