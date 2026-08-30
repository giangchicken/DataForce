"""I3 · code's phase and stage names are the flow's, and the spec's.

The flow table is stated twice on purpose -- once as prose a person reads, once as
``pipeline/flow.py`` the code reads -- and a fact stated in both places is compared by a
test rather than trusted. Changing either side alone fails here, and the failure names which row
and which side moved.

Five things are compared: the whole row -- phase, stage *and* summary, in the table's order -- the
phases that are declared and not built, the module each built stage is supposed to live in, that
module's ``STEP ·`` docstring (Requirement 3), and the key each stage's output lands in on the
record.

**The fifth closes a triangle that was open.** I3 compared the flow to the document and I20 compares
the record to the document, and nothing compared the flow to the record -- so a stage renamed in
``flow.py``, in the spec table and in its module filename, but not on its phase model, passed every
guard in this directory. What it produced was ``metrics.json`` reporting that stage as ``0`` for
every record, for ever, with ``make check`` green. ``Stage.phase``'s own comment says the phase is
"the record key its output lands in"; this is what makes that sentence a fact rather than a note.

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
from collections.abc import Sequence
from pathlib import Path

import pytest

from dataforce.pipeline.flow import DECLARED_ONLY, FROM_SOURCE, PHASES, STAGES
from dataforce.pipeline.runner import stage_module_name
from dataforce.record import Record

from .tree import SPEC, SRC, module_at, plain

# What a phase model holds besides one key per stage: the configuration that phase resolved. Named
# by suffix rather than listed, because `human_review` calls its own `human_config` and a list here
# would be a second statement of three field names.
CONFIG = "_config"

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


def folded_phases() -> list[str]:
    """Every phase whose stages write a key on the record: the ones `corpus_counts` counts.

    `load_data` makes records rather than writing on one, and `release` has no module -- the same
    two exclusions `edge/artifacts.py` applies, read from the same two constants so the fold and
    this guard cannot disagree about which phases it is about.
    """
    return [
        phase
        for phase in PHASES
        if phase not in FROM_SOURCE and phase not in DECLARED_ONLY
    ]


def phase_keys(phase: str) -> tuple[str, ...]:
    """The keys `Record.<phase>` holds, or `()` where the record declares no such phase at all."""
    field = Record.model_fields.get(phase)
    return tuple(getattr(field.annotation, "model_fields", {})) if field else ()


def stage_key_findings(
    phase: str, stages: Sequence[str], held: Sequence[str]
) -> list[str]:
    """Every stage of that phase the record has no key for, and every key no stage writes.

    Both directions, because *closed* is the claim: a stage with no key reports zero for ever, and
    a key no stage writes is a field nothing fills. A `<phase>_config` key is neither -- it is what
    that phase was run under, and § *The record* draws it.
    """
    keys = set(held)
    return [
        f"{phase}.{stage} is a stage whose output the record has no key for"
        for stage in stages
        if stage not in keys
    ] + [
        f"{phase}.{name} is a record key no stage of that phase writes"
        for name in sorted(keys - set(stages))
        if not name.endswith(CONFIG)
    ]


def test_the_table_names_every_stage_once() -> None:
    """Guards the parser, not the code: a row this regex silently skipped is a row nothing checks."""
    rows = spec_rows()

    assert len(rows) > 1
    assert len({stage for _, stage, _ in rows}) == len(rows)


def test_the_code_and_the_document_declare_the_same_rows() -> None:
    """I3: a row nobody implemented, a row renamed on one side, a reordering, or a reworded summary.

    The summary is compared too. A field of the table that nothing checks is the fiction this guard is
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


@pytest.mark.parametrize("phase", folded_phases(), ids=lambda p: p)
def test_each_phase_model_holds_one_key_per_stage_and_nothing_else(phase: str) -> None:
    """I3, flow -> record: the third edge, and the one `edge/artifacts.py` folds over."""
    stages = [row.stage for row in STAGES if row.phase == phase]

    assert stage_key_findings(phase, stages, phase_keys(phase)) == []


def test_the_scan_found_the_phases_it_is_supposed_to_scan() -> None:
    """Guards the discovery: an empty list would make the comparison above vacuous."""
    folded = folded_phases()

    assert folded and "load_data" not in folded and "release" not in folded
    assert all(phase_keys(phase) for phase in folded)


@pytest.mark.parametrize(
    ("stages", "held"),
    [
        (("jury", "cohesion"), ("jury", "cohesion_scores")),
        (("jury",), ("jury", "panel")),
        (("jury",), ()),
    ],
    ids=["a-renamed-stage", "a-key-no-stage-writes", "a-phase-the-record-forgot"],
)
def test_the_scan_rejects_a_flow_the_record_does_not_match(
    stages: tuple[str, ...], held: tuple[str, ...]
) -> None:
    """Proved red: the drift that used to report `0` for ever, and its two neighbours."""
    assert stage_key_findings("ai_review", stages, held) != []


def test_a_phase_s_own_config_key_is_not_a_stage_that_went_missing() -> None:
    """`<phase>_config` is what that phase was run under; § *The record* draws it as a key."""
    assert (
        stage_key_findings("ai_review", ("jury",), ("jury", "ai_review_config")) == []
    )
