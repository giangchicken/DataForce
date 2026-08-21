"""The `tool_decision` profile: tool selection over Vietnamese call-centre text.

Composes with the `text` modality. The answer is a set of tool names drawn from the
record's own catalog, and the empty set -- 35.4% of this corpus -- is a first-class
answer rather than a missing one.

The object below is the index to the rest. Every member delegates to the module that
does the work, so the four definitions -- `tool_schema` (a tool), `schema` (what an
answer looks like), `answer` (what is computed from one), `source_contract` (what this
corpus calls things) -- and the two steps --
`build_record` (stages 0-1) and `ask_annotator` (stages 7-8) -- can each be read on
their own. `measure_corpus` is a tool rather than a step and is imported by the CLI,
not from here.

Identity, the modality it composes with, the prompt it asks and the source's shape and
vocabulary are all in `config/profiles/tool_decision.yaml`, because each of those is
stamped into an artifact or decides how a file is read, and neither is something a
class attribute should be able to change without review. Reading that file, and the
question template it names, is the composition root's job: importing this module opens
nothing, so it works from any working directory.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision import answer, ask_annotator, build_record, schema
from dataforce.profiles.tool_decision.build_record import PROVENANCE_KEY
from dataforce.profiles.tool_decision.source_contract import read_source_contract
from dataforce.shared.manifest import Manifest
from dataforce.shared.record import Part, Record, UIControl

__all__ = ["MANIFEST_NAME", "PROVENANCE_KEY", "ToolDecisionProfile"]

MANIFEST_NAME = "tool_decision"


class ToolDecisionProfile:
    """Tool selection over Vietnamese call-centre text, composed with `text`."""

    def __init__(
        self, declared: Manifest, *, question_template: str, ceiling: int
    ) -> None:
        self.manifest = declared
        self.name = declared.name
        self.version = declared.version
        self.modality: str = declared.require("modality")
        # The version names the file and is stamped into `questions.jsonl`; the
        # template is its text, read by whoever built this object. Both are kept:
        # an artifact records which prompt asked a question, and rendering it here
        # is what keeps `config/prompts` out of the engine.
        self.question_prompt: str = declared.require("prompts")["question"]
        self.question_template = question_template
        # The largest answer this source is declared to contain, from `params.yaml`.
        # Held rather than read per record, and read before this object exists, so an
        # undeclared ceiling fails earlier than the first of 21,172 rows.
        self.ceiling = ceiling
        self.contract = read_source_contract(declared)
        self.answer_schema = schema.ANSWER_SCHEMA

    def build_record(self, raw: Any, parts: list[Part]) -> Record:
        return build_record.build_record(raw, parts, self.contract)

    def answer_distance(self, a: Answer, b: Answer) -> float:
        return answer.answer_distance(a, b)

    def vote_consensus(self, votes: list[Answer]) -> Answer | None:
        return answer.vote_consensus(votes)

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return build_record.validity_checks(self.contract, ceiling=self.ceiling)

    def question_text(self, record: Record, focus: str) -> str:
        return ask_annotator.question_text(self.question_template, focus)

    def readable_catalog(self, record: Record) -> str:
        return ask_annotator.readable_catalog(record)

    def answer_config(self, record: Record) -> UIControl:
        return ask_annotator.answer_config(record)

    def group_key(self, record: Record) -> str:
        return build_record.group_key(record)

    def training_example(self, record: Record) -> dict[str, Any]:
        return answer.training_example(record)
