"""logic · what a task hands a model: one sample, as the text a model reads.

The two renderings live here for the same reason: two definitions of what a turn is,
or of what a tool looks like, would let a juror and a reviewer disagree about the text they were
shown, and nothing would say so. `conversation_turns` is the turns; the catalog is the rest of the
file below it, and `text_to_openai_tool_format` at the end reads the other way -- text a model
wrote, back into the format -- so that what a call *is* is also defined once.

    [tool_name]
    <description, verbatim>
    require: <required param names, in property order>
    params:
      <p>[*] (<type>): <desc>.[ Giá trị khả dụng: a, b.][ Nếu khách không đề cập, mặc định là v.]

Two rules the schema does not state on its own. A required param that also declares a `default` is a
contradiction: the default wins, so it is optional, unmarked and out of `require:`. An object param
lists its subfields inline while they are plain strings, and puts them on their own deeper lines as
soon as one carries a type, a description, an enum or a default -- the inline form cannot hold those.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from agent_toolkit.string_utils import extract_json_from_text

SPACES_PER_LEVEL = 2


def conversation_turns(sample: Mapping[str, Any]) -> tuple[str, ...]:
    """The conversation as the flat turns every part reads, `role: content` per message."""
    return tuple(
        f"{turn.get('role', '')}: {turn.get('content', '')}"
        for turn in sample.get("messages") or ()
    )


def default_values_line(value: Any) -> str:
    """One default as a reviewer reads it: a boolean stays `true`/`false`, an empty list `[]`."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else "[]"
    return str(value)


def subfields_lines(spec: Mapping[str, Any]) -> bool:
    """True where a subfield carries what `Gồm các trường` cannot hold.

    That inline form holds names and a `*`, nothing else, so a type other than string -- a nested
    object included -- a description, an enum or a default each put the subfields on their own lines.
    """
    for field in (spec.get("properties") or {}).values():
        field = field or {}
        if field.get("type", "string") != "string" or "default" in field:
            return True
        if (field.get("description") or "").strip() or field.get("enum"):
            return True
        if (field.get("items") or {}).get("enum"):
            return True
    return False


def param_lines(
    name: str,
    spec: Mapping[str, Any],
    required: set[str],
    indent: int = SPACES_PER_LEVEL,
) -> list[str]:
    """One param as its line, and its subfields as deeper lines where they need their own."""
    typed = spec.get("type", "string")
    described = (spec.get("description") or "").strip()
    fields = spec.get("properties") or {}
    is_object = typed == "object" and bool(fields)
    deeper = is_object and subfields_lines(spec)

    if is_object and not deeper:
        sub = set(spec.get("required") or [])
        named = ", ".join(f"{f}{'*' if f in sub else ''}" for f in fields)
        described = f"{described} Gồm các trường: {named}.".strip()

    line = f"{' ' * indent}{name}{'*' if name in required else ''} ({typed}): {described}".rstrip()
    # An array carries its enum under `items`; every other type carries its own.
    values = (
        (spec.get("items") or {}).get("enum") if typed == "array" else spec.get("enum")
    )
    if values:
        line += f" Giá trị khả dụng: {', '.join(map(str, values))}."
    if "default" in spec:
        line += f" Nếu khách không đề cập, mặc định là {default_values_line(spec['default'])}."

    lines = [line]
    if deeper:
        sub_required = {
            f
            for f in spec.get("required") or []
            if "default" not in (fields.get(f) or {})
        }
        for field, field_spec in fields.items():
            lines += param_lines(
                field, field_spec or {}, sub_required, indent + SPACES_PER_LEVEL
            )
    return lines


def tool_block(function: Mapping[str, Any]) -> str:
    """One tool written out: its name, its description verbatim, and its params."""
    parameters = function.get("parameters") or {}
    properties = parameters.get("properties") or {}
    required = {
        name
        for name in parameters.get("required") or []
        if "default" not in (properties.get(name) or {})
    }
    block = [f"[{function['name']}]"]
    described = (function.get("description") or "").strip()
    if described:
        block.append(described)
    if properties:
        # In property order, not sorted, so text re-rendered from these tools is identical.
        block.append("require: " + ", ".join(n for n in properties if n in required))
        block.append("params:")
        for name, spec in properties.items():
            block += param_lines(name, spec or {}, required)
    return "\n".join(block)


def openai_tool_format_to_text(tools: Sequence[Any]) -> str:
    """Every tool written out, one block each, blank line between them.

    An entry is `{"type": "function", "function": {...}}` or the function on its own. One without a
    name is left out -- an unreadable tool is one entry, not a reason to render none of them.
    """
    blocks = []
    for entry in tools:
        if not isinstance(entry, Mapping):
            continue
        function = entry.get("function") if "function" in entry else entry
        if isinstance(function, Mapping) and isinstance(function.get("name"), str):
            blocks.append(tool_block(function))
    return "\n\n".join(blocks)


def text_to_openai_tool_format(text: str) -> tuple[dict[str, Any], ...]:
    """The calls in what a model wrote, as OpenAI tool-call entries. `()` where it wrote none.

    The other direction of `openai_tool_format_to_text`, and lenient in the same way: an entry may
    be `{"type": "function", "function": {...}}` or the call on its own, and one without a name is
    left out rather than costing the rest. `extract_json_from_text`, so an array with prose around
    it is still those calls.

    Each entry carries the call and nothing else: an `id` a provider hung on it is not part of what
    was called. The arguments come back as the JSON text the format writes them as, under one key
    ordering -- so a corpus writing the object and a provider writing the text wrote one call, and
    two orderings of the same arguments are one string. Text that will not parse stays as it is; it
    is what the model said, and nothing here reads it better than that.
    """
    read = extract_json_from_text(text)
    calls: list[dict[str, Any]] = []
    for one in read if isinstance(read, list) else [read]:
        if not isinstance(one, Mapping):
            continue
        function = one.get("function") if "function" in one else one
        if not isinstance(function, Mapping) or not isinstance(
            function.get("name"), str
        ):
            continue
        # Read the text a provider writes, then write every call's arguments back as that text:
        # the parse is what makes one key ordering possible, and the ordering is what makes two
        # spellings of one call one string.
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            as_object = extract_json_from_text(arguments)
            arguments = arguments if as_object is None else as_object
        if not isinstance(arguments, str):
            arguments = json.dumps(
                arguments or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        calls.append(
            {
                "type": "function",
                "function": {"name": function["name"], "arguments": arguments},
            }
        )
    return tuple(calls)
