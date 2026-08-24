"""I3 · code's phase and stage names are the flow's, and the spec's.

The flow table is stated twice on purpose -- once as prose a person reads, once as
``pipeline/flow.py`` the code reads -- and P31 says a fact stated in both places is compared by a
test rather than trusted. Changing either side alone fails here, and the failure names which row
and which side moved.

Four things are compared: the whole row -- phase, stage *and* summary, in the table's order -- the
phases that are declared and not built, the module each built stage is supposed to live in, and
that module's ``STEP ·`` docstring (Requirement 3).

**Order is position, and nothing else states it.** Neither side numbers a stage, so the comparison
is list-against-list rather than key-against-key: a row moved up is a row that fails here
(Decision 19).

Deriving a stage's module path was this test's business until the runner needed it. It now reads
``stage_module_name`` out of ``pipeline/runner.py``, which is what makes the two file assertions
below a check on the runner: every stage the document declares is where ``run_phase`` will go
looking for it.
"""

import ast
import re
from pathlib import Path

import pytest

from dataforce.pipeline.flow import DECLARED_ONLY, PHASES, STAGES
from dataforce.pipeline.runner import stage_module_name

from .tree import SPEC, SRC, module_at, plain

ROW = re.compile(r"^\|\s*(\w+)\s*\|\s*`(\w+)`\s*\|\s*(.+?)\s*\|$")
DECLARED = re.compile(r"\*\*Declared, not built:\s*(?P<names>[^*]+?)\.\*\*")
BACKTICKED = re.compile(r"`(\w+)`")

Row = tuple[str, str, str]


def flow_section() -> str:
    """§ *The flow*, on its own. Other tables in this document also have a stage column."""
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("### The flow")
    return text[start : text.index("\n### ", start + 1)]


def spec_rows() -> list[Row]:
    """The § *The flow* table, as the document states it: phase, stage, summary, in order."""
    rows = [
        (m[1], m[2], m[3])
        for line in flow_section().splitlines()
        if (m := ROW.match(line))
    ]
    assert rows, (
        f"no flow table found in {SPEC.name}; the parser and the document disagree"
    )
    return rows


def spec_declared_only() -> list[str]:
    """The phases the document says are in the flow and have no module."""
    stated = DECLARED.search(flow_section())

    assert stated, f"{SPEC.name} § *The flow* no longer says which phases are unbuilt"
    return BACKTICKED.findall(stated["names"])


def built_rows() -> list[Row]:
    """Every row whose stage the document says has a module."""
    unbuilt = spec_declared_only()
    return [row for row in spec_rows() if row[0] not in unbuilt]


def module_path(phase: str, stage: str) -> Path:
    """The file the runner will import for that row of the table."""
    dotted = stage_module_name(phase, stage)
    return SRC.parent / Path(*dotted.split(".")).with_suffix(".py")


def test_the_table_names_every_stage_once() -> None:
    """Guards the parser, not the code: a row this regex silently skipped is a row nothing checks."""
    rows = spec_rows()

    assert len(rows) > 1
    assert len({stage for _, stage, _ in rows}) == len(rows)


def test_the_code_and_the_document_declare_the_same_rows() -> None:
    """I3: a row nobody implemented, a row renamed on one side, a reordering, or a reworded summary.

    The summary is compared too. A field of the table that nothing checks is the fiction P31 is
    about -- and it would be the fourth place this flow is written down."""
    document = [(phase, stage, plain(summary)) for phase, stage, summary in spec_rows()]
    code = [(s.phase, s.stage, plain(s.summary)) for s in STAGES]

    assert code == document, "left is pipeline/flow.py, right is spec.md § *The flow*"


def test_the_phases_are_the_table_s_phases_in_the_table_s_order() -> None:
    """A phase is not declared anywhere else: it is the distinct phases of the flow, in order."""
    document = list(dict.fromkeys(phase for phase, _, _ in spec_rows()))

    assert list(PHASES) == document


def test_the_unbuilt_phases_are_the_ones_the_document_names() -> None:
    """`release` is in the flow and has no module; both sides name it, rather than cut at a number."""
    assert list(DECLARED_ONLY) == spec_declared_only()


def test_every_unbuilt_phase_is_a_phase() -> None:
    """A phase named unbuilt that is not in the flow at all would exclude nothing, silently."""
    assert set(DECLARED_ONLY) <= set(PHASES)


@pytest.mark.parametrize("row", built_rows(), ids=lambda r: r[1])
def test_each_built_stage_has_the_module_the_layout_puts_it_in(row: Row) -> None:
    """I3, code -> spec: a stage renamed in the document and not in the tree, or the reverse."""
    phase, stage, _ = row
    path = module_path(phase, stage)

    assert path.exists(), f"`{stage}` has no module at {path.relative_to(SRC)}"


@pytest.mark.parametrize("row", built_rows(), ids=lambda r: r[1])
def test_each_stage_module_s_docstring_is_its_row_of_the_table(row: Row) -> None:
    """Requirement 3: `STEP · <stage> · <what the table says it does>`."""
    phase, stage, summary = row
    docstring = ast.get_docstring(module_at(module_path(phase, stage)).tree)

    assert docstring, f"`{stage}` has no docstring"
    assert plain(docstring.splitlines()[0]) == plain(f"STEP · {stage} · {summary}")
