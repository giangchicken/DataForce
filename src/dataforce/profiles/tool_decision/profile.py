"""The profile object: nine members, assembled from the modules around it.

Behaviour is here. Identity, the modality it composes with, the prompt it asks and the
source's shape and vocabulary are all in `config/profiles/tool_decision.yaml`, because
each of those is stamped into an artifact or decides how a file is read, and neither is
something a class attribute should be able to change without review.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision import adapter, answers, checks, export
from dataforce.profiles.tool_decision import catalog as catalog_format
from dataforce.profiles.tool_decision.source import TOOLS_KEY, read_source_contract
from dataforce.shared import manifest, prompts
from dataforce.shared.record import Part, Record, UIControl

__all__ = ["MANIFEST_NAME", "TOOL_DECISION", "ToolDecisionProfile"]

MANIFEST_NAME = "tool_decision"


def _attribute(value: str) -> str:
    """One tool name, safe in an XML attribute and readable back unchanged.

    Tabs and newlines become character references because an XML parser normalises
    literal ones to spaces in an attribute value -- and one name in this corpus contains
    a literal tab, which would otherwise come back from the annotation UI as a name no
    catalog contains.
    """
    escaped = html.escape(value, quote=True)
    return escaped.replace("\t", "&#9;").replace("\n", "&#10;").replace("\r", "&#13;")


class ToolDecisionProfile:
    """Tool selection over Vietnamese call-centre text, composed with `text`."""

    def __init__(self, declared: manifest.Manifest) -> None:
        self.manifest = declared
        self.name = declared.name
        self.version = declared.version
        self.modality: str = declared.require("modality")
        self.question_prompt: str = declared.require("prompts")["question"]
        self.contract = read_source_contract(declared)
        self.answer_schema = answers.ANSWER_SCHEMA

    def build_record(self, raw: Any, parts: list[Part]) -> Record:
        return adapter.build_record(raw, parts, self.contract)

    def answer_distance(self, a: Answer, b: Answer) -> float:
        return answers.answer_distance(a, b)

    def vote_consensus(self, votes: list[Answer]) -> Answer | None:
        return answers.vote_consensus(votes)

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return checks.validity_checks(self.contract)

    def question_text(self, record: Record, focus: str) -> str:
        """One focused question. Choosing the focus is `generate_questions`'s job."""
        return prompts.render(self.question_prompt, {"focus": focus})

    def readable_catalog(self, record: Record) -> str:
        """The record's catalog as a person reads it, or empty if its turns already hold it.

        An annotator answering a question about `{hold_missing}` has to be able to read
        the clause. Under the legacy shape the catalog is rendered into the instruction
        turn and the modality already displays it; under the canonical shape the tools are
        data, and this is what turns them back into something legible.
        """
        declared = record.meta.get(TOOLS_KEY)
        if not declared:
            return ""
        return catalog_format.tools_to_catalog(
            catalog_format.Tool(
                name=entry["function"]["name"],
                description=entry["function"].get("description", ""),
                parameters=entry["function"].get("parameters", {}),
            )
            for entry in declared
        )

    def answer_config(self, record: Record) -> UIControl:
        """The capture half of the config, constrained to this record's catalog."""
        readable = self.readable_catalog(record)
        shown = (
            f'<HyperText name="catalog" clickableLinks="false">'
            f"<pre>{html.escape(readable)}</pre></HyperText>\n"
            if readable
            else ""
        )
        choices = "\n".join(
            f'  <Choice value="{_attribute(name)}"/>'
            for name in adapter.catalog_names(record)
        )
        return UIControl(
            f'{shown}<Choices name="tools" toName="content" choice="multiple" '
            f'showInline="false">\n{choices}\n</Choices>'
        )

    def group_key(self, record: Record) -> str:
        """The catalog fingerprint. Never `source_index`, which is unique per record."""
        return adapter.catalog_fingerprint(adapter.catalog_names(record))

    def training_example(self, record: Record) -> dict[str, Any]:
        return export.training_example(record)


TOOL_DECISION = ToolDecisionProfile(manifest.load("profiles", MANIFEST_NAME))
