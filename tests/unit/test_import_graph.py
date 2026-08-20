"""The core is task-agnostic and modality-agnostic, and stays that way.

This property degrades silently: one import added under deadline is how a stage
acquires an opinion about what an answer is. Both axes arrive through their
registries, so no module under `pipeline/` or `shared/` may name a concrete one.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import SOURCE_ROOT, parsed_sources

GENERIC_MODULES = frozenset({"__init__", "base", "registry"})
GUARDED_PACKAGES = ("pipeline", "shared")


def concrete_implementations(source_root: Path = SOURCE_ROOT) -> set[str]:
    """Every implementation of either axis, as an importable suffix."""
    found: set[str] = set()
    for axis in ("modalities", "profiles"):
        for child in sorted((source_root / axis).iterdir()):
            stem = child.stem
            if stem in GENERIC_MODULES or stem.startswith("_"):
                continue
            if child.is_dir() or child.suffix == ".py":
                found.add(f"{axis}.{stem}")
    return found


def imported_paths(tree: ast.Module) -> set[str]:
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            paths.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            paths.add(module)
            paths.update(f"{module}.{alias.name}" for alias in node.names)
    return paths


def concrete_imports(tree: ast.Module, concrete: set[str]) -> set[str]:
    return {path for path in imported_paths(tree) for name in concrete if name in path}


def test_no_generic_module_imports_a_concrete_profile_or_modality() -> None:
    concrete = concrete_implementations()
    scanned = 0
    for path, tree in parsed_sources():
        if not any(part in GUARDED_PACKAGES for part in path.parts):
            continue
        scanned += 1
        assert not concrete_imports(tree, concrete), (
            f"{path.relative_to(SOURCE_ROOT)} imports a concrete implementation; "
            "both axes arrive through their registries"
        )
    assert scanned, "no guarded module was scanned -- this test would pass vacuously"


def test_the_check_catches_the_import_it_exists_to_catch() -> None:
    """Proved against source, so the guard is honest before any profile exists."""
    offending = ast.parse(
        "from dataforce.profiles.tool_decision import ToolDecisionProfile\n"
    )
    assert concrete_imports(offending, {"profiles.tool_decision"})

    innocent = ast.parse("from dataforce.profiles.registry import get\n")
    assert not concrete_imports(innocent, {"profiles.tool_decision"})
