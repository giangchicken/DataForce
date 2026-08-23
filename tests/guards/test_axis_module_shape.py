"""I4 · every axis implementation is `__init__`, `schema`, `utils`, and `schema` imports no `utils`.

Three modules, closed. A shape is a shape and a conversion over it is logic; they change for
different reasons, so they are different files and the dependency runs one way -- ``utils.py`` may
read the shapes beside it, ``schema.py`` may not read the conversions. ``utils`` is the one module
name AGENTS.md §6 exempts, and only under exactly this condition; a fourth module in the package is
that exemption starting to spread.

This guard reads directories rather than the parsed tree, because the rule is about which files
exist. The synthetic violation is therefore a directory too.
"""

from pathlib import Path

import pytest

from .tree import axis_implementations, imports, module_from_source

SHAPE = frozenset({"__init__.py", "schema.py", "utils.py"})


def axis_shape_findings(package: Path) -> list[str]:
    """Every way this implementation departs from the three modules and the one direction."""
    found = []
    present = {path.name for path in package.glob("*.py")}
    if present != SHAPE:
        found.append(f"{package.name} holds {sorted(present)}, not {sorted(SHAPE)}")

    schema = package / "schema.py"
    if schema.exists():
        dotted = f"dataforce.{package.parent.name}.{package.name}.schema"
        module = module_from_source(schema.read_text(encoding="utf-8"), dotted)
        found += [
            f"{dotted}:{reached.line} imports its own utils"
            for reached in imports(module)
            if reached.module.split(".")[-1] == "utils"
        ]
    return found


@pytest.mark.parametrize("package", axis_implementations(), ids=lambda p: p.name)
def test_every_axis_implementation_has_the_three_modules(package: Path) -> None:
    """I4, over both axes."""
    assert axis_shape_findings(package) == []


def test_the_scan_rejects_a_fourth_module(tmp_path: Path) -> None:
    """P29: `utils.py` is exempted for one job, and a fourth file is that exemption spreading."""
    package = _implementation(tmp_path, extra="detectors.py")

    assert axis_shape_findings(package) != []


def test_the_scan_rejects_a_missing_module(tmp_path: Path) -> None:
    """P29: two modules is a shape too, and not this one."""
    package = _implementation(tmp_path)
    (package / "utils.py").unlink()

    assert axis_shape_findings(package) != []


def test_the_scan_rejects_a_schema_that_imports_its_utils(tmp_path: Path) -> None:
    """P29: the direction, proved both spellings of the import."""
    absolute = _implementation(
        tmp_path, schema="from dataforce.profiles.p.utils import to_schema"
    )
    relative = _implementation(
        tmp_path / "second", schema="from .utils import to_schema"
    )

    assert axis_shape_findings(absolute) != []
    assert axis_shape_findings(relative) != []


def test_the_scan_permits_a_utils_that_imports_its_schema(tmp_path: Path) -> None:
    """The direction is one way, not no way: a conversion reads the shapes beside it."""
    package = _implementation(tmp_path)
    (package / "utils.py").write_text("from .schema import Call\n", encoding="utf-8")

    assert axis_shape_findings(package) == []


def _implementation(root: Path, *, schema: str = "", extra: str = "") -> Path:
    """One synthetic axis implementation on disk, so the guard reads it the way it reads a real one."""
    package = root / "profiles" / "p"
    package.mkdir(parents=True)
    for name in SHAPE:
        (package / name).write_text(
            schema if name == "schema.py" else "", encoding="utf-8"
        )
    if extra:
        (package / extra).write_text("", encoding="utf-8")
    return package
