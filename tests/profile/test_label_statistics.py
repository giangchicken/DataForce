"""What this task's label can be measured by: is it a callable call, and what does the corpus cover.

`list_label_faults` is BFCL's AST check turned on the corpus rather than on a model. A label
calling a tool the sample was never offered is a broken row, and a row nobody notices is one a
buyer finds. The checks read **this row's own catalog**, so nothing here depends on a corpus-wide
list of tools.

It answers sentences and not a boolean because two readers want different halves of it: the store
writes `schema_valid` from whether it came back empty, and the page puts the sentences in front of
a reviewer before they say the label is correct. So the sentences are checked here too -- a fault
that does not name which call it is about is one nobody can act on.
"""

from typing import Any

import pytest

from dataforce.profile.tool_decision.label_statistics import (
    count_tool_calls,
    list_called_tools,
    list_label_faults,
    list_offered_tools,
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


def build_call(name: str, arguments: Any) -> dict[str, Any]:
    """One call in the format the catalog and the label are both written in."""
    return {"type": "function", "function": {"name": name, "arguments": arguments}}


def test_the_tools_a_label_calls_come_back_in_call_order() -> None:
    """Order is the sample's, because two calls at once are a turn and not a set."""
    label = (build_call("OpenTicket", {}), build_call("Lookup", {"ma_khach": "KH-1"}))
    assert list_called_tools(label) == ("OpenTicket", "Lookup")


def test_a_call_naming_a_tool_the_sample_never_offered_is_a_broken_row() -> None:
    """Not a hard example: nothing in the row could have produced that call."""
    faults = list_label_faults((build_call("Refund", {"so_tien": 1}),), CATALOG)
    assert faults == (
        "call 1 names Refund, which this sample's catalog does not offer",
    )


def test_a_call_missing_a_required_parameter_says_which_parameter() -> None:
    """`ma_khach` is what the catalog says the tool cannot be called without.

    Named in the sentence, because *this label is invalid* sends a reviewer back to read the
    catalog and *leaves out ma_khach* sends them to the one word they have to type.
    """
    assert list_label_faults((build_call("Lookup", {"kenh": "app"}),), CATALOG) == (
        "call 1 to Lookup leaves out ma_khach, which it requires",
    )


def test_a_call_missing_an_optional_parameter_is_valid() -> None:
    """`kenh` is offered, not demanded, so a call leaving it out is a call."""
    assert (
        list_label_faults((build_call("Lookup", {"ma_khach": "KH-1"}),), CATALOG) == ()
    )


def test_a_required_parameter_that_declares_a_default_is_not_required() -> None:
    """The catalog a model was shown leaves `ngay` out of `require:`, so the check does too."""
    assert "ngay" in LOOKUP["function"]["parameters"]["required"]  # type: ignore[index]
    assert (
        list_label_faults((build_call("Lookup", {"ma_khach": "KH-1"}),), CATALOG) == ()
    )


def test_arguments_written_as_json_text_are_read_as_the_same_call() -> None:
    """A provider writes them as text and a corpus writes the object; one call either way."""
    written = build_call("Lookup", '{"ma_khach": "KH-1"}')
    assert list_label_faults((written,), CATALOG) == ()


def test_an_entry_that_names_no_tool_is_not_a_call() -> None:
    """A label holding something that is not a call is a broken row, not an empty one."""
    assert list_label_faults(({"arguments": {"ma_khach": "KH-1"}},), CATALOG) == (
        'call 1 does not read as a tool call: it has to be {"name": ..., "arguments": {...}}',
    )


def test_a_bare_tool_name_is_told_what_a_call_is_made_of() -> None:
    """**The shape a corpus really arrives in**, and the one this whole check exists for.

    `["VerifyEmail_15d"]` is a corpus that recorded *which tool fires* and stopped. Telling the
    reviewer looking at it that the entry is unreadable says nothing they can act on; telling them
    what a call has to read as does.
    """
    assert list_label_faults(("Lookup",), CATALOG) == (
        'call 1 does not read as a tool call: it has to be {"name": ..., "arguments": {...}}',
    )


def test_every_broken_call_is_named_by_its_position_in_the_label() -> None:
    """A label makes more than one call, and *which one* is the first thing a fixer needs.

    All of them and not the first: a reviewer who fixed call 1 and posted again, only to be told
    about call 3, has been sent round the loop once per fault.
    """
    faults = list_label_faults(
        (
            build_call("Lookup", {"ma_khach": "KH-1"}),
            "Refund",
            build_call("Lookup", {}),
        ),
        CATALOG,
    )
    assert len(faults) == 2
    assert faults[0].startswith("call 2 ")
    assert faults[1].startswith("call 3 ")


def test_a_tool_whose_parameters_will_not_read_clears_no_call() -> None:
    """The catalog comes back out of a JSON column, so one junk entry must not raise here.

    A whole corpus of statistics answers through this function; a tool nothing can read is one
    tool no call can be cleared against, not a reason to answer nothing.
    """
    unreadable = {"type": "function", "function": {"name": "L", "parameters": "{}"}}
    assert list_label_faults((build_call("L", {}),), (unreadable,)) == (
        "call 1 names L, which this sample's catalog does not offer",
    )
    assert list_label_faults((), (unreadable, *CATALOG)) == ()
    assert (
        list_label_faults(
            (build_call("Lookup", {"ma_khach": "KH-1"}),), (unreadable, *CATALOG)
        )
        == ()
    )


def test_an_empty_label_is_valid_however_it_is_spelled() -> None:
    """A sample needing no call is an answer. Both spellings, because neither is settled."""
    assert list_label_faults((), CATALOG) == ()
    assert list_label_faults(None, CATALOG) == ()


def test_the_counts_say_what_is_offered_and_what_is_ever_called() -> None:
    """The tail is the finding, so the count per tool is the answer and not the share."""
    labels: list[Any] = [
        (build_call("Lookup", {"ma_khach": "KH-1"}),),
        (build_call("Lookup", {"ma_khach": "KH-2"}),),
        (),
    ]
    assert count_tool_calls(labels, [CATALOG, CATALOG, CATALOG]) == {
        "Lookup": 2,
        "OpenTicket": 0,
    }


def test_a_catalog_for_every_label_or_the_corpus_was_read_wrong() -> None:
    """The two come out of one query as two columns; a length apart silently truncates them."""
    with pytest.raises(ValueError):
        count_tool_calls([(), ()], [CATALOG])


def test_a_tool_offered_and_never_called_is_a_zero_and_not_an_absence() -> None:
    """The corpus's hole has to be visible, so it is a key with `0` rather than a missing key."""
    assert count_tool_calls([()], [CATALOG]) == {"Lookup": 0, "OpenTicket": 0}


def test_a_tool_called_without_being_offered_is_counted_rather_than_dropped() -> None:
    """It is a broken row and the count says so; `schema_valid` is what marks the row itself."""
    assert count_tool_calls([(build_call("Ghost", {}),)], [CATALOG]) == {
        "Ghost": 1,
        "Lookup": 0,
        "OpenTicket": 0,
    }


def test_a_tool_a_label_invented_is_not_one_that_was_offered() -> None:
    """§ *Tools offered and tools called* asks for *distinct tools offered*, and `count_tool_calls`'s keys cannot say
    it: a name a broken row called is in there too, with its count. Counting those keys would
    report an offer nobody made, which is the number the zeros are read against."""
    catalogs = [list(CATALOG)]
    labels = [[{"name": "Invented", "arguments": {}}]]

    assert list_offered_tools(catalogs) == ("Lookup", "OpenTicket")
    assert set(count_tool_calls(labels, catalogs)) == {
        "Lookup",
        "OpenTicket",
        "Invented",
    }


def test_the_same_tool_offered_by_every_row_is_offered_once() -> None:
    """Distinct: a catalog handed to a thousand samples is one offer, not a thousand."""
    assert list_offered_tools([[LOOKUP], [LOOKUP], [LOOKUP]]) == ("Lookup",)
