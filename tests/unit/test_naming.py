"""Every function in either axis is named for its result, not for an operation.

The two objectively checkable halves of that convention. The third -- whether a
name actually reads as its result -- needs a person, so it is not here.

A name shared with a stage makes a sentence ambiguous rather than wrong: `load`
was stage 0 and a modality member at once, and most of its ten mentions in the
core spec were the stage. A bare operation names no object, so read alone it says
nothing -- *parse what, into what?*

`declared/` is in scope too, since it is the surface both axes are configured
through. `core/` and `pipeline/` are out of scope, which is a scope and not a clean
bill -- though the three names that broke both halves, `manifest.load`, `prompts.load`
and `prompts.render`, are now `read_manifest`, `read_prompt` and gone respectively.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import SOURCE_ROOT, stage_table

# Both axes, plus the package that reads their configuration.
GUARDED_PACKAGES = ("modalities", "profiles", "declared")

# Operations with no object. Every one of them was a member name here before R1.
BARE_OPERATIONS = frozenset(
    {"adapt", "parse", "of", "render", "export", "load", "embed", "measure", "drift"}
)


def stage_names() -> set[str]:
    """The stage column of the core spec's stage table.

    Parsed by `conftest.stage_table`, which is also what `test_flow.py` checks the
    phase names against: one regex for one table, so the two guards cannot come to
    different conclusions about what the document says.
    """
    found = {stage for _, _, stage in stage_table()}
    # The three the convention was invented for.
    assert {"load", "embed", "export"} <= found, f"read only {sorted(found)}"
    return found


def guarded_functions() -> dict[str, Path]:
    """Every public function and method under a guarded package, by name."""
    found: dict[str, Path] = {}
    for package in GUARDED_PACKAGES:
        for path in sorted((SOURCE_ROOT / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    found.setdefault(node.name, path)
    return found


def test_no_guarded_function_is_named_after_a_stage() -> None:
    functions = guarded_functions()
    assert len(functions) > 20, "no function was scanned -- this would pass vacuously"
    shared = {
        name: str(path.relative_to(SOURCE_ROOT))
        for name, path in functions.items()
        if name in stage_names()
    }
    assert not shared, (
        f"these read as a stage in any sentence that mentions them: {shared}"
    )


def test_no_guarded_function_is_a_bare_operation() -> None:
    offenders = {
        name: str(path.relative_to(SOURCE_ROOT))
        for name, path in guarded_functions().items()
        if name in BARE_OPERATIONS
    }
    assert not offenders, f"these name an operation with no object: {offenders}"
