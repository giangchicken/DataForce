"""The adapter, and the marker tokens it must not touch.

A parser that strips the marker DSL passes every other test in this repository
while making the annotation task unanswerable, so the marker assertions here are
counted rather than sampled: every token in the source appears, as many times, in
what the adapter produced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataforce.profiles.tool_decision import adapter
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import Producer, Source, TextPart

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"
CATALOGS = FIXTURES / "catalogs"

MARKERS = ("{trigger}", "{hold_other}", "{hold_missing}", "{constraint}", "{or}")

PROVENANCE = {
    "source": {
        "file_sha256": "0" * 64,
        "offset": 3,
        "ingested_at": "2026-08-19T00:00:00Z",
    },
    "producer": {"modality": "text@1", "profile": "tool_decision@1"},
}


def catalog_text(name: str) -> str:
    return (CATALOGS / name).read_text(encoding="utf-8")


def fixture_records() -> list[dict[str, object]]:
    loaded: list[dict[str, object]] = json.loads(
        (FIXTURES / "records.json").read_text(encoding="utf-8")
    )
    return loaded


def parts_of(raw: dict[str, object]) -> list[TextPart]:
    messages: list[dict[str, str]] = raw["messages"]  # type: ignore[assignment]
    return [TextPart(role=turn["role"], text=turn["content"]) for turn in messages]


def clauses(catalog: adapter.Catalog) -> str:
    """Everything the adapter kept, as one string, for counting tokens in."""
    return "\n".join(
        "\n".join(
            [
                tool.purpose,
                tool.call_when,
                tool.hold_when,
                *(p.description for p in tool.params),
            ]
        )
        for tool in catalog.tools
    )


# --- the clause grammar -------------------------------------------------------


def test_an_entry_parses_into_every_clause() -> None:
    (tool,) = adapter.parse_catalog(catalog_text("one_tool.txt")).tools

    assert tool.name == "Lookup00_0a"
    assert tool.purpose == "tra cứu số dư cho khách hàng."
    assert tool.call_when.startswith("{trigger} khách hàng yêu cầu")
    assert tool.hold_when.startswith("{hold_other} khách hàng hỏi việc khác")
    assert tool.require == ("ma_khach",)
    assert [p.name for p in tool.params] == ["ma_khach", "ghi_chu"]
    assert [p.required for p in tool.params] == [True, False]
    assert [p.type for p in tool.params] == ["string", "string"]
    assert tool.params[0].description.endswith("{constraint} gồm đúng 6 chữ số.")


@pytest.mark.parametrize(
    ("fixture", "size"),
    [
        ("one_tool.txt", 1),
        ("eight_tools.txt", 8),
        ("twenty_tools.txt", 20),
        ("no_tools_header.txt", 0),
        ("header_without_entries.txt", 0),
    ],
)
def test_catalog_size(fixture: str, size: int) -> None:
    catalog = adapter.parse_catalog(catalog_text(fixture))

    assert len(catalog.tools) == size
    assert catalog.is_empty == (size == 0)


# --- invariant 1: the markers ------------------------------------------------


@pytest.mark.parametrize(
    "fixture", ["one_tool.txt", "eight_tools.txt", "twenty_tools.txt", "odd_names.txt"]
)
def test_every_marker_token_survives_the_adapter_byte_for_byte(fixture: str) -> None:
    """Counted, not sampled: a parser that drops one clause would still pass `in`."""
    source = catalog_text(fixture)
    kept = clauses(adapter.parse_catalog(source))

    for marker in MARKERS:
        assert kept.count(marker) == source.count(marker), marker


def test_a_marker_the_parser_has_never_seen_survives_too() -> None:
    """`{turn_trigger}` appears 881 times corpus-wide and in no clause label."""
    source = catalog_text("one_tool.txt").replace(
        "{trigger} khách hàng yêu cầu",
        "{turn_trigger} lượt cuối {trigger} khách hàng yêu cầu",
    )

    (tool,) = adapter.parse_catalog(source).tools

    assert tool.call_when.startswith("{turn_trigger} lượt cuối {trigger}")


# --- the name convention -----------------------------------------------------


def test_names_a_stricter_pattern_would_reject_are_real_entries() -> None:
    """The convention that decides `empty_catalog` and `label_not_in_catalog`."""
    catalog = adapter.parse_catalog(catalog_text("odd_names.txt"))

    assert catalog.names == (
        "card.search_faq",
        "end-call",
        "calculate BMI",
        "calculate_triangl\te_area",
    )
    assert all(tool.purpose for tool in catalog.tools)


def test_a_bracketed_phrase_inside_prose_is_not_an_entry() -> None:
    catalog = adapter.parse_catalog(catalog_text("bracket_inside_prose.txt"))

    assert catalog.names == ("Lookup00_0a",)
    assert "[Phụ lục A]" in catalog.tools[0].purpose


def test_a_malformed_entry_still_contributes_its_name() -> None:
    """Not an exception and not a partial catalog: the tool set stays complete."""
    catalog = adapter.parse_catalog(catalog_text("entry_missing_clauses.txt"))

    assert catalog.names == ("Bare_01a", "Full_02b")
    assert catalog.tools[0].purpose == ""
    assert catalog.tools[0].params == ()
    assert catalog.tools[1].purpose


def test_a_message_with_no_tools_header_is_an_empty_catalog_not_an_exception() -> None:
    assert adapter.parse_catalog(catalog_text("no_tools_header.txt")).is_empty


# --- the fingerprint ---------------------------------------------------------


def test_records_sharing_a_catalog_share_a_fingerprint() -> None:
    one = adapter.parse_catalog(catalog_text("eight_tools.txt"))
    again = adapter.parse_catalog(catalog_text("eight_tools.txt"))

    assert adapter.catalog_fingerprint(one.names) == adapter.catalog_fingerprint(
        again.names
    )


def test_a_different_catalog_gets_a_different_fingerprint() -> None:
    eight = adapter.parse_catalog(catalog_text("eight_tools.txt")).names
    twenty = adapter.parse_catalog(catalog_text("twenty_tools.txt")).names

    assert adapter.catalog_fingerprint(eight) != adapter.catalog_fingerprint(twenty)


def test_the_fingerprint_is_order_sensitive() -> None:
    """Two orderings of one tool set are two prompts, so they are two scenarios."""
    names = adapter.parse_catalog(catalog_text("eight_tools.txt")).names

    assert adapter.catalog_fingerprint(names) != adapter.catalog_fingerprint(
        names[::-1]
    )


# --- adapt -------------------------------------------------------------------


def test_rid_does_not_depend_on_position_in_the_file() -> None:
    raw = fixture_records()[0]
    parts = parts_of(raw)

    here = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, list(parts))
    moved = adapter.adapt(
        {**raw, "idx": 9999, adapter.PROVENANCE_KEY: PROVENANCE}, list(parts)
    )

    assert here.rid == moved.rid


def test_rid_changes_when_a_turn_changes() -> None:
    raw = fixture_records()[0]
    parts = parts_of(raw)
    other = [*parts[:1], TextPart(role="user", text="một câu khác"), *parts[2:]]

    first = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, list(parts))
    second = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, list(other))

    assert first.rid != second.rid


def test_the_answer_space_is_this_record_s_own_catalog() -> None:
    raw = fixture_records()[0]

    record = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, parts_of(raw))

    assert record.answer_space is not None
    assert record.answer_space["items"]["enum"] == list(
        adapter.parse_catalog(catalog_text("eight_tools.txt")).names
    )
    assert adapter.catalog_names(record) == record.answer_space["items"]["enum"]


@pytest.mark.parametrize("raw", fixture_records(), ids=lambda raw: str(raw["idx"]))
def test_adapt_preserves_meta_verbatim(raw: dict[str, object]) -> None:
    """All 22 observed key-sets, and every value in them, unchanged."""
    record = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, parts_of(raw))

    source_meta: dict[str, object] = raw["meta"]  # type: ignore[assignment]
    for key, value in source_meta.items():
        assert record.meta[key] == value
    assert record.label == source_meta["label"]


def test_the_fixtures_cover_every_observed_key_set_and_cardinality() -> None:
    """A fixture set that quietly stopped covering these would fail here first."""
    records = fixture_records()
    key_sets = {tuple(sorted(raw["meta"])) for raw in records}  # type: ignore[arg-type]
    cardinalities = {len(raw["meta"]["label"]) for raw in records}  # type: ignore[index]

    assert len(key_sets) == 22
    assert cardinalities == {0, 1, 2, 3}


def test_a_field_the_adapter_does_not_understand_survives_it() -> None:
    raw = fixture_records()[0]

    record = adapter.adapt(
        {**raw, "some_future_field": "keep me", adapter.PROVENANCE_KEY: PROVENANCE},
        parts_of(raw),
    )

    assert record.meta["some_future_field"] == "keep me"
    assert record.meta["idx"] == raw["idx"]


def test_provenance_is_required_so_an_unsourced_record_cannot_be_built() -> None:
    raw = fixture_records()[0]

    with pytest.raises(ConfigError, match="load stage"):
        adapter.adapt(raw, parts_of(raw))


def test_the_provenance_key_is_not_itself_kept_as_metadata() -> None:
    raw = fixture_records()[0]

    record = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, parts_of(raw))

    assert adapter.PROVENANCE_KEY not in record.meta
    assert record.source == Source(**PROVENANCE["source"])
    assert record.producer == Producer(**PROVENANCE["producer"])


def test_a_record_with_no_answer_space_is_named_rather_than_read_blindly() -> None:
    raw = fixture_records()[0]
    record = adapter.adapt({**raw, adapter.PROVENANCE_KEY: PROVENANCE}, parts_of(raw))

    with pytest.raises(ConfigError, match="not adapted"):
        adapter.catalog_names(record.model_copy(update={"answer_space": None}))
