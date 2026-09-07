"""`openai_tool_format_to_text` pinned against its known rendering.

Decision 8 puts one renderer behind both halves of the flow, so a reviewer and a juror cannot
disagree about the catalog they read. That makes this text a contract with two parties and no
schema: every character of it reaches a person on the page and a model in a prompt, and the module
was finished with nothing asserting any of it.

Three rules are pinned, and two of them the JSON Schema does not state. A required param that also
declares a `default` is a contradiction, and the default wins -- so it renders unmarked and out of
`require:`. An object param lists its subfields inline while they are plain strings and puts them on
their own deeper lines the moment one carries a type, a description, an enum or a default. And
property order is the order given -- § *Invariants*: text re-rendered from the same tools is
byte-identical, which a sort over a dict would still satisfy while sending a reviewer a different
catalog than the one the tools declare.
"""

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


def passenger_tool(phone: dict[str, object]) -> dict[str, object]:
    """One object param, with `phone` as the one subfield the two inline cases differ by."""
    return {
        "name": "book_flight",
        "parameters": {
            "type": "object",
            "properties": {
                "passenger": {
                    "type": "object",
                    "description": "Người bay.",
                    "properties": {"name": {"type": "string"}, "phone": phone},
                    "required": ["name"],
                }
            },
            "required": ["passenger"],
        },
    }


PLAIN = {"type": "string"}
WITH_AN_ENUM = {"type": "string", "enum": ["+84", "+66"]}


def test_the_catalog_renders_character_for_character() -> None:
    """The whole contract, pinned. A change to any character of it is a change to this literal."""
    assert openai_tool_format_to_text(TOOLS) == RENDERED


def test_a_required_param_carrying_a_default_is_optional_and_unmarked() -> None:
    """`cabin` is in the schema's `required` and declares a default, so the default wins."""
    rendered = openai_tool_format_to_text(TOOLS)

    assert "require: destination, passenger" in rendered
    assert "  cabin (string): Hạng ghế." in rendered
    assert "cabin*" not in rendered


def test_a_required_subfield_carrying_a_default_is_optional_too() -> None:
    """The same rule one level down: `count` is required by `bag` and declares a default."""
    assert "    count (integer): Nếu khách không đề cập" in openai_tool_format_to_text(
        TOOLS
    )


def test_plain_string_subfields_render_inline() -> None:
    """`Gồm các trường` holds names and a `*`, which is all these subfields carry."""
    assert openai_tool_format_to_text([passenger_tool(PLAIN)]) == (
        "[book_flight]\n"
        "require: passenger\n"
        "params:\n"
        "  passenger* (object): Người bay. Gồm các trường: name*, phone."
    )


def test_one_subfield_gaining_an_enum_moves_them_all_to_their_own_lines() -> None:
    """The inline form cannot hold an enum, so every subfield goes deep -- not only the one."""
    assert openai_tool_format_to_text([passenger_tool(WITH_AN_ENUM)]) == (
        "[book_flight]\n"
        "require: passenger\n"
        "params:\n"
        "  passenger* (object): Người bay.\n"
        "    name* (string):\n"
        "    phone (string): Giá trị khả dụng: +84, +66."
    )


def test_two_tools_render_in_the_order_given() -> None:
    """Reversing the array reverses the blocks, so the order is the array's and not a sort's."""
    forward = openai_tool_format_to_text(TOOLS)
    backward = openai_tool_format_to_text(list(reversed(TOOLS)))

    assert backward != forward
    assert backward.split("\n\n") == list(reversed(forward.split("\n\n")))


def test_property_order_is_the_order_declared() -> None:
    """§ *Invariants*. A sort would re-render byte-identically and still be a different catalog."""
    reordered = {
        "name": "book_flight",
        "parameters": {
            "type": "object",
            "properties": {
                "seats": {"type": "string", "description": "Chỗ ngồi mong muốn."},
                "destination": {"type": "string", "description": "Thành phố đến."},
            },
            "required": ["seats", "destination"],
        },
    }

    assert openai_tool_format_to_text([reordered]) == (
        "[book_flight]\n"
        "require: seats, destination\n"
        "params:\n"
        "  seats* (string): Chỗ ngồi mong muốn.\n"
        "  destination* (string): Thành phố đến."
    )
