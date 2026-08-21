"""LOGIC · every conversion of a tool and a catalog. Both directions, defined once.

The shapes are `schema.py`; what is computed over them is here. The catalog text is a
*rendering* of the tools -- what a person reads, in the system prompt of a legacy
record and on the annotator's screen -- and this module is the only place that knows
how the two correspond.

Both directions live here on purpose. The strings below are the format: putting them in
a config file while a parser also needed them would be two sources of truth for one
grammar, and the way to know a grammar is self-consistent is to render and read with
one definition and assert the round trip. Which is what
`tests/unit/test_catalog_format.py` does, over the real corpus: 21,172 catalogs, read
then re-rendered, byte-identical.

Ported from the corpus generator's `openai_to_catalog.py` and `catalog_to_openai.py`,
which own the same contract on the producing side, and carrying their names --
`tools_to_catalog`, `catalog_to_tools`, `build_system_prompt`, `to_strict_openai` -- so
the two codebases can be diffed one conversion at a time.

The description is never split. `Mục đích:` / `Khi nào gọi:` / `Khi nào KHÔNG gọi:` are
text *inside* it, not structure around it, so the marker DSL survives because nothing
takes it apart -- not because a parser remembered to be careful.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from agent_toolkit.string_utils import compute_hash

from dataforce.profiles.tool_decision.schema import Catalog, Gap, Tool
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import Record

__all__ = [
    "CATALOG_HEADER",
    "INSTRUCTION",
    "build_system_prompt",
    "catalog_hash",
    "catalog_names",
    "catalog_to_tools",
    "to_strict_openai",
    "tools_to_catalog",
]

# The instruction the source puts above the catalog. Not part of the catalog: under the
# canonical record shape this is the whole system message and the tools are data.
INSTRUCTION = (
    "Based on the available tools and conversation history, determine which tool(s) "
    "the assistant should call next.\n"
    "Return a JSON array of tool names.\n"
    "The array may contain zero, one, or multiple tool names.\n"
    "Return an empty array if no tool should be called."
)
CATALOG_HEADER = "TOOLS:"

_REQUIRE = "require:"
_PARAMS = "params:"
_ENUM_CLAUSE = "Giá trị khả dụng:"
_DEFAULT_CLAUSE = "Nếu khách không đề cập, mặc định là"
_FIELDS_CLAUSE = "Gồm các trường:"
_INDENT = "  "

# A name on a line of its own. Permissive by measurement: 7,114 of the corpus's 105,880
# entries are named with a dot, a hyphen, a space or a literal tab, every one of them a
# real entry with a real body, and a stricter pattern reports 841 empty catalogs and 722
# out-of-catalog labels that are facts about the pattern rather than about the corpus.
_NAME = re.compile(r"(?m)^\[([^\]\n]+)\]$")

# One parameter line. The leading indent is captured because depth is what tells a
# top-level parameter from an object's subfield.
_PARAM = re.compile(r"^(\s{2,})([^\s(*]+)(\*)?\s*\(([a-zA-Z]+)\):\s*(.*)$")

# Captured greedily up to the '.' that *ends* the clause, so a dotted enum value like
# `phiGiaoDich.ngoaiTe` stays whole. The trailing '.' is optional: legacy catalogs end
# the clause at the newline.
_ENUM = re.compile(
    rf"\s*{_ENUM_CLAUSE}\s*(.+?)\.?(?=\s*$|\s+{_DEFAULT_CLAUSE.split(',')[0]})"
)
# The clause ends at a '.' not followed by a digit, so a decimal default survives.
_DEFAULT = re.compile(rf"\s*{_DEFAULT_CLAUSE}\s*([^\n]+?)\.(?!\d)")
_DEFAULT_PROSE = re.compile(r"mặc định (?:là\s+)?([^\n.]+?)\s*(?:\.|$)")
_FIELDS = re.compile(rf"\s*{_FIELDS_CLAUSE}\s*([^\n]+?)\.")

# Prose saying a datum should exist where no structured key was recovered. Reported as a
# gap rather than guessed at: a parser that infers `required` from wording is a parser
# that quietly disagrees with the schema.
_REQUIRED_IN_PROSE = (
    "thông tin bắt buộc",
    "bắt buộc phải có",
    "là bắt buộc",
    "buộc phải cung cấp",
)
_ENUM_IN_PROSE = (
    "chỉ chấp nhận",
    "phải là một trong",
    "một trong các giá trị",
    "chỉ nhận giá trị",
)


def to_strict_openai(tool: Tool) -> dict[str, Any]:
    """The strict OpenAI shape: standard keys only."""
    function: dict[str, Any] = {"name": tool.name}
    if tool.description:
        function["description"] = tool.description
    if tool.parameters:
        function["parameters"] = tool.parameters
    return {"type": "function", "function": function}


# --- rendering: tools -> the text a person reads ------------------------------


def _default_text(value: Any) -> str:
    if isinstance(value, bool):
        return "có" if value else "không"
    if isinstance(value, list):
        return "[]" if not value else ", ".join(map(str, value))
    return str(value)


def _effective_required(parameters: Mapping[str, Any]) -> set[str]:
    """Declared required, minus anything carrying a default -- the default wins.

    A parameter that is both required and defaulted is a contradiction in the schema,
    and resolving it silently the other way would mark a name required in the text while
    the schema says it can be omitted.
    """
    properties = parameters.get("properties") or {}
    return {
        name
        for name in (parameters.get("required") or [])
        if "default" not in (properties.get(name) or {})
    }


def _is_rich(spec: Mapping[str, Any]) -> bool:
    """Whether an object's subfields carry more than the inline form can hold."""
    for sub in (spec.get("properties") or {}).values():
        sub = sub or {}
        if (sub.get("description") or "").strip():
            return True
        if sub.get("type", "string") != "string":
            return True
        if sub.get("enum") or "default" in sub or (sub.get("items") or {}).get("enum"):
            return True
    return False


