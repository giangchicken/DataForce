"""LOGIC · one turn as one part: what it said, what it called, and the string that holds both.

A turn arrives in the shape Requirement 13 declares and leaves as a ``Part``. Every form one can
arrive in is read here and nowhere else: ``content`` may be a string, a null or a content-block
array, and a call's ``arguments`` may be a JSON string or the object that string means.

**A turn that both speaks and calls joins the two on ``record.SPOKEN_AND_STATED``**, which is the
record's constant and not this module's, because ``tool_decision`` reads the calls back off it and a
convention spelled here and assumed there is connascence of meaning across a boundary neither side
may import. ``record.py``'s docstring says why it lives there, and one test in
``tests/stages/test_tool_decision.py`` builds a turn through this module and reads it through that
one, so neither end can move alone.

**A tool-call turn is rendered here, and that is content rather than an answer.** ``messages`` holds
the conversation and *nothing in it is an answer* (Requirement 13); an assistant turn that already
called a tool is context like any other. Requirement 15 asks that one call spelled three ways --
arguments as a JSON string, the same string reordered and re-spaced, and the object form -- be one
part and one ``record_id``, so the rendering is canonical JSON over the parsed arguments. What a
call *means* is still the profile's (Requirement 47): this module writes a turn down, it does not
decide what an answer is.

**A turn declaring no ``role`` raises, and Requirement 43 says nothing may.** ``modality.py`` carries
the argument for both of this axis's raises. The short of it is that ``a_turn`` returns a ``Part``
and has no value channel for *this turn is unreadable*, ``load_data`` is the only caller that knows
the offset, and T14 settled it there by catching the raise and counting it against the item. A
non-string ``content`` is **not** in that category and does not raise: the content-block form is the
same standard Requirement 13 declares, so an item carrying one is a declared item and becomes a
record.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.errors import ConfigError
from dataforce.record import SPOKEN_AND_STATED, Part, canonical_json

# The declared source shape's keys, as one turn spells them.
ROLE = "role"
CONTENT = "content"
TOOL_CALLS = "tool_calls"
FUNCTION = "function"
ARGUMENTS = "arguments"
NAME = "name"
TEXT = "text"


def spoken_text(content: Any) -> str:
    """What a turn said, whatever shape its `content` arrived in.

    A string is copied verbatim (Requirement 16) and a null turn said nothing. A **list** is the
    content-block form the same OpenAI shape declares -- `[{"type": "text", "text": "…"}]` -- and
    Requirement 13 declares that shape, so an item carrying one is a declared item and becomes a
    record. A text block contributes its text; any other block contributes its canonical JSON,
    which keeps it inside `record_id` instead of dropping it, and puts it where `label_check` and
    triage can see it. No separator is inserted between blocks, because any choice of one would be
    invented here and would change what a `record_id` covers.

    Blocks are joined rather than refused even where one of them is an image: a media block in a
    text2text run is a mis-composed pair, and the place that says so is `text_parts`, on a part
    whose *type* is not text -- refusing here would be a per-record raise on a readable item.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block[TEXT]
            if isinstance(block, Mapping) and isinstance(block.get(TEXT), str)
            else canonical_json(block)
            for block in content
        )
    return canonical_json(content)


def stated_calls(calls: Sequence[Mapping[str, Any]]) -> str:
    """The calls a turn made, canonically, so Requirement 15's three spellings are one string.

    A call whose shape the declared input does not match is written down as it arrived rather than
    refused: a malformed turn is evidence for `label_check` to find, and a run always completes
    (Requirement 43).
    """
    return canonical_json(
        [
            {NAME: named.get(NAME, ""), ARGUMENTS: call_arguments(named.get(ARGUMENTS))}
            for call in calls
            for named in [call.get(FUNCTION) or {}]
        ]
    )


def call_arguments(stated: Any) -> Any:
    """One call's arguments as the object they mean, whichever of the two forms they arrived in."""
    if not isinstance(stated, str):
        return stated
    try:
        return json.loads(stated)
    except json.JSONDecodeError:
        return stated


def a_turn(turn: Mapping[str, Any]) -> Part:
    """One message as one part: what was said, and what was called, in the order it happened."""
    if ROLE not in turn:
        raise ConfigError(
            f"a text2text turn declares no {ROLE!r}; this one holds {sorted(turn)}"
        )
    calls = turn.get(TOOL_CALLS)
    written = [spoken_text(turn.get(CONTENT)), stated_calls(calls) if calls else None]
    return Part(
        type="text",
        role=str(turn[ROLE]),
        text=SPOKEN_AND_STATED.join(piece for piece in written if piece),
    )
