"""The profile object: nine members, assembled from the modules around it."""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from agent_toolkit.string_utils import slot_filling

from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision import adapter, answers, checks

# By its module path, not through the package: `__init__` re-exports the function
# under the same name as its module, and `export` here would be the function.
from dataforce.profiles.tool_decision.export import export as export_example
from dataforce.shared.record import Part, Record, UIControl

__all__ = ["TOOL_DECISION", "ToolDecisionProfile"]

# Filled with `slot_filling`, whose `{{placeholder}}` syntax leaves the marker DSL's
# single braces alone. `str.format` would raise on the first `{trigger}` it met.
_QUESTION = (
    "Dựa trên danh mục tool và hội thoại, những tool nào cần được gọi? "
    "Có thể là tập rỗng nếu không tool nào nên được gọi.\n"
    "Tập trung vào: {{focus}}"
)


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
    """Tool selection over Vietnamese call-centre text, composed with `text`."""

    name = "tool_decision"
    version = "1"
    modality = "text"
    answer_schema = answers.ANSWER_SCHEMA

    def adapt(self, raw: Any, parts: list[Part]) -> Record:
        return adapter.adapt(raw, parts)

    def delta(self, a: Answer, b: Answer) -> float:
        return answers.delta(a, b)

    def consensus(self, votes: list[Answer]) -> Answer | None:
        return answers.consensus(votes)

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return checks.validity_checks()

    def question(self, record: Record, focus: str) -> str:
        """One focused question. The template library is `generate_questions`'s."""
        return slot_filling(_QUESTION, {"focus": focus})

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


TOOL_DECISION = ToolDecisionProfile()
