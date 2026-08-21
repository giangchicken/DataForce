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
import re
from pathlib import Path

from conftest import REPO_ROOT, SOURCE_ROOT

# Both axes, plus the package that reads their configuration.
GUARDED_PACKAGES = ("modalities", "profiles", "declared")

SPEC = REPO_ROOT / "docs" / "annotation-pipeline" / "spec.md"

# Operations with no object. Every one of them was a member name here before R1.
BARE_OPERATIONS = frozenset(
    {"adapt", "parse", "of", "render", "export", "load", "embed", "measure", "drift"}
)

# A stage-table row: `| 3 | data_quality | `embed` | ... `. The phase column is
# plain words, which is what keeps this off the five-rule table further down.
_STAGE_ROW = re.compile(r"^\|\s*\d+\s*\|\s*[\w ]+\|\s*`(\w+)`\s*\|")


def stage_names(spec: Path = SPEC) -> set[str]:
    """The stage column of the core spec's stage table."""
    found = {
        match.group(1)
        for line in spec.read_text(encoding="utf-8").splitlines()
        if (match := _STAGE_ROW.match(line))
    }
    # The three the convention was invented for. If the table moves and the parse
    # silently reads nothing, this fails instead of passing on an empty set.
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
