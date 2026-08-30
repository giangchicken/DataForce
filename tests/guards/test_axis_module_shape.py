"""I4 · an axis's `schema.py` imports no sibling, and a `utils.py` beside it holds only conversions.

A shape is a shape and a conversion over it is logic; they change for different reasons, so they are
different files and the dependency runs one way -- a conversion may read the shapes beside it, a
shape may not read the conversions.

**This guard counted files until T55, and that was the defect.** It required exactly `__init__.py`,
`schema.py` and `utils.py`, and failed on a fourth. AGENTS.md says the remedy for a ``utils.py``
that has outgrown its exemption is to give it a real name -- so the guard made the convention's own
remedy a build failure, and a rule that forbids its own remedy turns every later addition into
``utils.py``, which is the outcome the convention exists to prevent. AGENTS.md records the
resolution: a guard may fix a package's shape only where the
conventions state that shape, and should prefer to constrain the direction of an import over the
number of files.

So the file-set half is gone and two halves stand in its place.

**One · ``schema.py`` exists and imports nothing from its own package.** Generalised from *imports no
``utils``*: a ``schema.py`` that imports ``detectors.py`` is the same defect under a new filename, and
the old spelling could not see it. Reading directories is still right for *exists*, because that half
is about which files there are.

**Two · every top-level function in a ``utils.py`` references a shape ``schema.py`` defines.** This is
the convention's condition on the one module name it exempts -- "only for conversions over the shapes in the
``schema.py`` beside it" -- checked for the first time. *Every*, not *most*: the convention says "and nothing
else", and a threshold would be a tuned literal in a guard with no measurement behind it. A
helper that touches no shape is not a conversion over one, and belongs in a module named for what it
produces.

The second half reports **one finding per module**, anchored on line 1 -- the line that means *this
module* rather than one function chosen to stand for the rest, and the one place a `#` comment sits
above a docstring without disturbing it. The message names every offender.

**Both implementations carried that annotation between T55 and T56, and neither does now.** Only 2 of
16 top-level functions in ``text2text/utils.py`` touched a shape, and 5 of 23 in
``tool_decision/utils.py``, so the two annotations were excusing 14 and 18 -- the measurement that
reopened this, and not a hypothetical. T56 split both packages into modules named for what they
produce, and the annotations went with the files that carried them.

A package with no ``utils.py`` passes the second half with nothing to say, which is where both of
them are. The rule stands for the next axis someone writes, which is when it is worth having.
"""

import ast
from pathlib import Path

import pytest

from .tree import Module, axis_implementations, imports, module_from_source, not_exempt

SCHEMA = "schema.py"
UTILS = "utils.py"


