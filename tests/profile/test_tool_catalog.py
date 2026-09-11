"""`openai_tool_format_to_text` pinned against its known rendering.

One renderer stands behind both halves of the flow, so a reviewer and a juror cannot
disagree about the catalog they read. That makes this text a contract with two parties and no
schema: every character of it reaches a person on the page and a model in a prompt, and the module
was finished with nothing asserting any of it.

Four rules are pinned, and two of them the JSON Schema does not state. A required param that also
declares a `default` is a contradiction, and the default wins -- so it renders unmarked and out of
`require:`. An object param lists its subfields inline while they are plain strings and puts them on
their own deeper lines the moment one carries a type, a description, an enum or a default: **all
five triggers, one case each**, because a fixture stacking two of them proves neither. A default is
written the way a reviewer reads it, which for a boolean and an empty list is not what `str()`
gives. And property order is the order given -- § *Invariants*: text re-rendered from the same tools
is byte-identical, which both a sort and a walk of the `required` list would still satisfy while
handing a reviewer a different catalog than the one the tools declare.

Every case below is written to fail on its own. A case that only re-reads a substring of the
whole-catalog pin documents a rule without holding it.
"""

import pytest

from dataforce.profile.tool_decision.utils import openai_tool_format_to_text

# `add_bag` is given second, so the pinned order is not also the alphabetical one.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_flight",
            "description": "Đặt vé máy bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Thành phố đến."},
                    "cabin": {
                        "type": "string",
                        "description": "Hạng ghế.",
                        "enum": ["economy", "business"],
                        "default": "economy",
                    },
                    "passenger": {
                        "type": "object",
                        "description": "Người bay.",
                        "properties": {
                            "name": {"type": "string"},
                            "phone": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                    "seats": {
                        "type": "array",
                        "description": "Chỗ ngồi mong muốn.",
                        "items": {"type": "string", "enum": ["aisle", "window"]},
                    },
                },
                "required": ["destination", "cabin", "passenger"],
            },
        },
    },
    {
        "name": "add_bag",
        "description": "Thêm hành lý.",
        "parameters": {
            "type": "object",
            "properties": {
                "bag": {
                    "type": "object",
                    "description": "Hành lý ký gửi.",
                    "properties": {
                        "size": {"type": "string", "enum": ["cabin", "checked"]},
                        "count": {"type": "integer", "default": 1},
                    },
                    "required": ["size", "count"],
                }
            },
            "required": ["bag"],
        },
    },
]

RENDERED = """[book_flight]
Đặt vé máy bay.
require: destination, passenger
params:
  destination* (string): Thành phố đến.
  cabin (string): Hạng ghế. Giá trị khả dụng: economy, business. Nếu khách không đề cập, mặc định là economy.
  passenger* (object): Người bay. Gồm các trường: name*, phone.
  seats (array): Chỗ ngồi mong muốn. Giá trị khả dụng: aisle, window.

[add_bag]
Thêm hành lý.
require: bag
params:
  bag* (object): Hành lý ký gửi.
    size* (string): Giá trị khả dụng: cabin, checked.
    count (integer): Nếu khách không đề cập, mặc định là 1."""

# One object param, deepened. `{}` is the `phone` line the deepening cases differ by.
DEEPENED = """[f]
require: passenger
params:
  passenger* (object): Người bay.
    name* (string):
{}"""


