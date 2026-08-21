"""The `tool_decision` profile: tool selection over Vietnamese call-centre text.

Composes with the `text` modality. The answer is a set of **calls** drawn from the
record's own catalog -- a call being a tool name and the arguments it is called with --
and the empty set, 35.4% of the reference source, is a first-class answer rather than a
missing one.

The object below is the index to the rest, and the rest is the flow. Every member
delegates to the module named for the phase that asks for it -- `data_quality` (stages
0-4), `ai_review` (5-6), `human_review` (7-11), `release` (12-14) -- over two modules
that belong to no phase: `schema` (every shape: a source contract, a tool, a catalog,
an answer) and `utils` (every conversion and computation over them, including the
distance between two answers, which two phases need). So the answer to *what does stage
8 ask of this profile* is a filename. `measure_corpus` is a tool rather than a step and
is imported by the CLI, not from here.

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

from dataforce.core.errors import ConfigError
from dataforce.core.manifest import Manifest
from dataforce.core.record import Part, Record, UIControl
from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision import (
    ai_review,
    data_quality,
    human_review,
    release,
    schema,
)
from dataforce.profiles.tool_decision.data_quality import PROVENANCE_KEY
from dataforce.profiles.tool_decision.utils import (
    answer_distance,
    read_source_contract,
    record_catalog,
)

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
        if self.answer_control not in human_review.CONTROLS:
            raise ConfigError(
                f"{declared.name}: answer_control {self.answer_control!r} is not one "
                f"of {list(human_review.CONTROLS)}"
            )

    def build_record(self, raw: Any, parts: list[Part]) -> Record:
        return data_quality.build_record(raw, parts, self.contract)

    def answer_distance(self, a: Answer, b: Answer) -> float:
        return answer_distance(a, b)

    def vote_consensus(self, votes: list[Answer], record: Record) -> Answer | None:
        return ai_review.vote_consensus(votes, record_catalog(record, self.contract))

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return data_quality.validity_checks(
            self.contract, answer_ceiling=self.answer_ceiling
        )

    def question_text(self, record: Record, focus: str) -> str:
        return human_review.question_text(self.question_template, focus)

    def annotator_catalog_text(self, record: Record) -> str:
        return human_review.annotator_catalog_text(record)

    def answer_config(self, record: Record) -> UIControl:
        return human_review.answer_config(
            record, self.contract, control=self.answer_control
        )

    def answer_space(self, record: Record) -> dict[str, Any]:
        """This record's answer space, built now and stored nowhere.

        Requirement 71. Not a member of the `Profile` protocol yet: the two callers it
        is for -- the jury's `complete_structured` request and pull-time validation of
        a human correction -- are Phases 4 and 5, and the protocol gains a member when
        something generic needs to call one, not before.
        """
        return schema.answer_space(record_catalog(record, self.contract))

    def scenario_hash(self, record: Record) -> str:
        return release.scenario_hash(record, self.contract)

    def training_example(self, record: Record) -> dict[str, Any]:
        return release.training_example(record)
