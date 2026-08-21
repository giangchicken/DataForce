"""The phase and stage names in code are the document's, and cannot drift from it.

`core/flow.py` is a copy of one column of the core spec's stage table. A copy is worth
having -- four string literals were repeated across `pipeline/`, `core/artifacts/` and
every profile -- but only while something proves it is still a copy. That is this file.

The phase names are a file layout in three places, and each is checked here:
`core/artifacts/<phase>.py`, `pipeline/<phase>/` -- which is also where the *stage*
names become filenames -- and, in `test_layout.py`, `profiles/<name>/<phase>.py`. The
`pipeline/` half arrived with stage 0: until then the directory held nothing, so the one
mirror that holds the stages was the one nothing checked.

`api.STAGES` is checked against the same table, because it decides what order stages run
in and a table that disagreed with the document would run one before what it reads.

The parse is in `conftest.stage_table`, which asserts it read something, so a table that
moves fails here instead of passing vacuously.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import SOURCE_ROOT, first_docstring_line, stage_table

from dataforce import api
from dataforce.core.flow import PHASES

FLOW_STAGES = 15

PIPELINE = SOURCE_ROOT / "pipeline"

# `STEP · load (stage 0) · every source item as ...`. The stage and its number are the
# checked part; what follows the second separator is prose. One stage rather than a range,
# which is what makes a stage module a different thing from a profile's phase module.
_STAGE_LINE = re.compile(r"^STEP · (\w+) \(stage (\d+)\)(?: · .+)?$")


def phase_of_stage() -> dict[str, str]:
    """Which phase the document puts each stage in."""
    return {stage: phase for _, phase, stage in stage_table()}


def stage_numbers() -> dict[str, int]:
    """Which number the document gives each stage."""
    return {stage: number for number, _, stage in stage_table()}


def stage_packages() -> list[Path]:
    """Every phase package under `pipeline/` that exists yet."""
    return [
        path
        for path in sorted(PIPELINE.iterdir())
        if path.is_dir() and (path / "__init__.py").exists()
    ]


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


def test_every_pipeline_directory_is_a_phase_of_the_flow() -> None:
    """Subset rather than equality: the stages of a phase arrive with that phase."""
    directories = {package.name for package in stage_packages()}
    assert directories, "no phase package under pipeline/ -- this would pass vacuously"
    unknown = directories - {phase.name for phase in PHASES}
    assert not unknown, (
        f"pipeline/ holds {sorted(unknown)}, which `core/flow.py` does not name; a "
        "stage lives under the phase that owns it"
    )


def test_every_stage_module_is_a_stage_of_its_own_phase_and_says_which() -> None:
    """The filename, the directory and the docstring all have to agree with the table."""
    phases, numbers = phase_of_stage(), stage_numbers()
    seen = 0
    for package in stage_packages():
        for path in sorted(package.glob("*.py")):
            if path.stem == "__init__":
                continue
            seen += 1
            assert phases.get(path.stem) == package.name, (
                f"{path.stem}.py is under {package.name}/, and the stage table puts "
                f"stage {path.stem!r} in {phases.get(path.stem)!r}"
            )
            found = _STAGE_LINE.match(first_docstring_line(path))
            assert found, f"{path} does not open `STEP · <stage> (stage N)`"
            assert found.group(1) == path.stem, f"{path} says it is {found.group(1)}"
            assert int(found.group(2)) == numbers[path.stem], (
                f"{path} claims stage {found.group(2)}, the table says "
                f"{numbers[path.stem]}"
            )
    assert seen, "no stage module was scanned -- this would pass vacuously"


def test_the_built_stages_run_in_the_documents_order() -> None:
    """`api.STAGES` is a subset of the table, in the table's order, with its phases.

    Order matters because a stage reads what the one before it wrote, and naming stages
    on the command line must not be able to reverse that.
    """
    built = list(api.STAGES)
    assert built, "no stage is built -- this would pass vacuously"
    declared = [stage for _, _, stage in stage_table()]
    unknown = set(built) - set(declared)
    assert not unknown, f"{sorted(unknown)} is not a stage the spec declares"
    assert built == [stage for stage in declared if stage in set(built)]
    phases = phase_of_stage()
    for stage, wiring in api.STAGES.items():
        assert wiring.phase == phases[stage], (
            f"api.STAGES writes {stage!r} into {wiring.phase!r}; the table says "
            f"{phases[stage]!r}"
        )