def _parameter_lines(
    name: str, spec: Mapping[str, Any], required: set[str], depth: int = 1
) -> list[str]:
    spec = spec or {}
    declared = spec.get("type", "string")
    description = (spec.get("description") or "").strip()
    subfields = spec.get("properties") or {}
    rich = declared == "object" and bool(subfields) and _is_rich(spec)

    if declared == "object" and subfields and not rich:
        sub_required = set(spec.get("required") or [])
        inline = ", ".join(
            f"{key}{'*' if key in sub_required else ''}" for key in subfields
        )
        description = f"{description} {_FIELDS_CLAUSE} {inline}.".strip()

    star = "*" if name in required else ""
    line = f"{_INDENT * depth}{name}{star} ({declared}): {description}".rstrip()

    values = (
        (spec.get("items") or {}).get("enum")
        if declared == "array"
        else spec.get("enum")
    )
    if values:
        line += f" {_ENUM_CLAUSE} {', '.join(map(str, values))}."
    if "default" in spec:
        line += f" {_DEFAULT_CLAUSE} {_default_text(spec['default'])}."

    lines = [line]
    if rich:
        deeper = _effective_required(spec)
        for key, sub in subfields.items():
            lines.extend(_parameter_lines(key, sub, deeper, depth + 1))
    return lines


def tools_to_catalog(tools: Iterable[Tool]) -> str:
    """The catalog as a person reads it. One block per tool, blank line between."""
    return "\n\n".join(_render_tool(tool) for tool in tools)


def _render_tool(tool: Tool) -> str:
    required = _effective_required(tool.parameters)
    block = [f"[{tool.name}]"]
    if tool.description:
        block.append(tool.description)
    lines = [
        line
        for name, spec in tool.properties.items()
        for line in _parameter_lines(name, spec, required)
    ]
    if lines:
        # In property-definition order, not sorted: a corpus catalog has to come back
        # byte-identical.
        ordered = [name for name in tool.properties if name in required]
        block.append(f"{_REQUIRE} {', '.join(ordered)}")
        block.append(_PARAMS)
        block.extend(lines)
    return "\n".join(block)


def build_system_prompt(tools: Iterable[Tool]) -> str:
    """The legacy system message: the instruction, then the catalog under its header."""
    return f"{INSTRUCTION}\n\n{CATALOG_HEADER}\n{tools_to_catalog(tools)}"


# --- parsing: the text a person reads -> tools --------------------------------


def _coerce(text: str, declared: str) -> Any:
    text = text.strip()
    if declared == "boolean":
        return text.lower() in ("có", "true")
    if declared in ("integer", "number"):
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        if re.fullmatch(r"-?\d+\.\d+", text):
            return float(text)
    if declared == "array" and text in ("[]", ""):
        return []
    return text


def _spec_from(declared: str, rest: str) -> tuple[dict[str, Any], bool, str | None]:
    """A parameter spec from the text after `name (type):`."""
    spec: dict[str, Any] = {"type": declared}

    found_enum = _ENUM.search(rest)
    values = (
        [v.strip() for v in found_enum.group(1).split(",") if v.strip()]
        if found_enum
        else None
    )
    found_default = _DEFAULT.search(rest)
    prose_default = None
    if not found_default:
        loose = _DEFAULT_PROSE.search(rest)
        prose_default = loose.group(1) if loose else None

    found_fields = _FIELDS.search(rest)
    if found_fields:  # the compact inline object: subfield names and requiredness only
        subfields: dict[str, Any] = {}
        sub_required: list[str] = []
        for entry in found_fields.group(1).split(","):
            entry = entry.strip()
            name = entry.rstrip("*").strip()
            if not name:
                continue
            subfields[name] = {"type": "string"}
            if entry.endswith("*"):
                sub_required.append(name)
        spec = {"type": "object", "properties": subfields, "required": sub_required}

    description = _FIELDS.sub("", _DEFAULT.sub("", _ENUM.sub("", rest))).strip()
    if description:
        spec["description"] = description
    if values:
        if spec["type"] == "array":
            spec["items"] = {"type": "string", "enum": values}
        else:
            spec["enum"] = values
    if found_default:
        spec["default"] = _coerce(found_default.group(1), declared)
    elif prose_default is not None:
        spec["default"] = _coerce(prose_default, declared)
    return spec, bool(found_default), prose_default


