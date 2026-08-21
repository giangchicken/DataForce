"""STEP · stages 7-8 · what a person is asked, and what they answer with.

Stage 7 writes the question, stage 8 puts it in front of an annotator with the
control that captures the answer. One module because the two halves have to agree:
a question about `{hold_missing}` is unanswerable unless the clause is on screen.

Nothing here may carry anything a model produced -- that is stage 8's gate, and it
is why the catalog is rendered from the record's own `tools` rather than passed in.
"""

from __future__ import annotations

import html

from agent_toolkit.string_utils import slot_filling

from dataforce.profiles.tool_decision.schema import Tool
from dataforce.profiles.tool_decision.source_contract import TOOLS_KEY
from dataforce.profiles.tool_decision.utils import catalog_names, tools_to_catalog
from dataforce.shared.record import Record, UIControl

__all__ = ["answer_config", "question_text", "readable_catalog"]


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
    return tools_to_catalog(
        Tool(
            name=entry["function"]["name"],
            description=entry["function"].get("description", ""),
            parameters=entry["function"].get("parameters", {}),
        )
        for entry in declared
    )


def answer_config(record: Record) -> UIControl:
    """The capture half of the config, constrained to this record's catalog."""
    readable = readable_catalog(record)
    shown = (
        f'<HyperText name="catalog" clickableLinks="false">'
        f"<pre>{html.escape(readable)}</pre></HyperText>\n"
        if readable
        else ""
    )
    choices = "\n".join(
        f'  <Choice value="{_attribute(name)}"/>' for name in catalog_names(record)
    )
    return UIControl(
        f'{shown}<Choices name="tools" toName="content" choice="multiple" '
        f'showInline="false">\n{choices}\n</Choices>'
    )
