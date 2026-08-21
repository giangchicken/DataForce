"""STEP · stages 7-8 · what a person is asked, and what they answer with.

Stage 7 writes the question, stage 8 puts it in front of an annotator with the
control that captures the answer. One module because the two halves have to agree:
a question about `{hold_missing}` is unanswerable unless the clause is on screen.

Nothing here may carry anything a model produced -- that is stage 8's gate, and it
is why the catalog is rendered from the record's own `tools` rather than passed in.

An answer is a set of **calls**, so capturing one is a form rather than a multi-select:
requirement 75. Two controls can express it and which one ships is *declared*, not
detected, because it changes what an annotator could physically say and therefore what
their agreement means.

**Reading an answer back is not here, and the reason is a dependency boundary.**
Requirement 75 pairs the `JSON_TEXT` fallback with validation at pull time against
requirement 71's schema, which needs a JSON Schema validator applied to a value already
in hand. `agent-toolkit` owns schema validation and exposes only
`complete_structured`, which makes an LLM request; `jsonschema` is in
`test_no_reimplementation.py`'s `NOT_OURS`, so no module here may import it directly.
The core spec's § *Out of Scope* settles which way that resolves -- a gap is fixed by a
release there, not patched locally -- and the entry is filed. Until then the fallback
control exists and nothing accepts its output.
"""

from __future__ import annotations

import html

from agent_toolkit.string_utils import slot_filling

from dataforce.core.errors import ConfigError
from dataforce.core.record import Record, UIControl
from dataforce.profiles.tool_decision.schema import Tool
from dataforce.profiles.tool_decision.source_contract import TOOLS_KEY, SourceContract
from dataforce.profiles.tool_decision.utils import (
    catalog_names,
    openai_to_tools,
    record_catalog,
    tools_to_catalog,
)

__all__ = [
    "CONTROLS",
    "JSON_TEXT",
    "PER_NAME_ARGUMENTS",
    "answer_config",
    "question_text",
    "readable_catalog",
]

# The two ways an annotation tool can be asked to capture a set of calls.
#
# `PER_NAME_ARGUMENTS` is the one to want: a name control plus, per name, the argument
# fields generated from that tool's own `parameters`, shown only when that name is
# picked. An annotator cannot then state an argument for a tool they did not call.
#
# `JSON_TEXT` is the declared fallback for a tool that cannot express per-name
# conditional fields. It can express *any* answer, including ones outside the space,
# which is why requirement 75 pairs it with validation at pull time rather than treating
# it as equivalent.
#
# Which one ships is a per-project fact and is recorded as one, because an annotator who
# had to hand-write JSON and an annotator who filled in a form were not asked the same
# question, and their agreement does not mean the same thing.
PER_NAME_ARGUMENTS = "per_name_arguments"
JSON_TEXT = "json_text"
CONTROLS = (PER_NAME_ARGUMENTS, JSON_TEXT)


def _attribute(value: str) -> str:
    """One tool name, safe in an XML attribute and readable back unchanged.

    Tabs and newlines become character references because an XML parser normalises
    literal ones to spaces in an attribute value -- and one name in this corpus contains
    a literal tab, which would otherwise come back from the annotation UI as a name no
    catalog contains.
    """
    escaped = html.escape(value, quote=True)
    return escaped.replace("\t", "&#9;").replace("\n", "&#10;").replace("\r", "&#13;")


def question_text(template: str, focus: str) -> str:
    """One focused question. Choosing the focus is `generate_questions`'s job.

    Handed the template rather than the `prompt_version` that names it: reading
    `config/prompts` is `declared/`'s job, and `slot_filling` only fills doubled
    braces, so the marker DSL's single ones pass through untouched.
    """
    return slot_filling(template, {"focus": focus})


def readable_catalog(record: Record) -> str:
    """The record's catalog as a person reads it, or empty if its turns already hold it.

    An annotator answering a question about `{hold_missing}` has to be able to read
    the clause. Under the legacy shape the catalog is rendered into the instruction
    turn and the modality already displays it; under the canonical shape the tools are
    data, and this is what turns them back into something legible.
    """
    declared = record.meta.get(TOOLS_KEY)
    if not declared:
        return ""
    return tools_to_catalog(openai_to_tools(declared).tools)


def _argument_fields(tool: Tool) -> str:
    """One tool's arguments as controls, shown only when that tool is picked.

    `visibleWhen` is what makes this a form rather than a wall: an annotator sees the
    arguments of the tools they chose and no others, so they cannot state a value for a
    tool they did not call. A declared `enum` becomes a closed choice, so an argument
    the tool constrains cannot be typed freely; everything else is text, because a
    JSON Schema can say things -- nested objects, arrays of objects -- that no
    single control expresses, and pretending otherwise is what pull-time validation
    would then have to catch.
    """
    lines = []
    required = set(tool.required)
    for name, spec in tool.properties.items():
        spec = spec or {}
        label = f"{name}{'*' if name in required else ''}"
        common = (
            f'perRegion="false" visibleWhen="choice-selected" '
            f'whenTagName="tools" whenChoiceValue="{_attribute(tool.name)}"'
        )
        field = f"{_attribute(tool.name)}.{_attribute(name)}"
        values = spec.get("enum")
        if values:
            options = "".join(
                f'<Choice value="{_attribute(str(value))}"/>' for value in values
            )
            lines.append(
                f'  <Choices name="{field}" toName="content" choice="single" '
                f"{common}>{options}</Choices>"
            )
        else:
            lines.append(
                f'  <TextArea name="{field}" toName="content" rows="1" '
                f'editable="true" maxSubmissions="1" placeholder="{_attribute(label)}" '
                f"{common}/>"
            )
    return "\n".join(lines)


def answer_config(
    record: Record, contract: SourceContract, *, control: str = PER_NAME_ARGUMENTS
) -> UIControl:
    """The capture half of the config, constrained to this record's catalog.

    Requirement 75. `control` is declared by the profile manifest rather than detected,
    because which one shipped changes what an annotator could physically express. It is
    a keyword with a default so the choice is visible at every call site that makes one.
    """
    if control not in CONTROLS:
        raise ConfigError(
            f"{control!r} is not an answer control; there are two: {list(CONTROLS)}"
        )
    readable = readable_catalog(record)
    shown = (
        f'<HyperText name="catalog" clickableLinks="false">'
        f"<pre>{html.escape(readable)}</pre></HyperText>\n"
        if readable
        else ""
    )
    if control == JSON_TEXT:
        # One control, any answer. What keeps it inside the space is `read_answer`,
        # which is why requirement 75 refuses to accept this path unvalidated.
        return UIControl(
            f'{shown}<TextArea name="calls" toName="content" rows="4" '
            f'editable="true" maxSubmissions="1" '
            f'placeholder="[{{&quot;name&quot;: &quot;…&quot;, '
            f'&quot;arguments&quot;: {{}}}}]"/>'
        )

    catalog = record_catalog(record, contract)
    choices = "\n".join(
        f'  <Choice value="{_attribute(name)}"/>'
        for name in catalog_names(record, contract)
    )
    arguments = "\n".join(
        fields
        for fields in (_argument_fields(tool) for tool in catalog.tools)
        if fields
    )
    return UIControl(
        f'{shown}<Choices name="tools" toName="content" choice="multiple" '
        f'showInline="false">\n{choices}\n</Choices>'
        + (f"\n{arguments}" if arguments else "")
    )