def _parse_tool(name: str, body: str, gaps: list[Gap] | None) -> Tool:
    lines = body.split("\n")
    require_at = next(
        (i for i, line in enumerate(lines) if line.lower().startswith(_REQUIRE)), None
    )
    params_at = next(
        (i for i, line in enumerate(lines) if line.strip() == _PARAMS), None
    )
    description_ends = min(
        x for x in (require_at, params_at, len(lines)) if x is not None
    )

    # Everything between the name and require:/params:, verbatim -- structured clauses
    # and freeform prose alike. One string, so a re-render echoes it back unchanged.
    description = "\n".join(lines[:description_ends]).strip()

    named_required: list[str] = []
    if require_at is not None:
        named_required = [
            part.strip()
            for part in lines[require_at].split(":", 1)[1].split(",")
            if part.strip()
        ]

    properties: dict[str, Any] = {}
    starred: list[str] = []
    rest_of: dict[str, str] = {}
    if params_at is not None:
        top_indent: int | None = None
        current_object: dict[str, Any] | None = None
        for line in lines[params_at + 1 :]:
            matched = _PARAM.match(line)
            if matched is None:
                continue
            indent, parameter, star, declared, rest = matched.groups()
            if top_indent is None:
                top_indent = len(indent)
            spec, had_default, prose_default = _spec_from(declared, rest)

            if len(indent) > top_indent and current_object is not None:
                current_object.setdefault("properties", {})[parameter] = spec
                if star and "default" not in spec:
                    current_object.setdefault("required", []).append(parameter)
                continue

            rest_of[parameter] = rest
            properties[parameter] = spec
            if star:
                starred.append(parameter)
            current_object = spec if spec.get("type") == "object" else None

            if prose_default is not None and not had_default:
                _note(gaps, name, parameter, "prose_default", rest)
            if (
                "enum" not in spec
                and declared != "array"
                and _says(rest, _ENUM_IN_PROSE)
            ):
                _note(gaps, name, parameter, "enum_stated_in_prose", rest)

        for parameter, spec in properties.items():
            if spec.get("type") == "object" and not spec.get("properties"):
                _note(
                    gaps,
                    name,
                    parameter,
                    "object_without_subfields",
                    rest_of[parameter],
                )

    required = [
        parameter
        for parameter in (starred or named_required)
        if "default" not in properties.get(parameter, {})
    ]
    if properties and not required:
        _note(gaps, name, None, "nothing_required", "")
    for parameter, rest in rest_of.items():
        if parameter not in required and _says(rest, _REQUIRED_IN_PROSE):
            _note(gaps, name, parameter, "required_stated_in_prose", rest)

    return Tool(
        name=name,
        description=description,
        parameters={"type": "object", "properties": properties, "required": required},
    )


def _says(text: str, signals: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in signals)


def _note(
    gaps: list[Gap] | None, tool: str, parameter: str | None, kind: str, evidence: str
) -> None:
    if gaps is not None:
        gaps.append(
            Gap(tool=tool, parameter=parameter, kind=kind, evidence=evidence.strip())
        )


def catalog_to_tools(text: str, *, gaps: list[Gap] | None = None) -> Catalog:
    """The catalog a rendered text offers, with or without the instruction above it.

    Text with no catalog header, and text whose header is followed by no entry, both
    give an empty catalog rather than an exception: whether that is a genuinely toolless
    prompt or a reader that missed something is not the reader's to decide, and
    `empty_catalog` is a quarantine for triage rather than a verdict.
    """
    header = f"{CATALOG_HEADER}\n"
    body = text.split(header, 1)[1] if header in text else text
    found = list(_NAME.finditer(body))
    bounds = [*(match.end() for match in found), len(body)]
    return Catalog(
        tools=tuple(
            _parse_tool(
                match.group(1).strip(), body[bounds[i] : found[i + 1].start()], gaps
            )
            if i + 1 < len(found)
            else _parse_tool(match.group(1).strip(), body[bounds[i] : len(body)], gaps)
            for i, match in enumerate(found)
        )
    )


# A catalog hash, in hex characters. Long enough that two different catalogs colliding
# is not a thing that happens at corpus scale.
_HASH_LENGTH = 16


def catalog_names(record: Record) -> list[str]:
    """The catalog a record was built with, read back off its answer space."""
    if record.answer_space is None:
        raise ConfigError(
            f"record {record.rid} carries no answer space; "
            "it was not built by the tool_decision profile"
        )
    names: list[str] = record.answer_space["items"]["enum"]
    return names


def catalog_hash(names: Sequence[str]) -> str:
    """The hash of one catalog: what makes two records the same scenario here.

    Named for what it hashes, because that is the only thing a reader needs to know to
    say whether two records should get the same value. Order-sensitive, because the
    catalog is presented in order and two orderings are two prompts. `source_index` is
    not this: it is unique per record, measured, and so gives no leakage protection.
    """
    return compute_hash("|".join(names), "sha256")[:_HASH_LENGTH]