def defined_shapes(schema: Module) -> frozenset[str]:
    """Every name `schema.py` declares at module level: a class, a type alias, or an assignment.

    Assignments count because a shape may be spelled as one -- `type Calls = tuple[Call, ...]` and a
    module-level constant are both things a conversion converts over. Being generous here is the safe
    direction: the finding is *this function touches nothing from schema.py at all*, and a name that
    should not have counted can only turn a finding into a pass, never the reverse.
    """
    names: set[str] = set()
    for node in schema.tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias):
            names.add(ast.unparse(node.name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
    return frozenset(names)


def names_in(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Every identifier this function mentions, in its signature or its body."""
    return {node.id for node in ast.walk(function) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(function) if isinstance(node, ast.Attribute)
    }


def unconverted(utils: Module, shapes: frozenset[str]) -> list[tuple[int, str]]:
    """The one finding a `utils.py` earns when it holds something that is not a conversion.

    **One finding, anchored on line 1.** Twelve findings in one file would need twelve annotations to
    excuse and an exemption annotates a line, so the module gets one -- and the line that means *this module*
    is its first, where a `#` comment sits above the docstring without disturbing it. Anchoring on the
    first offending `def` was the other build: it puts a long comment on a real signature, which the
    formatter then splits across three lines, and it picks one function to stand for a fact about all
    of them. The message names every offender so the annotation is written by someone who saw the list.
    """
    functions = [
        node
        for node in utils.tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    missing = [node for node in functions if not names_in(node) & shapes]
    if not missing:
        return []
    named = ", ".join(node.name for node in missing)
    return [
        (
            1,
            f"{len(missing)} of {len(functions)} top-level functions touch no shape "
            f"from {SCHEMA}, so {UTILS} is holding something the exemption does not cover: {named}",
        )
    ]


def axis_shape_findings(package: Path) -> list[str]:
    """Every way this implementation departs from the one direction and the one condition."""
    schema_path = package / SCHEMA
    if not schema_path.exists():
        return [f"{package.name} has no {SCHEMA}"]

    dotted = f"dataforce.{package.parent.name}.{package.name}"
    schema = module_from_source(
        schema_path.read_text(encoding="utf-8"), f"{dotted}.{SCHEMA[:-3]}"
    )
    found = not_exempt(
        schema,
        "I4",
        [
            (reached.line, f"{SCHEMA} imports {reached.module}, a module beside it")
            for reached in imports(schema)
            if reached.module == dotted or reached.module.startswith(f"{dotted}.")
        ],
    )

    utils_path = package / UTILS
    if utils_path.exists():
        utils = module_from_source(
            utils_path.read_text(encoding="utf-8"), f"{dotted}.{UTILS[:-3]}"
        )
        found += not_exempt(utils, "I4", unconverted(utils, defined_shapes(schema)))
    return found


@pytest.mark.parametrize("package", axis_implementations(), ids=lambda p: p.name)
def test_every_axis_implementation_keeps_the_direction_and_the_condition(
    package: Path,
) -> None:
    """I4, over both axes."""
    assert axis_shape_findings(package) == []


def test_the_scan_rejects_a_schema_that_imports_a_module_beside_it(
    tmp_path: Path,
) -> None:
    """Proved red: the direction, in the three spellings that reach a sibling.

    `utils` is the one the old rule named; `detectors` is the one it could not see, and is the whole
    reason this half was generalised.
    """
    for number, source in enumerate(
        (
            "from dataforce.profiles.p.utils import to_schema",
            "from .utils import to_schema",
            "from .detectors import a_detector",
        )
    ):
        package = _implementation(tmp_path / str(number), schema=source)

        assert axis_shape_findings(package) != [], source


def test_the_scan_rejects_a_utils_holding_something_that_is_not_a_conversion(
    tmp_path: Path,
) -> None:
    """Proved red for the condition no guard checked until T55."""
    package = _implementation(
        tmp_path,
        schema="class Detector:\n    pass\n",
        utils="def spaced(phrase):\n    return phrase\n",
    )

    assert axis_shape_findings(package) != []


def test_the_scan_rejects_a_package_with_no_schema(tmp_path: Path) -> None:
    """Proved red: the half that is still about which files exist, and the only one left."""
    package = _implementation(tmp_path)
    (package / SCHEMA).unlink()

    assert axis_shape_findings(package) != []


def test_the_scan_permits_a_fourth_module(tmp_path: Path) -> None:
    """The rule this task deleted, kept as a green case so the deletion cannot be undone by accident.

    A fourth file was a finding until T55 and is the shape both packages are in since T56. If this
    ever goes red again, the convention's remedy has been made a build failure a second time.
    """
    package = _implementation(
        tmp_path, schema="class Detector:\n    pass\n", extra="detectors.py"
    )

    assert axis_shape_findings(package) == []


def test_the_scan_permits_a_utils_that_converts_the_shapes_beside_it(
    tmp_path: Path,
) -> None:
    """The green case for both halves: the direction is one way, not no way, and a conversion counts."""
    package = _implementation(
        tmp_path,
        schema="class Call:\n    pass\n",
        utils="from .schema import Call\n\n\ndef calls_in(stored) -> Call:\n    return Call()\n",
    )

    assert axis_shape_findings(package) == []


def test_an_annotated_exemption_covers_a_utils_that_has_outgrown_the_condition(
    tmp_path: Path,
) -> None:
    """The hatch both implementations stand on until T56 splits them.

    One annotation for the module, because the finding is one finding -- which is the whole reason
    `unconverted` reports it that way.
    """
    excused = (
        "# guard-exempt: I4 · not yet split · the modality · 2026-08-30\n"
        '"""LOGIC · conversions."""\n\n\n'
        "def spaced(phrase):\n"
        "    return phrase\n"
    )
    package = _implementation(
        tmp_path, schema="class Detector:\n    pass\n", utils=excused
    )

    assert axis_shape_findings(package) == []


def _implementation(
    root: Path, *, schema: str = "", utils: str = "", extra: str = ""
) -> Path:
    """One synthetic axis implementation on disk, so the guard reads it the way it reads a real one."""
    package = root / "profiles" / "p"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / SCHEMA).write_text(schema, encoding="utf-8")
    (package / UTILS).write_text(utils, encoding="utf-8")
    if extra:
        (package / extra).write_text("", encoding="utf-8")
    return package
