"""The `tool_decision` profile: tool selection over Vietnamese call-centre text.

Composes with the `text` modality. The answer is a set of **calls** drawn from the
record's own catalog -- a call being a tool name and the arguments it is called with --
and the empty set, 35.4% of the reference source, is a first-class answer rather than a
missing one.

The object below is the index to the rest. Every member delegates to the module that
does the work, so the three definitions -- `schema` (every shape: a tool, a
catalog, an answer), `source_contract` (what this corpus calls things) and `answer`
(what is computed from an answer) -- the conversions in `utils` -- and the two steps
--
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
from dataforce.profiles.tool_decision.utils import record_catalog
from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest
from dataforce.shared.record import Part, Record, UIControl

__all__ = ["MANIFEST_NAME", "PROVENANCE_KEY", "ToolDecisionProfile"]

MANIFEST_NAME = "tool_decision"


class ToolDecisionProfile:
    """Tool selection over Vietnamese call-centre text, composed with `text`."""

    def __init__(
        self, declared: Manifest, *, question_template: str, answer_ceiling: int
    ) -> None:
        self.manifest = declared
        self.name = declared.name
        self.version = declared.version
        self.modality: str = declared.require("modality")
        self.question_prompt: str = declared.require("prompts")["question"]
        self.question_template = question_template
        self.answer_ceiling = answer_ceiling
        self.contract = read_source_contract(declared)
        self.answer_schema = schema.ANSWER_SCHEMA
        # Required, not defaulted: a silently-defaulted capture control is exactly what
        # requirement 75 forbids, because the two are not equivalent surfaces.
        self.answer_control: str = declared.require("answer_control")
        if self.answer_control not in ask_annotator.CONTROLS:
            raise ConfigError(
                f"{declared.name}: answer_control {self.answer_control!r} is not one "
                f"of {list(ask_annotator.CONTROLS)}"
            )

    def build_record(self, raw: Any, parts: list[Part]) -> Record:
        return build_record.build_record(raw, parts, self.contract)

    def answer_distance(self, a: Answer, b: Answer) -> float:
        return answer.answer_distance(a, b)

    def vote_consensus(self, votes: list[Answer], record: Record) -> Answer | None:
        return answer.vote_consensus(votes, record_catalog(record, self.contract))

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return build_record.validity_checks(
            self.contract, answer_ceiling=self.answer_ceiling
        )

    def question_text(self, record: Record, focus: str) -> str:
        return ask_annotator.question_text(self.question_template, focus)

    def readable_catalog(self, record: Record) -> str:
        return ask_annotator.readable_catalog(record)

    def answer_config(self, record: Record) -> UIControl:
        return ask_annotator.answer_config(
            record, self.contract, control=self.answer_control
        )

    def answer_schema_for(self, record: Record) -> dict[str, Any]:
        """This record's answer space, built now and stored nowhere.

        Requirement 71. Not a member of the `Profile` protocol yet: the two callers it
        is for -- the jury's `complete_structured` request and pull-time validation of
        a human correction -- are Phases 4 and 5, and the protocol gains a member when
        something generic needs to call one, not before.
        """
        return schema.answer_schema_for(record_catalog(record, self.contract))

    def scenario_hash(self, record: Record) -> str:
        return build_record.scenario_hash(record, self.contract)

    def training_example(self, record: Record) -> dict[str, Any]:
        return answer.training_example(record)
