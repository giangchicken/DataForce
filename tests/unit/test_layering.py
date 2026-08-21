"""The engine computes and never opens a file, asserted rather than remembered.

`modalities/`, `profiles/`, `pipeline/` and `core/` are the engine. Everything it
needs arrives already parsed, which is what lets a web handler, a notebook or another
codebase import it from any working directory. `api/`, `declared/` and `cli.py` are
where the filesystem lives, so none of them is guarded here.

Both guards below are proved rather than trusted. The AST one is proved against
synthetic source, the way `test_import_graph.py` and `test_naming.py` prove theirs;
both were also run against the tree as it stood before this phase, where the first
named five sites and the second failed outright.

The subprocess guard cannot be written as an in-process assertion. By the time any
assertion runs the module is already imported -- and importing it used to be the
failure, because `TEXT = TextModality(read_manifest(...))` read a relative path.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from conftest import SOURCE_ROOT, docstring_ids, parsed_sources

GUARDED_PACKAGES = ("modalities", "profiles", "pipeline", "core")

# Where the committed policy and the data tiers live. A module that spells one of
# these in code has decided which directory it is being run from. Saying where the
# policy lives is a docstring's job, and a docstring is not code, so it is exempt --
# the same distinction `test_prompts.py` draws about prose mentioning a placeholder.
LOCATIONS = ("config/", "data/", "metrics/", "params.yaml")

# The two layers above the engine, and the library's file reader. The arrow points
# one way: `api/` and `declared/` import the engine, never the reverse.
IMPORTS = ("agent_toolkit.file_utils", "dataforce.api", "dataforce.declared")


def _imported(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return {module} | {f"{module}.{alias.name}" for alias in node.names}
    return set()


def violations(tree: ast.Module) -> list[str]:
    """Every place one module reaches for the filesystem, with its line."""
    documentation = docstring_ids(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        for imported in _imported(node):
            for forbidden in IMPORTS:
                if imported.startswith(forbidden):
                    found.append(f"line {node.lineno}: imports {imported}")
        if isinstance(node, ast.Call):
            opener = node.func
            name = (
                opener.id
                if isinstance(opener, ast.Name)
                else opener.attr
                if isinstance(opener, ast.Attribute)
                else ""
            )
            if name == "open":
                found.append(f"line {node.lineno}: calls open()")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in documentation
        ):
            for location in LOCATIONS:
                if location in node.value:
                    found.append(f"line {node.lineno}: names {location!r}")
    return sorted(found)


def guarded_modules(source_root: Path = SOURCE_ROOT) -> dict[Path, list[str]]:
    """Every engine module, with whatever it does that it may not."""
    found: dict[Path, list[str]] = {}
    for path, tree in parsed_sources(source_root):
        if any(part in GUARDED_PACKAGES for part in path.parts):
            found[path.relative_to(source_root)] = violations(tree)
    return found


def test_no_engine_module_touches_the_filesystem() -> None:
    scanned = guarded_modules()

    assert len(scanned) > 10, (
        f"only {len(scanned)} modules scanned -- this would pass vacuously"
    )
    offenders = {str(path): found for path, found in scanned.items() if found}
    assert not offenders, f"the engine may not read a file or know a path: {offenders}"


def test_the_guard_catches_each_of_the_three_things_it_forbids() -> None:
    """Proved against source, so the guard is honest before it has ever failed."""
    assert violations(
        ast.parse("from agent_toolkit.file_utils import read_yaml\n")
    ) == [
        "line 1: imports agent_toolkit.file_utils",
        "line 1: imports agent_toolkit.file_utils.read_yaml",
    ]
    assert violations(ast.parse("from dataforce.declared.manifest import x\n")) == [
        "line 1: imports dataforce.declared.manifest",
        "line 1: imports dataforce.declared.manifest.x",
    ]
    assert violations(ast.parse('CONFIG = Path("config")\n')) == []
    assert violations(ast.parse('CONFIG = Path("config/gates.yaml")\n')) == [
        "line 1: names 'config/'"
    ]
    assert violations(ast.parse('PARAMS = Path("params.yaml")\n')) == [
        "line 1: names 'params.yaml'"
    ]
    assert violations(ast.parse('with path.open("rb") as handle:\n    pass\n')) == [
        "line 1: calls open()"
    ]
    assert violations(ast.parse('handle = open("x")\n')) == ["line 1: calls open()"]

    innocent = "from dataforce.core.manifest import Manifest\nx = compute_hash(t)\n"
    assert violations(ast.parse(innocent)) == []

    prose = ast.parse('"""Identity is a line in config/<axis>/<name>.yaml."""\n')
    assert violations(prose) == [], "a docstring saying where the policy lives is prose"


def test_importing_the_engine_from_another_directory_reads_no_file(
    tmp_path: Path,
) -> None:
    """Invariant 19, and the one assertion this whole phase exists to make true.

    Run from a directory holding no `config/`, so a module that reads one off a
    relative path fails here and nowhere else.
    """
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import dataforce.modalities.text, dataforce.profiles.tool_decision",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert done.returncode == 0, done.stderr
    assert not list(tmp_path.iterdir()), "the import wrote something"
