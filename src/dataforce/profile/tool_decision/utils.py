"""LOGIC · every tool a conversation was offered, written out as the text a reviewer reads.

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

from collections.abc import Mapping, Sequence
from typing import Any

SPACES_PER_LEVEL = 2


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
