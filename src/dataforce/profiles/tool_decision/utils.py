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
from dataclasses import dataclass
from typing import Any

from agent_toolkit.string_utils import compute_hash

from dataforce.core.errors import ConfigError
from dataforce.core.manifest import Manifest
from dataforce.core.record import Part, Record, TextPart
from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision.schema import (
    LEGACY_SYSTEM_PROMPT,
    SHAPES,
    TARGET,
    TOOLS_KEY,
    Catalog,
    SourceContract,
    Tool,
)

__all__ = [
    "CATALOG_HEADER",
    "INSTRUCTION",
    "Gap",
    "answer_distance",
    "build_system_prompt",
    "calls_by_name",
    "catalog_hash",
    "catalog_names",
    "catalog_to_tools",
    "openai_to_tools",
    "read_catalog",
    "read_source_contract",
    "record_catalog",
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


def openai_to_tools(entries: Iterable[Mapping[str, Any]]) -> Catalog:
    """The catalog a source states as data. The inverse of `to_strict_openai`.

    One of the two ways a source carries its catalog; `catalog_to_tools` is the other,
    and reading a rendered one is the expensive path. Named to match that pair, so the
    two directions of each conversion sit under names that differ only in order.
    """
    return Catalog(
        tools=tuple(
            Tool(
                name=entry["function"]["name"],
                description=entry["function"].get("description", ""),
                parameters=entry["function"].get("parameters", {}),
            )
            for entry in entries
        )
    )


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


# `Gap` is here and not in `schema.py`, against the rule that a shape belongs in a
# schema module. It is not a shape this profile's *data* has: no record carries one, no
# stage sees one, and this module is both its only producer and its only consumer. The
# rule that wins is the one about consumers -- a definition with one consumer is that
# consumer's code. AGENTS.md §8, and the module-layout spec's requirement 10.
@dataclass(frozen=True)
class Gap:
    """Something the text implies that the schema could not be given.

    The parser's own account of what it could not recover. A format reader that returns
    less than it was given and says nothing is the failure `utils.py` is arranged
    against.
    """

    tool: str
    parameter: str | None
    kind: str
    evidence: str


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


def read_catalog(
    tools: Iterable[Mapping[str, Any]] | None,
    parts: Sequence[Part],
    contract: SourceContract,
) -> Catalog:
    """One record's catalog, from wherever its shape keeps it.

    Under the canonical shape the tools are data and nothing is parsed. Under the
    legacy shape they were rendered into the instruction turn, so they are read back
    out of it -- and this is the **only** caller of `catalog_to_tools` in the system,
    asserted by test, which is what keeps a 93 µs parse from quietly becoming one per
    stage.

    Takes the tools rather than the raw item so that stage 0 can pass `raw["tools"]`
    and every later caller `record.meta["tools"]`, from one branch in one place.
    """
    if contract.shape != LEGACY_SYSTEM_PROMPT:
        return openai_to_tools(tools or ())
    instruction = contract.role_name("instruction")
    rendered = next(
        (
            part.text
            for part in parts
            if isinstance(part, TextPart) and part.role == instruction
        ),
        "",
    )
    return catalog_to_tools(rendered)


def record_catalog(record: Record, contract: SourceContract) -> Catalog:
    """The catalog a built record offers, from wherever its shape keeps it.

    `read_catalog` takes the pieces because stage 0 has a raw item and no record yet;
    every caller after stage 0 has one, and this is that call.
    """
    return read_catalog(record.meta.get(TOOLS_KEY), record.content, contract)


def catalog_names(record: Record, contract: SourceContract) -> list[str]:
    """The names a record's own catalog offers, in the order it offers them.

    Derived from the record's content, never read off a stored copy: requirement 71,
    and the measurement that reversed the first draft of it -- 0.27 µs against 0.07,
    which is 0.0 seconds across a 21,172-record run, against a second thing that can
    disagree with the first.
    """
    return list(record_catalog(record, contract).names)


def catalog_hash(names: Sequence[str]) -> str:
    """The hash of one catalog: what makes two records the same scenario here.

    Named for what it hashes, because that is the only thing a reader needs to know to
    say whether two records should get the same value. Order-sensitive, because the
    catalog is presented in order and two orderings are two prompts. `source_index` is
    not this: it is unique per record, measured, and so gives no leakage protection.
    """
    return compute_hash("|".join(names), "sha256")[:_HASH_LENGTH]


# --- one source's own vocabulary ---------------------------------------------


def _declared(manifest: Manifest, key: str, inner: str) -> Any:
    """One value out of a mapping the manifest declares, or an error naming both keys."""
    block = manifest.require(key)
    if not isinstance(block, Mapping) or inner not in block:
        raise ConfigError(
            f"{manifest.name}: {key}.{inner} is not declared; {key} holds "
            f"{sorted(block) if isinstance(block, Mapping) else block!r}"
        )
    return block[inner]


def read_source_contract(manifest: Manifest) -> SourceContract:
    """One source's contract, from its manifest. Every missing key names itself."""
    shape = manifest.require("shape")
    if shape not in SHAPES:
        raise ConfigError(
            f"{manifest.name}: shape {shape!r} is not one of {list(SHAPES)}"
        )
    gold = manifest.declared.get("gold") or {}
    contract = SourceContract(
        name=manifest.name,
        shape=shape,
        roles=manifest.require("roles"),
        label_key=_declared(manifest, "label", "at"),
        meta=manifest.require("meta"),
        gold_from=gold.get("from", ""),
    )
    # so an undeclared target role fails here rather than once per record
    if not contract.restating_role:
        raise ConfigError(f"{manifest.name}: roles.{TARGET} is declared empty")
    return contract


# --- an answer, read and compared --------------------------------------------
#
# Both phases that measure disagreement compute this: the jury's cohesion and the
# triage buckets at stages 5-6, and Krippendorff's alpha at stage 10. So it is here
# rather than in `ai_review.py`, which `human_review.py` would then have to import.


def calls_by_name(answer: Answer) -> dict[str, dict[str, Any]]:
    """The calls an answer means, keyed by tool name, the first spelling of a name winning.

    A bare string entry is the call with no arguments. That is what makes a names-only
    source a special case of this answer type rather than a second one, and requirement
    72's reduction -- δ equals Jaccard over names when arguments agree -- is asserted on
    exactly it.

    A bare *answer* is rejected rather than iterated: `set("SendMail")` is a set of
    characters, and a δ that accepted it would silently compare spellings.

    A repeated name collapses here. Requirement 73 declares the multiset out and
    `label_names_one_tool_twice` finds one by comparing this length against the
    answer's, so nothing downstream has to decide which of two calls to one tool won.
    """
    if isinstance(answer, str) or not isinstance(answer, Iterable):
        raise TypeError(f"an answer is an array of calls, not {type(answer).__name__}")
    calls: dict[str, dict[str, Any]] = {}
    for entry in answer:
        if isinstance(entry, str):
            calls.setdefault(entry, {})
            continue
        if not isinstance(entry, Mapping) or not isinstance(entry.get("name"), str):
            raise TypeError(f"a call is a name and its arguments, not {entry!r}")
        arguments = entry.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"the arguments of {entry['name']!r} are an object, not {arguments!r}"
            )
        calls.setdefault(entry["name"], dict(arguments))
    return calls


