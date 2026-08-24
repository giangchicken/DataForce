"""TOOL · the source tree as the guards read it, and the exemptions annotated in it.

Every guard is an AST scan or a model introspection over the same tree, so the walking, the parsing
and the import resolution live here once and each rule lives in the ``test_*`` module that states
it. Nothing here knows any rule.

**Exemptions (P30).** A rule with no escape hatch gets bypassed entirely -- the import moves to a
helper, or someone deletes the check -- so a line may carry::

    # guard-exempt: I2 · why · who owns it · 2026-08-23

and the guard that invariant belongs to will pass over that line. Every guard filters through
`not_exempt`, and `test_exemptions.py` keeps the list well-formed and short.
"""

import ast
import re
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

SRC = Path(__file__).resolve().parents[2] / "src" / "dataforce"
SPEC = Path(__file__).resolve().parents[2] / "docs" / "annotation-pipeline" / "spec.md"

MARKER = "guard-exempt"
EXEMPTION = re.compile(
    rf"#\s*{MARKER}:\s*(?P<invariant>I\d+)"
    r"\s*·\s*(?P<reason>[^·]+?)"
    r"\s*·\s*(?P<owner>[^·]+?)"
    r"\s*·\s*(?P<date>\d{4}-\d{2}-\d{2})\s*$"
)


class Module(NamedTuple):
    """One module as a guard sees it: what to call it in a failure message, and its syntax."""

    name: str  # dotted, the way an importer writes it: `dataforce.pipeline.flow`
    package: str  # the dotted package a relative import inside it resolves against
    lines: tuple[
        str, ...
    ]  # the source, for the exemptions -- a comment is not in the tree
    tree: ast.Module  # the parsed source; every rule reads this


class Import(NamedTuple):
    """One module name an import statement makes reachable, absolute, and where it says it."""

    module: str  # dotted and absolute, relative imports already resolved
    line: int  # the line of the statement, for the failure message and for an exemption


def plain(text: str) -> str:
    """One line with its markup gone, so a document and a docstring compare as words.

    The spec writes single backticks and an em dash, a docstring writes double backticks and `--`,
    and either may or may not end in a stop. None of that is the fact being compared.
    """
    bare = text.replace("`", "").replace("—", "--").replace("–", "--")
    return re.sub(r"\s+", " ", bare).strip().rstrip(".")


def module_from_source(
    source: str, name: str = "dataforce.synthetic", package: str | None = None
) -> Module:
    """The module that source holds. A guard's P29 proof passes a violation in here.

    `package` is what a relative import inside it resolves against. The default is the parent, which
    is right for a module and wrong for an `__init__.py`, where the package *is* the name -- so a
    synthetic façade has to say so or its `from . import x` resolves one level too high.
    """
    return Module(
        name,
        name.rsplit(".", 1)[0] if package is None else package,
        tuple(source.splitlines()),
        ast.parse(source),
    )


def module_at(path: Path) -> Module:
    """The module that file holds. `path` is absolute, and under `SRC`."""
    parts = path.relative_to(SRC.parent).with_suffix("").parts
    is_init = parts[-1] == "__init__"
    name = ".".join(parts[:-1] if is_init else parts)
    package = name if is_init else ".".join(parts[:-1])
    source = path.read_text(encoding="utf-8")
    return Module(
        name, package, tuple(source.splitlines()), ast.parse(source, str(path))
    )


def modules_in(package: str = "") -> list[Module]:
    """Every module under `src/dataforce/<package>`, parsed. The default is the whole package."""
    root = SRC / package if package else SRC
    return [module_at(p) for p in sorted(root.rglob("*.py"))]


def engine_modules() -> list[Module]:
    """Every module the engine owns: the package less `edge/` and `cli.py` (Requirement 36)."""
    return [
        module
        for module in modules_in()
        if not module.name.startswith("dataforce.edge")
        and module.name != "dataforce.cli"
    ]


def axis_implementations() -> list[Path]:
    """Every registrable implementation of either axis: the sub-packages beside a `base.py`."""
    return sorted(
        package
        for axis in ("modalities", "profiles")
        for package in (SRC / axis).iterdir()
        if package.is_dir() and not package.name.startswith("__")
    )


def imports(module: Module) -> list[Import]:
    """Every module name this one reaches, absolute.

    `from x import y` yields both `x` and `x.y`: either spelling is how a forbidden module gets
    in, and only the second one names it when `y` is a sub-package.
    """
    found: list[Import] = []
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            found += [Import(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(module, node)
            found.append(Import(base, node.lineno))
            found += [
                Import(f"{base}.{alias.name}", node.lineno)
                for alias in node.names
                if alias.name != "*"
            ]
    return found


def called_name(node: ast.Call) -> str:
    """The dotted name a call names -- `open`, `datetime.now`, `a.b.c` -- or `""` if it names none."""
    parts: list[str] = []
    target: ast.expr = node.func
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if not isinstance(target, ast.Name):
        return ""
    parts.append(target.id)
    return ".".join(reversed(parts))


def not_exempt(
    module: Module, invariant: str, found: Iterable[tuple[int, str]]
) -> list[str]:
    """The findings whose line carries no annotated exemption for that invariant (P30)."""
    return [
        f"{module.name}:{line} {message}"
        for line, message in found
        if not _exemption_on(module, line, invariant)
    ]


def exemptions(modules: Iterable[Module]) -> list[str]:
    """Every well-formed exemption in those modules -- the list P30 asks to be kept short."""
    return [
        f"{module.name}:{number} {match['invariant']} · {match['reason']} ·"
        f" {match['owner']} · {match['date']}"
        for module in modules
        for number, line in enumerate(module.lines, start=1)
        if (match := EXEMPTION.search(line))
    ]


def malformed_exemptions(modules: Iterable[Module]) -> list[str]:
    """Every line claiming an exemption without naming an invariant, a reason, an owner, a date."""
    return [
        f"{module.name}:{number} {line.strip()}"
        for module in modules
        for number, line in enumerate(module.lines, start=1)
        if MARKER in line and not EXEMPTION.search(line)
    ]


def _absolute(module: Module, node: ast.ImportFrom) -> str:
    """One `from ... import` resolved against the package the module sits in."""
    if not node.level:
        return node.module or ""
    parts = module.package.split(".")
    base = parts[: len(parts) - node.level + 1]
    return ".".join([*base, node.module] if node.module else base)


def _exemption_on(module: Module, line: int, invariant: str) -> bool:
    if not 0 < line <= len(module.lines):
        return False
    match = EXEMPTION.search(module.lines[line - 1])
    return match is not None and match["invariant"] == invariant
