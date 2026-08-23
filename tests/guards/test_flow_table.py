"""I3 · code's phase and stage names are the flow's, and the spec's.

The flow table is stated twice on purpose -- once as prose a person reads, once as
``pipeline/flow.py`` the code reads -- and P31 says a fact stated in both places is compared by a
test rather than trusted. Changing either side alone fails here, and the failure names which row
and which side moved.

Three things are compared: the whole row -- number, phase, stage *and* summary -- the module each
in-scope stage is supposed to live in, and that module's ``STEP ·`` docstring (Requirement 3).
Markup is normalised away before the summaries are compared -- the spec writes single backticks and
a docstring writes double -- but the words are not.

Deriving a stage's module path is this test's business and nothing else's yet. It moves into
``pipeline/runner.py`` when the runner needs to dispatch over the table for real.
"""

import ast
import re
from pathlib import Path

import pytest

from dataforce.pipeline.flow import LAST_IN_SCOPE_STAGE, PHASES, STAGES

from .tree import SRC, module_at

SPEC = Path(__file__).resolve().parents[2] / "docs" / "annotation-pipeline" / "spec.md"

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*`(\w+)`\s*\|\s*(.+?)\s*\|$")
SCOPE = re.compile(r"\*\*Stages (\d+)[–-](\d+) are in scope\.\*\*")


def spec_rows() -> list[tuple[int, str, str, str]]:
    """The § *The flow* table, as the document states it: number, phase, stage, summary."""
    rows = [
        (int(m[1]), m[2], m[3], m[4])
        for line in SPEC.read_text(encoding="utf-8").splitlines()
        if (m := ROW.match(line))
    ]
    assert rows, (
        f"no flow table found in {SPEC.name}; the parser and the document disagree"
    )
    return rows


def plain(text: str) -> str:
    """One summary with its markup and its trailing stop removed, so two mediums compare."""
    return re.sub(r"\s+", " ", text.replace("`", "")).strip().rstrip(".")


def module_path(number: int, phase: str, stage: str) -> Path:
    """Where that stage's module belongs: a phase with one stage is a module, several is a
    directory (spec.md § *Package layout*)."""
    siblings = [row for row in spec_rows() if row[1] == phase]
    tail = f"{stage}.py" if len(siblings) == 1 else f"{phase}/{stage}.py"
    return SRC / "pipeline" / tail


def test_the_table_has_the_rows_the_document_promises() -> None:
    """Fifteen rows, numbered 0-14 without a gap. Guards the parser, not the code."""
    rows = spec_rows()

    assert [row[0] for row in rows] == list(range(15))


def test_the_code_and_the_document_declare_the_same_rows() -> None:
    """I3: a row nobody implemented, a row renamed on one side, or a summary reworded on one.

    The summary is compared too. A field of the table that nothing checks is the fiction P31 is
    about -- and it would be the fourth place this flow is written down."""
    document = [
        (number, phase, stage, plain(summary))
        for number, phase, stage, summary in spec_rows()
    ]
    code = [(s.number, s.phase, s.stage, plain(s.summary)) for s in STAGES]

    assert code == document, "left is pipeline/flow.py, right is spec.md § *The flow*"


def test_the_phases_are_the_table_s_phases_in_the_table_s_order() -> None:
    """A phase is not declared anywhere else: it is the distinct phases of the flow, in order."""
    document = list(dict.fromkeys(phase for _, phase, _, _ in spec_rows()))

    assert list(PHASES) == document


def test_the_in_scope_boundary_is_the_one_the_document_states() -> None:
    """`release` is declared in the flow and built later; both sides say where the line is."""
    stated = SCOPE.search(SPEC.read_text(encoding="utf-8"))

    assert stated, "spec.md no longer says which stages are in scope"
    assert (int(stated[1]), int(stated[2])) == (0, LAST_IN_SCOPE_STAGE)


@pytest.mark.parametrize(
    "row", [r for r in spec_rows() if r[0] <= 11], ids=lambda r: r[2]
)
def test_each_in_scope_stage_has_the_module_the_layout_puts_it_in(
    row: tuple[int, str, str, str],
) -> None:
    """I3, code -> spec: a stage renamed in the document and not in the tree, or the reverse."""
    number, phase, stage, _ = row
    path = module_path(number, phase, stage)

    assert path.exists(), (
        f"stage {number} `{stage}` has no module at {path.relative_to(SRC)}"
    )


@pytest.mark.parametrize(
    "row", [r for r in spec_rows() if r[0] <= 11], ids=lambda r: r[2]
)
def test_each_stage_module_s_docstring_names_its_stage_and_its_number(
    row: tuple[int, str, str, str],
) -> None:
    """Requirement 3: `STEP · <stage> (stage <n>) · <what the table says it does>`."""
    number, phase, stage, summary = row
    docstring = ast.get_docstring(module_at(module_path(number, phase, stage)).tree)

    assert docstring, f"stage {number} `{stage}` has no docstring"
    assert plain(docstring.splitlines()[0]) == plain(
        f"STEP · {stage} (stage {number}) · {summary}"
    )
