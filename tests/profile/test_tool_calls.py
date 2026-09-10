"""`text_to_openai_tool_format` pinned: what a model wrote, read back as calls.

The shape is the format's own -- `{"type": "function", "function": {"name", "arguments"}}` with the
arguments as JSON text -- so what comes out of here is what a provider would be sent.

The other direction of `openai_tool_format_to_text`, and the reason the panel needs no judge --
two answers are one where the calls in them are the same calls (spec § *Requirements* 21). What
that means is all in here: which spellings of a call are one call, and which are two.

The panel's own matrix reads these rules through `normalize_prediction`, which compares two
answers as strings and so cannot see the shape they were read into. These read the shape.
"""

from dataforce.profile.tool_decision.utils import text_to_openai_tool_format

# The format's own shape: the arguments as JSON text, under one key ordering.
OPEN_TICKET = {
    "type": "function",
    "function": {"name": "OpenTicket", "arguments": '{"ma_khach":"KH-1"}'},
}


def test_a_call_is_read_as_the_format() -> None:
    """The shape every other case is a spelling of: the call, and nothing that is not the call."""
    assert text_to_openai_tool_format(
        '[{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}]'
    ) == (OPEN_TICKET,)


def test_the_wire_format_s_own_wrapper_is_the_same_call() -> None:
    """A juror may answer in the format it was shown; `openai_tool_format_to_text` is as lenient."""
    assert text_to_openai_tool_format(
        '[{"type": "function", "id": "call_1", "function":'
        ' {"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}}]'
    ) == (OPEN_TICKET,)


def test_the_id_a_provider_hangs_on_a_call_is_not_part_of_it() -> None:
    """Two jurors calling one tool must not differ by a string neither of them chose."""
    assert text_to_openai_tool_format(
        '[{"type": "function", "id": "call_9", "name": "OpenTicket",'
        ' "arguments": {"ma_khach": "KH-1"}}]'
    ) == (OPEN_TICKET,)


def test_arguments_written_as_json_text_are_the_same_call() -> None:
    """The provider's wire format writes them as text; a corpus writes the object. One call.

    Both are read and written back as the format's own text, which is what makes them one.
    """
    assert text_to_openai_tool_format(
        '[{"name": "OpenTicket", "arguments": "{\\"ma_khach\\": \\"KH-1\\"}"}]'
    ) == (OPEN_TICKET,)


def test_the_arguments_are_written_under_one_key_ordering() -> None:
    """The reason the text is written and not passed through: two orderings are one call."""
    assert text_to_openai_tool_format(
        '[{"name": "Book", "arguments": {"den": "SGN", "di": "HAN"}}]'
    ) == text_to_openai_tool_format(
        '[{"name": "Book", "arguments": {"di": "HAN", "den": "SGN"}}]'
    )


def test_arguments_that_will_not_parse_stay_as_the_text() -> None:
    """It is what the model said, and nothing here reads it better than that."""
    assert text_to_openai_tool_format(
        '[{"name": "OpenTicket", "arguments": "KH-1"}]'
    ) == (
        {"type": "function", "function": {"name": "OpenTicket", "arguments": "KH-1"}},
    )


def test_a_call_with_no_arguments_carries_the_empty_object() -> None:
    """A tool that takes none, and a model that wrote the key as null, are the same call."""
    assert text_to_openai_tool_format(
        '[{"name": "ListTickets"}, {"name": "X", "arguments": null}]'
    ) == (
        {"type": "function", "function": {"name": "ListTickets", "arguments": "{}"}},
        {"type": "function", "function": {"name": "X", "arguments": "{}"}},
    )


def test_prose_around_the_array_is_still_those_calls() -> None:
    """A model that explained itself before answering answered (`extract_json_from_text`)."""
    assert text_to_openai_tool_format(
        'Đây là kết luận của tôi: [{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}]'
    ) == (OPEN_TICKET,)


def test_a_call_with_no_name_costs_only_itself() -> None:
    """One unreadable entry is one entry, not a reason to read none of them -- as the catalog is."""
    assert text_to_openai_tool_format(
        '[{"arguments": {"ma_khach": "KH-1"}},'
        ' {"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}]'
    ) == (OPEN_TICKET,)


def test_one_call_written_alone_is_read_without_its_array() -> None:
    """`tool_prediction.txt` asks for an array; a model that wrote the object still called it."""
    assert text_to_openai_tool_format(
        '{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}'
    ) == (OPEN_TICKET,)


def test_an_answer_with_no_call_in_it_is_no_calls() -> None:
    """`[]` is the answer that no tool is needed, and prose is a model that answered in prose.

    Both read as no calls, which is why `normalize_prediction` cannot match on this alone: it
    falls back to what the answer says, or every prose would agree with `[]`.
    """
    assert text_to_openai_tool_format("[]") == ()
    assert text_to_openai_tool_format("không cần gọi tool nào") == ()