def one_tool(properties: dict[str, object], required: list[str]) -> dict[str, object]:
    """One tool holding nothing but the params a case is about."""
    return {
        "name": "f",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def passenger_tool(phone: dict[str, object]) -> dict[str, object]:
    """One object param whose `phone` subfield is what a deepening case changes."""
    return one_tool(
        {
            "passenger": {
                "type": "object",
                "description": "Người bay.",
                "properties": {"name": {"type": "string"}, "phone": phone},
                "required": ["name"],
            }
        },
        ["passenger"],
    )


def test_the_catalog_renders_character_for_character() -> None:
    """The whole contract, pinned. A change to any character of it is a change to this literal."""
    assert openai_tool_format_to_text(TOOLS) == RENDERED


def test_a_required_param_carrying_a_default_is_optional_and_unmarked() -> None:
    """The default wins, so the param is out of `require:` and carries no `*`.

    Its own fixture, where `where` is the only required param declared -- so a rendering that
    marked it has nothing else to hide behind.
    """
    tool = one_tool(
        {"where": {"type": "string", "description": "Ở đâu.", "default": "Hà Nội"}},
        ["where"],
    )

    assert openai_tool_format_to_text([tool]) == (
        "[f]\n"
        "require: \n"
        "params:\n"
        "  where (string): Ở đâu. Nếu khách không đề cập, mặc định là Hà Nội."
    )


def test_a_required_subfield_carrying_a_default_is_optional_too() -> None:
    """The same rule one level down, where a second `required` list applies it."""
    assert openai_tool_format_to_text(
        [passenger_tool({"type": "string", "default": "+84"})]
    ) == DEEPENED.format("    phone (string): Nếu khách không đề cập, mặc định là +84.")


def test_plain_string_subfields_render_inline() -> None:
    """`Gồm các trường` holds names and a `*`, which is all these subfields carry."""
    assert openai_tool_format_to_text([passenger_tool({"type": "string"})]) == (
        "[f]\n"
        "require: passenger\n"
        "params:\n"
        "  passenger* (object): Người bay. Gồm các trường: name*, phone."
    )


@pytest.mark.parametrize(
    ("phone", "line"),
    [
        ({"type": "integer"}, "    phone (integer):"),
        (
            {"type": "string", "description": "Số điện thoại."},
            "    phone (string): Số điện thoại.",
        ),
        (
            {"type": "string", "enum": ["+84", "+66"]},
            "    phone (string): Giá trị khả dụng: +84, +66.",
        ),
        (
            {"type": "string", "default": "+84"},
            "    phone (string): Nếu khách không đề cập, mặc định là +84.",
        ),
        ({"items": {"enum": ["+84"]}}, "    phone (string):"),
    ],
    ids=["a-type", "a-description", "an-enum", "a-default", "an-enum-under-items"],
)
def test_one_subfield_gaining_anything_moves_them_all_to_their_own_lines(
    phone: dict[str, object], line: str
) -> None:
    """Five triggers, one case each. The inline form cannot hold any of them.

    `name` goes deep too, though it gained nothing: the form is per object, not per subfield. One
    fixture carrying two triggers at once passes with either of them unimplemented, which is how
    four of these five went unpinned when the whole catalog was the only assertion.

    `an-enum-under-items` declares no `type`, which is the only way to reach that branch: an
    `items` under a declared `array` is already a non-string type, so the first branch answers it.
    Its deeper line then shows no enum -- the values are read from `items` only for a declared
    `array` -- so the trigger fires and prints nothing. Pinned as it behaves, and reported.
    """
    assert openai_tool_format_to_text([passenger_tool(phone)]) == DEEPENED.format(line)


@pytest.mark.parametrize(
    ("default", "written"),
    [
        (True, "true"),
        (False, "false"),
        ([], "[]"),
        (["a", "b"], "a, b"),
        (1, "1"),
        ("economy", "economy"),
    ],
    ids=["true", "false", "an-empty-list", "a-list", "a-number", "a-string"],
)
def test_a_default_is_written_the_way_a_reviewer_reads_it(
    default: object, written: str
) -> None:
    """A boolean is `true`/`false` and not Python's `True`, and an empty list says `[]`.

    Both reach a model in a prompt, so `str()` on either is a rendering a reviewer and a juror read
    differently from the schema they came from.
    """
    tool = one_tool({"p": {"type": "string", "default": default}}, [])

    assert openai_tool_format_to_text([tool]) == (
        "[f]\n"
        "require: \n"
        "params:\n"
        f"  p (string): Nếu khách không đề cập, mặc định là {written}."
    )


def test_two_tools_render_in_the_order_given() -> None:
    """The blocks follow the array: a sort fails the first line, a reversal the second."""
    assert openai_tool_format_to_text(TOOLS).startswith("[book_flight]")
    assert openai_tool_format_to_text(list(reversed(TOOLS))).startswith("[add_bag]")


def test_property_order_is_the_order_declared() -> None:
    """§ *Invariants*, and `require:` reads that order too.

    `required` is declared back to front here, so a `require:` line walking that list rather than
    the properties renders `second, first`. Both spellings re-render byte-identically, and only one
    of them is the catalog the tools declare.
    """
    tool = one_tool(
        {
            "first": {"type": "string", "description": "Một."},
            "second": {"type": "string", "description": "Hai."},
        },
        ["second", "first"],
    )

    assert openai_tool_format_to_text([tool]) == (
        "[f]\n"
        "require: first, second\n"
        "params:\n"
        "  first* (string): Một.\n"
        "  second* (string): Hai."
    )


def test_an_entry_without_a_name_is_left_out_and_the_rest_still_render() -> None:
    """An unreadable tool is one entry, not a reason to render none of them."""
    entries = [
        {"name": "a"},
        {"description": "no name"},
        "not a mapping",
        {"name": "b"},
    ]

    assert openai_tool_format_to_text(entries) == "[a]\n\n[b]"
