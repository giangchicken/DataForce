"""What this task's label can be measured by: is it a valid call, and what does the corpus cover.

`schema_valid_label` is BFCL's AST check turned on the corpus rather than on a model. A label
calling a tool the sample was never offered is a broken row, and a row nobody notices is one a
buyer finds. The checks read **this row's own catalog**, so nothing here depends on a corpus-wide
list of tools.
"""

from typing import Any

import pytest

from dataforce.profile.tool_decision.dataset_management.label_statistics import (
    call_counts,
    called_tools,
    schema_valid_label,
    tool_coverage,
)

LOOKUP = {
    "type": "function",
    "function": {
        "name": "Lookup",
        "description": "Tra cứu công nợ",
        "parameters": {
            "type": "object",
            "properties": {
                "ma_khach": {"type": "string"},
                "kenh": {"type": "string"},
                "ngay": {"type": "string", "default": "hom_nay"},
            },
            "required": ["ma_khach", "ngay"],
        },
    },
}
OPEN_TICKET = {
    "type": "function",
    "function": {"name": "OpenTicket", "parameters": {"type": "object"}},
}
CATALOG = (LOOKUP, OPEN_TICKET)


def call(name: str, arguments: Any) -> dict[str, Any]:
    """One call in the format the catalog and the label are both written in."""
    return {"type": "function", "function": {"name": name, "arguments": arguments}}


def test_the_tools_a_label_calls_come_back_in_call_order() -> None:
    """Order is the sample's, because two calls at once are a turn and not a set."""
    label = (call("OpenTicket", {}), call("Lookup", {"ma_khach": "KH-1"}))
    assert called_tools(label) == ("OpenTicket", "Lookup")


def test_a_call_naming_a_tool_the_sample_never_offered_is_a_broken_row() -> None:
    """Not a hard example: nothing in the row could have produced that call."""
    assert schema_valid_label((call("Refund", {"so_tien": 1}),), CATALOG) is False


def test_a_call_missing_a_required_parameter_is_invalid() -> None:
    """`ma_khach` is what the catalog says the tool cannot be called without."""
    assert schema_valid_label((call("Lookup", {"kenh": "app"}),), CATALOG) is False


def test_a_call_missing_an_optional_parameter_is_valid() -> None:
    """`kenh` is offered, not demanded, so a call leaving it out is a call."""
    assert schema_valid_label((call("Lookup", {"ma_khach": "KH-1"}),), CATALOG) is True


def test_a_required_parameter_that_declares_a_default_is_not_required() -> None:
    """The catalog a model was shown leaves `ngay` out of `require:`, so the check does too."""
    assert "ngay" in LOOKUP["function"]["parameters"]["required"]  # type: ignore[index]
    assert schema_valid_label((call("Lookup", {"ma_khach": "KH-1"}),), CATALOG) is True


def test_arguments_written_as_json_text_are_read_as_the_same_call() -> None:
    """A provider writes them as text and a corpus writes the object; one call either way."""
    written = call("Lookup", '{"ma_khach": "KH-1"}')
    assert schema_valid_label((written,), CATALOG) is True


def test_an_entry_that_names_no_tool_is_not_a_call() -> None:
    """A label holding something that is not a call is a broken row, not an empty one."""
    assert schema_valid_label(({"arguments": {"ma_khach": "KH-1"}},), CATALOG) is False


def test_a_tool_whose_parameters_will_not_read_clears_no_call() -> None:
    """The catalog comes back out of a JSON column, so one junk entry must not raise here.

    A whole corpus of statistics answers through this function; a tool nothing can read is one
    tool no call can be cleared against, not a reason to answer nothing.
    """
    unreadable = {"type": "function", "function": {"name": "L", "parameters": "{}"}}
    assert schema_valid_label((call("L", {}),), (unreadable,)) is False
    assert schema_valid_label((), (unreadable, *CATALOG)) is True
    assert schema_valid_label(
        (call("Lookup", {"ma_khach": "KH-1"}),), (unreadable, *CATALOG)
    )


def test_an_empty_label_is_valid_however_it_is_spelled() -> None:
    """A sample needing no call is an answer. Both spellings, because neither is settled."""
    assert schema_valid_label((), CATALOG) is True
    assert schema_valid_label(None, CATALOG) is True


def test_call_counts_tell_no_call_from_one_call_from_several() -> None:
    """`0` is counted rather than treated as missing; `2` is one turn answered at once."""
    labels = [
        None,
        (),
        (call("Lookup", {"ma_khach": "KH-1"}),),
        (call("Lookup", {"ma_khach": "KH-1"}), call("OpenTicket", {})),
    ]
    assert call_counts(labels) == {0: 2, 1: 1, 2: 1}


def test_tool_coverage_answers_what_is_offered_and_what_is_ever_called() -> None:
    """The tail is the finding, so the count per tool is the answer and not the share."""
    labels: list[Any] = [
        (call("Lookup", {"ma_khach": "KH-1"}),),
        (call("Lookup", {"ma_khach": "KH-2"}),),
        (),
    ]
    assert tool_coverage(labels, [CATALOG, CATALOG, CATALOG]) == {
        "Lookup": 2,
        "OpenTicket": 0,
    }


def test_a_catalog_for_every_label_or_the_corpus_was_read_wrong() -> None:
    """The two come out of one query as two columns; a length apart silently truncates them."""
    with pytest.raises(ValueError):
        tool_coverage([(), ()], [CATALOG])


def test_a_tool_offered_and_never_called_is_a_zero_and_not_an_absence() -> None:
    """The corpus's hole has to be visible, so it is a key with `0` rather than a missing key."""
    assert tool_coverage([()], [CATALOG]) == {"Lookup": 0, "OpenTicket": 0}


def test_a_tool_called_without_being_offered_is_counted_rather_than_dropped() -> None:
    """It is a broken row and the count says so; `schema_valid` is what marks the row itself."""
    assert tool_coverage([(call("Ghost", {}),)], [CATALOG]) == {
        "Ghost": 1,
        "Lookup": 0,
        "OpenTicket": 0,
    }