def _argument_agreement(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    """How far two calls to one tool agree: the share of keys present in both and equal.

    Over the *union* of keys, so a key present in only one is a disagreement. That is
    why it is not `len(shared) / len(left)`, which would call a one-argument call a
    perfect match for the same call carrying five. Two calls with no arguments agree
    perfectly, which is what makes a names-only answer reduce exactly. Both are
    requirement 72.
    """
    keys = left.keys() | right.keys()
    if not keys:
        return 1.0
    agreed = sum(
        1 for key in keys if key in left and key in right and left[key] == right[key]
    )
    return agreed / len(keys)


def answer_distance(a: Answer, b: Answer) -> float:
    """Name-first: a different tool disagrees fully, a differing argument only partly.

    Requirement 72. Over the union of names in the two answers, a name in both
    contributes how far its arguments agree and a name in only one contributes zero;
    δ is one minus the mean of those contributions. So naming a different tool is full
    disagreement and naming the same tool with one differing argument is *partial*,
    which is the whole point: the two failures are not equally wrong and a jury that
    scored them the same would rank them the same.

    `answer_distance(∅, ∅) = 0` is returned before the division, and it is load-bearing:
    35.4% of the reference source is the empty answer, so a `0/0` would make the
    population carrying the real difficulty look like the one with least agreement.

    When every matched call has identical arguments this **is** Jaccard over names --
    two argument-less calls agree perfectly, so each matched name contributes exactly 1
    -- so a names-only profile is the special case rather than a different formula, and
    every measurement taken before arguments existed still describes it.

    The mean over the union of names is a *choice*, recorded as one in requirement 72:
    it weights every named tool equally, so a record whose answer is one call and a
    record whose answer is four are scored on the same scale. Changing it is a threshold
    decision with its own task.
    """
    left, right = calls_by_name(a), calls_by_name(b)
    names = left.keys() | right.keys()
    if not names:
        return 0.0
    agreement = sum(
        _argument_agreement(left[name], right[name])
        for name in names
        if name in left and name in right
    )
    return 1.0 - agreement / len(names)
