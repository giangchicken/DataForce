"""The profile object: nine members, assembled from the modules around it."""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision import adapter, answers, checks

# By its module path, not through the package: `__init__` re-exports the function
# under the same name as its module, and `export` here would be the function.
from dataforce.profiles.tool_decision.export import export as export_example
from dataforce.shared import manifest, prompts
from dataforce.shared.record import Part, Record, UIControl

__all__ = ["MANIFEST_NAME", "TOOL_DECISION", "ToolDecisionProfile"]

# The manifest this profile is: `config/profiles/tool_decision.yaml`. Its name, version,
# the modality it composes with and the `prompt_version` it asks with are all declared
# there, because every one of them is stamped into an artifact.
MANIFEST_NAME = "tool_decision"


def _attribute(value: str) -> str:
    """One tool name, safe to put in an XML attribute and read back unchanged.

    Tabs and newlines are emitted as character references because an XML parser
    normalises literal ones to spaces in an attribute value -- and one name in this
    corpus contains a literal tab, which would otherwise come back from the
    annotation UI as a name no catalog contains.
    """
    escaped = html.escape(value, quote=True)
    return escaped.replace("\t", "&#9;").replace("\n", "&#10;").replace("\r", "&#13;")


class ToolDecisionProfile:
    """Tool selection over Vietnamese call-centre text, composed with `text`.

    Behaviour is here; identity is in the manifest. Nothing in this class names its own
    version, so bumping one is a reviewed line in a declared file rather than an edit
    that silently changes what `producer.profile` claims about every record produced.
    """

    def __init__(self, declared: manifest.Manifest) -> None:
        self.manifest = declared
        self.name = declared.name
        self.version = declared.version
        self.modality: str = declared.require("modality")
        self.question_prompt: str = declared.require("prompts")["question"]
        self.answer_schema = answers.ANSWER_SCHEMA

    def adapt(self, raw: Any, parts: list[Part]) -> Record:
        return adapter.adapt(raw, parts)

    def delta(self, a: Answer, b: Answer) -> float:
        return answers.delta(a, b)

    def consensus(self, votes: list[Answer]) -> Answer | None:
        return answers.consensus(votes)

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return checks.validity_checks()

    def question(self, record: Record, focus: str) -> str:
        """One focused question. Choosing the focus is `generate_questions`'s job."""
        return prompts.render(self.question_prompt, {"focus": focus})

    def answer_control(self, record: Record) -> UIControl:
        """The capture half of the config, constrained to this record's catalog."""
        choices = "\n".join(
            f'  <Choice value="{_attribute(name)}"/>'
            for name in adapter.catalog_names(record)
        )
        return UIControl(
            '<Choices name="tools" toName="content" choice="multiple" '
            f'showInline="false">\n{choices}\n</Choices>'
        )

    def group_key(self, record: Record) -> str:
        """The catalog fingerprint. Never `source_index`, which is unique per record."""
        return adapter.catalog_fingerprint(adapter.catalog_names(record))

    def export(self, record: Record) -> dict[str, Any]:
        return export_example(record)


TOOL_DECISION = ToolDecisionProfile(manifest.load("profiles", MANIFEST_NAME))
