"""TOOL · the source tree as the guards read it: a module's dotted name, and its parsed source.

Every guard is an AST scan or a model introspection over the same tree, so the walking and parsing
live here once and the rules live in the ``test_*`` module that states each of them.
"""

import ast
from pathlib import Path
from typing import NamedTuple

SRC = Path(__file__).resolve().parents[2] / "src" / "dataforce"


class Module(NamedTuple):
    """One module as a guard sees it: what to call it in a failure message, and its syntax."""

    name: str  # dotted, the way an importer writes it: `dataforce.pipeline.flow`
    package: str  # the dotted package a relative import inside it resolves against
    tree: ast.Module  # the parsed source; every guard reads this and never the text


def module_at(path: Path) -> Module:
    """The module that file holds. `path` is absolute, and under `SRC`."""
    parts = path.relative_to(SRC.parent).with_suffix("").parts
    package = ".".join(parts if parts[-1] == "__init__" else parts[:-1])
    name = package if parts[-1] == "__init__" else ".".join(parts)
    return Module(name, package, ast.parse(path.read_text(encoding="utf-8"), str(path)))


def modules_in(package: str = "") -> list[Module]:
    """Every module under `src/dataforce/<package>`, parsed. The default is the whole package."""
    root = SRC / package if package else SRC
    return [module_at(p) for p in sorted(root.rglob("*.py"))]
