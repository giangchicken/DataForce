"""The catalog format, both directions, and the round trip that proves they agree.

The format is defined in one module because a grammar with two definitions has none.
What makes that safe is this: render what was read and compare bytes. The corpus-wide
version of the same assertion runs over all 21,172 catalogs in the integration suite.

The marker assertions are counted rather than sampled. A reader that dropped one clause
would still satisfy `marker in text`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from conftest import SOURCE_ROOT, parsed_sources

from dataforce.profiles.tool_decision import schema, utils

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"
CATALOGS = FIXTURES / "catalogs"

MARKERS = ("{trigger}", "{hold_other}", "{hold_missing}", "{constraint}", "{or}")
ALL_FIXTURES = [
    "one_tool.txt",
    "eight_tools.txt",
    "twenty_tools.txt",
    "odd_names.txt",
    "entry_missing_clauses.txt",
    "bracket_inside_prose.txt",
]


def text_of(name: str) -> str:
    return (CATALOGS / name).read_text(encoding="utf-8")


def catalog_part(name: str) -> str:
    """The fixture with its instruction preamble removed."""
    header = f"{utils.CATALOG_HEADER}\n"
    body = text_of(name)
    return body.split(header, 1)[1] if header in body else ""


# --- the round trip ----------------------------------------------------------


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_a_catalog_read_and_re_rendered_is_byte_identical(fixture: str) -> None:
    """The one assertion that makes a single format definition trustworthy."""
    original = catalog_part(fixture)

    again = utils.tools_to_catalog(utils.catalog_to_tools(text_of(fixture)).tools)

    assert again == original.rstrip("\n")


def test_tools_rendered_and_read_back_are_the_same_tools() -> None:
    tools = (
        schema.Tool(
            name="calc_loan",
            description="Mục đích: tính lãi.\nKhi nào gọi: {trigger} khách hỏi lãi.",
            parameters={
                "type": "object",
                "properties": {
                    "principal": {"type": "number", "description": "số tiền gốc"},
                    "channel": {
                        "type": "string",
                        "description": "kênh",
                        "enum": ["call", "sms"],
                        "default": "call",
                    },
                    "rounds": {
                        "type": "integer",
                        "description": "số kỳ",
                        "default": 12,
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "đã xác nhận",
                        "default": True,
                    },
                    "tags": {
                        "type": "array",
                        "description": "nhãn",
                        "items": {"type": "string", "enum": ["a.b", "c"]},
                    },
                },
                "required": ["principal", "channel"],
            },
        ),
    )

    again = utils.catalog_to_tools(utils.build_system_prompt(tools)).tools

    assert [t.name for t in again] == ["calc_loan"]
    assert again[0].description == tools[0].description
    assert again[0].parameters == {
        "type": "object",
        "properties": {
            "principal": {"type": "number", "description": "số tiền gốc"},
            "channel": {
                "type": "string",
                "description": "kênh",
                "enum": ["call", "sms"],
                "default": "call",
            },
            "rounds": {"type": "integer", "description": "số kỳ", "default": 12},
            "confirmed": {
                "type": "boolean",
                "description": "đã xác nhận",
                "default": True,
            },
            "tags": {
                "type": "array",
                "description": "nhãn",
                "items": {"type": "string", "enum": ["a.b", "c"]},
            },
        },
        # `channel` is required *and* defaulted, which is a contradiction: the default
        # wins, so it is not required and carries no star.
        "required": ["principal"],
    }


def test_a_dotted_enum_value_survives_the_clause_that_ends_in_a_dot() -> None:
    tools = (
        schema.Tool(
            name="pick",
            description="Mục đích: chọn.",
            parameters={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["phiGiaoDich.ngoaiTe", "b"]}
                },
                "required": ["kind"],
            },
        ),
    )

    again = utils.catalog_to_tools(utils.build_system_prompt(tools)).tools

    assert again[0].properties["kind"]["enum"] == ["phiGiaoDich.ngoaiTe", "b"]


def test_a_decimal_default_is_not_cut_at_its_point() -> None:
    tools = (
        schema.Tool(
            name="scale",
            description="Mục đích: nhân.",
            parameters={
                "type": "object",
                "properties": {"factor": {"type": "number", "default": 1.5}},
                "required": [],
            },
        ),
    )

    again = utils.catalog_to_tools(utils.build_system_prompt(tools)).tools

    assert again[0].properties["factor"]["default"] == 1.5


# --- the description is never split ------------------------------------------


def test_a_freeform_description_is_kept_whole() -> None:
    """The failure the first reader had: three clause labels, and prose vanished."""
    tools = (
        schema.Tool(
            name="legacy",
            description="Tra cứu hoá đơn. Chỉ khi đã xác thực.",
            parameters={},
        ),
    )

    again = utils.catalog_to_tools(utils.build_system_prompt(tools)).tools

    assert again[0].description == "Tra cứu hoá đơn. Chỉ khi đã xác thực."


def test_a_structured_description_is_also_just_a_description() -> None:
    (tool,) = utils.catalog_to_tools(text_of("one_tool.txt")).tools

    assert tool.description.startswith("Mục đích: tra cứu số dư cho khách hàng.")
    assert "Khi nào gọi: {trigger}" in tool.description
    assert "Khi nào KHÔNG gọi: {hold_other}" in tool.description
    assert tool.description.count("\n") == 2


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_every_marker_token_survives_byte_for_byte(fixture: str) -> None:
    source = text_of(fixture)
    tools = utils.catalog_to_tools(source).tools
    kept = "\n".join(
        tool.description + json.dumps(tool.parameters, ensure_ascii=False)
        for tool in tools
    )

    for marker in MARKERS:
        assert kept.count(marker) == source.count(marker), marker


# --- structure ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "size"),
    [
        ("one_tool.txt", 1),
        ("eight_tools.txt", 8),
        ("twenty_tools.txt", 20),
        ("odd_names.txt", 4),
        ("no_tools_header.txt", 0),
        ("header_without_entries.txt", 0),
    ],
)
def test_catalog_size(fixture: str, size: int) -> None:
    parsed = utils.catalog_to_tools(text_of(fixture))

    assert len(parsed.tools) == size
    assert bool(parsed.tools) == (size > 0)


def test_parameters_carry_their_type_requiredness_and_clauses() -> None:
    (tool,) = utils.catalog_to_tools(text_of("one_tool.txt")).tools

    assert list(tool.properties) == ["ma_khach", "ghi_chu"]
    assert tool.required == ("ma_khach",)
    assert tool.properties["ma_khach"]["type"] == "string"
    assert (
        "{constraint} gồm đúng 6 chữ số." in tool.properties["ma_khach"]["description"]
    )


def test_a_rich_object_keeps_its_subfields_instead_of_flattening_them() -> None:
    """The second failure the first reader had: subfields became sibling parameters."""
    tools = (
        schema.Tool(
            name="book",
            description="Mục đích: đặt lịch.",
            parameters={
                "type": "object",
                "properties": {
                    "customer": {
                        "type": "object",
                        "description": "thông tin khách",
                        "properties": {
                            "full_name": {
                                "type": "string",
                                "description": "tên đầy đủ",
                            },
                            "priority": {
                                "type": "string",
                                "description": "mức ưu tiên",
                                "enum": ["cao", "thap"],
                            },
                        },
                        "required": ["full_name"],
                    },
                    "channel": {"type": "string", "description": "kênh"},
                },
                "required": ["customer", "channel"],
            },
        ),
    )

    again = utils.catalog_to_tools(utils.build_system_prompt(tools)).tools

    assert list(again[0].properties) == ["customer", "channel"]
    customer = again[0].properties["customer"]
    assert list(customer["properties"]) == ["full_name", "priority"]
    assert customer["required"] == ["full_name"]
    assert customer["properties"]["priority"]["enum"] == ["cao", "thap"]


def test_a_bare_object_stays_on_the_compact_inline_form() -> None:
    """Byte-stability with legacy catalogs, which is why the two forms both exist."""
    tools = (
        schema.Tool(
            name="note",
            description="Mục đích: ghi.",
            parameters={
                "type": "object",
                "properties": {
                    "who": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "string"},
                            "b": {"type": "string"},
                        },
                        "required": ["a"],
                    }
                },
                "required": [],
            },
        ),
    )
    rendered = utils.tools_to_catalog(tools)

    assert "Gồm các trường: a*, b." in rendered
    assert utils.catalog_to_tools(rendered).tools[0].properties["who"]["required"] == [
        "a"
    ]


# --- the name convention ------------------------------------------------------


def test_names_a_stricter_pattern_would_reject_are_real_entries() -> None:
    """The convention deciding whether 841 and 722 records are invalid or none are."""
    parsed = utils.catalog_to_tools(text_of("odd_names.txt"))

    assert parsed.names == (
        "card.search_faq",
        "end-call",
        "calculate BMI",
        "calculate_triangl\te_area",
    )
    assert all(tool.description for tool in parsed.tools)


def test_a_bracketed_phrase_inside_prose_is_not_an_entry() -> None:
    parsed = utils.catalog_to_tools(text_of("bracket_inside_prose.txt"))

    assert parsed.names == ("Lookup00_0a",)
    assert "[Phụ lục A]" in parsed.tools[0].description


def test_a_malformed_entry_still_contributes_its_name() -> None:
    """Not an exception and not a partial catalog: the tool set stays complete."""
    parsed = utils.catalog_to_tools(text_of("entry_missing_clauses.txt"))

    assert parsed.names == ("Bare_01a", "Full_02b")
    assert parsed.tools[0].description == ""
    assert parsed.tools[0].properties == {}
    assert parsed.tools[1].description


def test_a_message_with_no_header_is_an_empty_catalog_not_an_exception() -> None:
    assert not utils.catalog_to_tools(text_of("no_tools_header.txt")).tools


# --- what the reader could not recover ----------------------------------------


def test_the_reader_reports_what_it_could_not_be_given() -> None:
    """A format reader that returns less than it was given must say so."""
    gaps: list[utils.Gap] = []

    utils.catalog_to_tools(text_of("one_tool.txt"), gaps=gaps)

    assert [gap.kind for gap in gaps] == []


def test_an_enum_stated_only_in_prose_is_reported_rather_than_guessed() -> None:
    source = text_of("one_tool.txt").replace(
        "Mã khách hàng cần tra cứu.", "Mã khách hàng. chỉ chấp nhận VIP hoặc STANDARD."
    )
    gaps: list[utils.Gap] = []

    utils.catalog_to_tools(source, gaps=gaps)

    assert [(g.parameter, g.kind) for g in gaps] == [
        ("ma_khach", "enum_stated_in_prose")
    ]


def test_the_require_line_is_the_fallback_when_a_star_is_missing() -> None:
    """Two statements of requiredness; the stars win and the line covers for them."""
    starless = text_of("one_tool.txt").replace(
        "ma_khach* (string)", "ma_khach (string)"
    )

    (tool,) = utils.catalog_to_tools(starless).tools

    assert tool.required == ("ma_khach",)


def test_a_tool_whose_parameters_are_all_optional_is_reported() -> None:
    both_removed = (
        text_of("one_tool.txt")
        .replace("ma_khach* (string)", "ma_khach (string)")
        .replace("require: ma_khach", "require: ")
    )
    gaps: list[utils.Gap] = []

    (tool,) = utils.catalog_to_tools(both_removed, gaps=gaps).tools

    assert tool.required == ()
    assert "nothing_required" in [gap.kind for gap in gaps]


def test_to_strict_openai_emits_only_standard_openai_keys() -> None:
    (tool,) = utils.catalog_to_tools(text_of("one_tool.txt")).tools

    emitted = utils.to_strict_openai(tool)

    assert set(emitted) == {"type", "function"}
    assert set(emitted["function"]) <= {"name", "description", "parameters"}
    assert emitted["type"] == "function"


def test_only_one_module_in_the_system_parses_a_rendered_catalog() -> None:
    """The 93 µs parse cannot quietly become one per stage.

    `read_catalog` is the one caller, and it is in the module that defines the grammar.
    This is the check on requirement 71's cost argument: the reason no record stores its
    answer space is that deriving one is free where the catalog is data and paid once
    where it is prose -- and a second caller of the parser is what would make the second
    half of that false, silently, from anywhere.
    """
    callers = set()
    for path, tree in parsed_sources():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            named = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if named == "catalog_to_tools":
                callers.add(path.relative_to(SOURCE_ROOT).as_posix())

    assert callers == {"profiles/tool_decision/utils.py"}, callers


def test_the_two_ways_a_source_carries_a_catalog_agree() -> None:
    """`openai_to_tools` and `catalog_to_tools` are the two, and `read_catalog` picks.

    Losslessness in this direction is what makes a rendered catalog a way *in* rather
    than a second format to maintain.
    """
    parsed = utils.catalog_to_tools(text_of("eight_tools.txt"))

    as_data = [utils.to_strict_openai(tool) for tool in parsed.tools]

    assert utils.openai_to_tools(as_data) == parsed
