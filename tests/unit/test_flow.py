"""The four phase names in code are the document's, and cannot drift from it.

`core/flow.py` is a copy of one column of the core spec's stage table. A copy is worth
having -- four string literals were repeated across `pipeline/`, `core/artifacts/` and
every profile -- but only while something proves it is still a copy. That is this file.

The parse is in `conftest.stage_table`, which asserts it read something, so a table that
moves fails here instead of passing vacuously.
"""

from __future__ import annotations

from conftest import SOURCE_ROOT, stage_table

from dataforce.core.flow import PHASES

FLOW_STAGES = 15


def test_the_phases_are_the_stage_tables_phase_column() -> None:
    """In order, and with no phase the table does not name."""
    ordered: list[str] = []
    for _, phase, _ in stage_table():
        if phase not in ordered:
            ordered.append(phase)
    assert [phase.name for phase in PHASES] == ordered


def test_each_phase_covers_exactly_the_stages_the_table_gives_it() -> None:
    rows = stage_table()
    for phase in PHASES:
        numbered = sorted(number for number, name, _ in rows if name == phase.name)
        assert numbered == list(range(phase.first_stage, phase.last_stage + 1)), (
            f"{phase.name} claims {phase.first_stage}-{phase.last_stage}, "
            f"the table gives it {numbered}"
        )


def test_the_phases_cover_every_stage_once() -> None:
    """No stage in two phases, and no stage in none -- which a range per phase allows."""
    covered = [
        number
        for phase in PHASES
        for number in range(phase.first_stage, phase.last_stage + 1)
    ]
    assert covered == list(range(FLOW_STAGES))


def test_every_phase_has_one_artifact_module() -> None:
    """`core/artifacts/` is the first place the phase names are a file layout."""
    stems = {path.stem for path in (SOURCE_ROOT / "core" / "artifacts").glob("*.py")}
    assert stems == {"__init__", "base"} | {phase.name for phase in PHASES}
