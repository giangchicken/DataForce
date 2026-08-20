"""Fixtures every test directory shares: where the repo is, and stand-in contracts.

The fakes here are shape-complete rather than clever: every member does the least it
can honestly do, because what the tests using them assert is that they satisfy the
protocol and resolve by name. `SetProfile`'s Jaccard distance and strict-majority
consensus are real but nothing calls either now -- they were what the deleted
conformance suite exercised.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from dataforce.modalities import registry as modality_registry
from dataforce.profiles import registry as profile_registry
from dataforce.profiles.base import Answer
from dataforce.shared.record import (
    Part,
    Producer,
    Record,
    Source,
    Span,
    TextPart,
    UIControl,
    compute_rid,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPO_ROOT / "src" / "dataforce"

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


def parsed_sources() -> Iterator[tuple[Path, ast.Module]]:
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.fixture(autouse=True)
def _isolated_registries() -> Iterator[None]:
    """Registration is process-global; a test that registers must not leak."""
    modalities = dict(modality_registry._REGISTRY)
    profiles = dict(profile_registry._REGISTRY)
    yield
    modality_registry._REGISTRY.clear()
    modality_registry._REGISTRY.update(modalities)
    profile_registry._REGISTRY.clear()
    profile_registry._REGISTRY.update(profiles)


class FakeTextModality:
    """Four members, doing the least each one can honestly do."""

    name = "fake_text"
    version = "1"

    def load(self, raw: Any) -> list[Part]:
        return [TextPart(role="user", text=str(raw))]

    def embed(self, parts: list[Part]) -> Sequence[float]:
        return [float(len(parts))]

    def privacy_detectors(self) -> list[Callable[[list[Part]], list[Span]]]:
        return []

    def display_control(self, record: Record) -> UIControl:
        return UIControl(f"<Text name='content' value='${record.rid}'/>")


class SetProfile:
    """A set-valued answer: Jaccard distance, strict-majority consensus.

    `delta` returns 0 for two empty answers rather than dividing 0 by 0, which is
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

    def adapt(self, raw: Any, parts: list[Part]) -> Record:
        return Record(
            rid=compute_rid(parts),
            source=Source(
                file_sha256="abc", offset=0, ingested_at="2026-08-18T00:00:00Z"
            ),
            producer=Producer(modality="fake_text@1", profile="fake_tools@1"),
            content=parts,
            label=list(raw.get("tools", [])),
            answer_space={"tools": TOOLS},
            meta=dict(raw),
        )

    def delta(self, a: Answer, b: Answer) -> float:
        left, right = set(a), set(b)
        union = left | right
        if not union:
            return 0.0
        return 1.0 - len(left & right) / len(union)

    def consensus(self, answers: list[Answer]) -> Answer | None:
        if not answers:
            return None
        threshold = len(answers) / 2
        counts = {tool: sum(tool in answer for answer in answers) for tool in TOOLS}
        return sorted(tool for tool, count in counts.items() if count > threshold)

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return {"answer_in_space": lambda r: set(r.label) <= set(TOOLS)}

    def question(self, record: Record, focus: str) -> str:
        return f"Is {focus} right for record {record.rid}?"

    def answer_control(self, record: Record) -> UIControl:
        return UIControl("<Choices name='answer' toName='content'/>")

    def group_key(self, record: Record) -> str:
        return f"g_{record.rid[:8]}"

    def export(self, record: Record) -> dict[str, Any]:
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

    def adapt(self, raw: Any, parts: list[Part]) -> Record:
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

    def delta(self, a: Answer, b: Answer) -> float:
        return 0.0 if a == b else 1.0

    def consensus(self, answers: list[Answer]) -> Answer | None:
        return None

    def validity_checks(self) -> dict[str, Callable[[Record], bool]]:
        return {}

    def question(self, record: Record, focus: str) -> str:
        return f"Is this answer right for {record.rid}?"

    def answer_control(self, record: Record) -> UIControl:
        return UIControl("<TextArea name='answer' toName='content'/>")

    def group_key(self, record: Record) -> str:
        return record.rid

    def export(self, record: Record) -> dict[str, Any]:
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
