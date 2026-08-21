"""Every implementation of either axis is the same seven files, and they are the flow.

The layout is the answer to *where does stage 8 ask this profile for something*: it is
`human_review.py`, in every profile, without reading one. That only stays true while
something checks it, because the pressure that produced `build_record.py`, `answer.py`
and `ask_annotator.py` -- name the module after the function you are writing -- is
constant and each instance of it looks reasonable alone.

Four claims: the file set is closed, each phase module says which phase it is, no phase
module imports a sibling, and the two phase-independent modules import neither a phase
nor each other. The third and fourth are the ones with teeth: a sibling import is how
one phase's work migrates into another's module without anybody choosing that.

`sibling_phase_imports` and `imported_modules` take a parsed tree so they can be run
against synthetic source, which is how the guards below are shown to fail rather than
assumed to.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from conftest import SOURCE_ROOT

from dataforce.core.flow import PHASES

AXES = ("modalities", "profiles")
PHASE_NAMES = frozenset(phase.name for phase in PHASES)

# What every implementation package holds beyond its phase modules, and nothing else --
# except a module whose docstring declares it out of the flow entirely.
PHASE_INDEPENDENT = frozenset({"__init__", "schema", "utils"})
NOT_IN_THE_FLOW = "TOOL ·"

# `STEP · human_review (stages 7-11) · what a person is asked ...`. The phase and the
# range are the checked part; what follows the second separator is prose.
_STEP_LINE = re.compile(r"^STEP · (\w+) \(stages (\d+)-(\d+)\)(?: · .+)?$")

DOCSTRING_KIND = {"schema": "DEFINITION ·", "utils": "LOGIC ·"}


def implementation_packages(source_root: Path = SOURCE_ROOT) -> list[Path]:
    """Every implementation of either axis that is a package rather than one module."""
    found = [
        child
        for axis in AXES
        for child in sorted((source_root / axis).iterdir())
        if child.is_dir() and (child / "__init__.py").exists()
    ]
    assert found, "no implementation package found -- these guards would pass vacuously"
    return found


def modules_of(package: Path) -> dict[str, Path]:
    return {path.stem: path for path in sorted(package.glob("*.py"))}


def first_docstring_line(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    doc = ast.get_docstring(tree)
    assert doc, f"{path} has no module docstring"
    return doc.splitlines()[0]


def imported_modules(tree: ast.Module, prefix: str) -> set[str]:
    """Which modules of one package this tree imports, however it spells the import.

    Takes the dotted prefix rather than the package name, because the axis is part of it
    and a guard that assumed `profiles` would have read every modality package as
    importing nothing -- passing vacuously on exactly the tree it exists to check.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == prefix:
                found.update(alias.name for alias in node.names)
            elif node.module.startswith(f"{prefix}."):
                found.add(node.module[len(prefix) + 1 :].split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(f"{prefix}."):
                    found.add(alias.name[len(prefix) + 1 :].split(".")[0])
    return found


def sibling_phase_imports(module: str, tree: ast.Module, prefix: str) -> set[str]:
    """The phase modules this phase module imports, which must be none of them."""
    return (imported_modules(tree, prefix) & PHASE_NAMES) - {module}


def dotted_prefix(package: Path) -> str:
    """One implementation package as it is imported: `dataforce.<axis>.<name>`."""
    return f"dataforce.{package.parent.name}.{package.name}"


def test_an_implementation_is_the_seven_files_or_declares_itself_out_of_the_flow() -> (
    None
):
    for package in implementation_packages():
        modules = modules_of(package)
        if set(modules) == {"__init__"}:
            # One module until a second consumer needs half of it, and then it splits
            # into these same names -- the module-layout spec's Decision 7.
            continue
        expected = PHASE_INDEPENDENT | PHASE_NAMES
        missing = expected - set(modules)
        assert not missing, f"{package.name} has no {sorted(missing)}"
        for extra in sorted(set(modules) - expected):
            line = first_docstring_line(modules[extra])
            assert line.startswith(NOT_IN_THE_FLOW), (
                f"{package.name}/{extra}.py is not one of the seven and does not "
                f"declare itself out of the flow: {line!r}"
            )


def test_every_phase_module_states_its_own_phase_and_stage_range() -> None:
    ranges = {phase.name: (phase.first_stage, phase.last_stage) for phase in PHASES}
    seen = 0
    for package in implementation_packages():
        for name, path in modules_of(package).items():
            if name not in PHASE_NAMES:
                continue
            seen += 1
            found = _STEP_LINE.match(first_docstring_line(path))
            assert found, (
                f"{package.name}/{name}.py does not open `STEP · <phase> (stages N-M)`"
            )
            assert found.group(1) == name, f"{path} says it is {found.group(1)}"
            assert (int(found.group(2)), int(found.group(3))) == ranges[name], (
                f"{path} claims stages {found.group(2)}-{found.group(3)}, "
                f"`core/flow.py` gives {name} {ranges[name]}"
            )
    # At least one full set, not exactly one: a second implementation that splits
    # brings its own four, and an equality here would fail on the arrival of the very
    # thing this file exists to keep uniform.
    assert seen >= len(PHASES), f"only {seen} phase modules scanned"


def test_the_two_phase_independent_modules_say_which_kind_they_are() -> None:
    """A shape is a shape and a conversion is logic -- AGENTS.md §6, in the docstring."""
    for package in implementation_packages():
        for name, prefix in DOCSTRING_KIND.items():
            path = modules_of(package).get(name)
            if path is None:
                continue
            assert first_docstring_line(path).startswith(prefix), f"{path}"


def test_no_phase_module_imports_a_sibling_phase() -> None:
    for package in implementation_packages():
        for name, path in modules_of(package).items():
            if name not in PHASE_NAMES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            siblings = sibling_phase_imports(name, tree, dotted_prefix(package))
            assert not siblings, (
                f"{package.name}/{name}.py imports {sorted(siblings)}; anything two "
                "phases need belongs in schema.py or utils.py"
            )


def test_schema_and_utils_import_no_phase_module_and_schema_imports_no_utils() -> None:
    for package in implementation_packages():
        modules = modules_of(package)
        for name in ("schema", "utils"):
            path = modules.get(name)
            if path is None:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = imported_modules(tree, dotted_prefix(package))
            assert not imported & PHASE_NAMES, (
                f"{package.name}/{name}.py imports the phase module(s) "
                f"{sorted(imported & PHASE_NAMES)}"
            )
        schema = modules.get("schema")
        if schema is not None:
            tree = ast.parse(schema.read_text(encoding="utf-8"), filename=str(schema))
            assert "utils" not in imported_modules(tree, dotted_prefix(package)), (
                f"{package.name}/schema.py imports utils.py -- a shape must not depend "
                "on a conversion over it"
            )


def test_the_sibling_guard_finds_one_when_there_is_one() -> None:
    """Proved against synthetic source, three spellings of the same mistake."""
    for prefix in ("dataforce.profiles.x", "dataforce.modalities.x"):
        for source in (
            f"from {prefix}.ai_review import vote_consensus\n",
            f"from {prefix} import ai_review\n",
            f"import {prefix}.ai_review\n",
        ):
            found = sibling_phase_imports("human_review", ast.parse(source), prefix)
            assert found == {"ai_review"}, f"{source!r} slipped past the guard"


def test_the_sibling_guard_allows_the_phase_independent_two() -> None:
    source = (
        "from dataforce.profiles.x.schema import Catalog\n"
        "from dataforce.profiles.x.utils import answer_distance\n"
        "from dataforce.core.record import Record\n"
    )
    prefix = "dataforce.profiles.x"
    assert sibling_phase_imports("ai_review", ast.parse(source), prefix) == set()


def test_the_guard_reads_the_axis_and_not_only_profiles() -> None:
    """A modality package's own imports were invisible to this before the prefix."""
    source = "from dataforce.modalities.x.release import training_example\n"
    assert imported_modules(ast.parse(source), "dataforce.modalities.x") == {"release"}
    assert imported_modules(ast.parse(source), "dataforce.profiles.x") == set()
