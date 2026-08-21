"""Fixtures every test directory shares: where the repo is, and stand-in contracts.

The fakes here are shape-complete rather than clever: every member does the least it
can honestly do, because what the tests using them assert is that they satisfy the
protocol and resolve by name. `SetProfile`'s Jaccard distance and strict-majority
consensus are real but nothing calls either now -- they were what the deleted
conformance suite exercised.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from dataforce.api import text_modality, tool_decision_profile
from dataforce.core.record import (
    Part,
    Producer,
    Record,
    Source,
    Span,
    TextPart,
    UIControl,
    compute_rid,
)
from dataforce.profiles.base import Answer

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPO_ROOT / "src" / "dataforce"
CONFIG = REPO_ROOT / "config"
PARAMS = REPO_ROOT / "params.yaml"
CORE_SPEC = REPO_ROOT / "docs" / "annotation-pipeline" / "spec.md"

# Both axes, built once from the repository's own committed policy, through the same
# composition root every caller uses. Neither is constructed at import time by the
# library itself, so this is where a test gets one -- as a module constant rather than
# a fixture, because the helpers that build records are module-level too.
TEXT = text_modality(config_root=CONFIG)
TOOL_DECISION = tool_decision_profile(config_root=CONFIG, params=PARAMS)

TOOLS = ["Calendar", "SendMail", "Search"]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def source_files() -> list[Path]:
    """Every module under src/dataforce, so a guard test cannot miss one."""
    files = sorted(SOURCE_ROOT.rglob("*.py"))
    assert files, "no source modules found -- the guard tests would pass vacuously"
    return files


_STAGE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([a-z_]+)\s*\|\s*`(\w+)`\s*\|")


def stage_table(spec: Path = CORE_SPEC) -> tuple[tuple[int, str, str], ...]:
    """The core spec's stage table: one `(number, phase, stage)` row per stage.

    The document is the source for both the phase names and the stage names, so the
    guards that check code against it all parse the table here rather than each
    carrying its own regex for one document.
    """
    rows = tuple(
        (int(found.group(1)), found.group(2), found.group(3))
        for line in spec.read_text(encoding="utf-8").splitlines()
        if (found := _STAGE_ROW.match(line))
    )
    # If the table moves and the parse silently reads nothing, every caller would
    # pass vacuously. Two claims that hold however the table is edited.
    assert rows, f"no stage row parsed out of {spec}"
    numbers = [number for number, _, _ in rows]
    assert len(set(numbers)) == len(numbers), f"a stage number is repeated: {numbers}"
    return rows


def parsed_sources(
    source_root: Path = SOURCE_ROOT,
) -> Iterator[tuple[Path, ast.Module]]:
    """Every module under one source tree, parsed. Any tree, so a guard written here
    can be run against an older checkout of it and shown to fail."""
    for path in sorted(source_root.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def docstring_ids(tree: ast.Module) -> set[int]:
    """Which string constants in one module are documentation.

    Prose that mentions a placeholder, or names where `config/` is, is prose. Two
    guards need this distinction, so it is here rather than in either of them.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


class FakeTextModality:
    """Four members, doing the least each one can honestly do."""

    name = "fake_text"
    version = "1"

    def content_parts(self, raw: Any) -> list[Part]:
        return [TextPart(role="user", text=str(raw))]

    def embedding(self, parts: list[Part]) -> Sequence[float]:
        return [float(len(parts))]

    def personal_data_detectors(self) -> list[Callable[[list[Part]], list[Span]]]:
        return []

    def display_config(self, record: Record) -> UIControl:
        return UIControl(f"<Text name='content' value='${record.rid}'/>")


class SetProfile:
    """A set-valued answer: Jaccard distance, strict-majority consensus.

    `answer_distance` returns 0 for two empty answers rather than dividing 0 by 0, which is
    the case that matters -- for the first real profile a third of the corpus is
    the empty set.
    """

    name = "fake_tools"
    version = "1"
    modality = "fake_text"
    answer_schema: dict[str, Any] = {
        "type": "array",
        "items": {"enum": TOOLS},
        "uniqueItems": True,
    }

    def build_record(self, raw: Any, parts: list[Part]) -> Record:
        return Record(
            rid=compute_rid(parts),
            source=Source(
                file_sha256="abc", offset=0, ingested_at="2026-08-18T00:00:00Z"
            ),
            producer=Producer(modality="fake_text@1", profile="fake_tools@1"),
            content=parts,
            label=list(raw.get("tools", [])),
            meta=dict(raw),
        )

    def answer_distance(self, a: Answer, b: Answer) -> float:
        left, right = set(a), set(b)
        union = left | right
        if not union:
            return 0.0
        return 1.0 - len(left & right) / len(union)

    def vote_consensus(self, votes: list[Answer], record: Record) -> Answer | None:
        if not votes:
            return None
        threshold = len(votes) / 2
        counts = {tool: sum(tool in vote for vote in votes) for tool in TOOLS}
        return sorted(tool for tool, count in counts.items() if count > threshold)

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return {"answer_in_space": lambda r: set(r.label) <= set(TOOLS)}

    def question_text(self, record: Record, focus: str) -> str:
        return f"Is {focus} right for record {record.rid}?"

    def answer_config(self, record: Record) -> UIControl:
        return UIControl("<Choices name='answer' toName='content'/>")

    def scenario_hash(self, record: Record) -> str:
        return f"g_{record.rid[:8]}"

    def training_example(self, record: Record) -> dict[str, Any]:
        return {
            "content": [part.model_dump() for part in record.content],
            "tools": record.label,
        }


class FreeTextProfile:
    """The honest exception: no defensible consensus over generated strings."""

    name = "fake_free_text"
    version = "1"
    modality = "fake_text"
    answer_schema: dict[str, Any] = {"type": "string"}

    def build_record(self, raw: Any, parts: list[Part]) -> Record:
        return Record(
            rid=compute_rid(parts),
            source=Source(
                file_sha256="abc", offset=0, ingested_at="2026-08-18T00:00:00Z"
            ),
            producer=Producer(modality="fake_text@1", profile="fake_free_text@1"),
            content=parts,
            label=str(raw.get("answer", "")),
            meta=dict(raw),
        )

    def answer_distance(self, a: Answer, b: Answer) -> float:
        return 0.0 if a == b else 1.0

    def vote_consensus(self, votes: list[Answer], record: Record) -> Answer | None:
        return None

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return {}

    def question_text(self, record: Record, focus: str) -> str:
        return f"Is this answer right for {record.rid}?"

    def answer_config(self, record: Record) -> UIControl:
        return UIControl("<TextArea name='answer' toName='content'/>")

    def scenario_hash(self, record: Record) -> str:
        return record.rid

    def training_example(self, record: Record) -> dict[str, Any]:
        return {"answer": record.label}


@pytest.fixture
def modality() -> FakeTextModality:
    return FakeTextModality()


@pytest.fixture
def profile() -> SetProfile:
    return SetProfile()


@pytest.fixture
def parts() -> list[Part]:
    return [
        TextPart(role="system", text="You are a router."),
        TextPart(role="user", text="hi"),
    ]
