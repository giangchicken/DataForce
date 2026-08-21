"""Every function is named for its result, not for an operation. Private ones too.

Three objectively checkable halves of that convention; the fourth -- whether a name
actually reads as its result -- needs a person, so it is not here.

A name shared with a stage makes a sentence ambiguous rather than wrong: `load` was
stage 0 and a modality member at once, and most of its ten mentions in the core spec
were the stage. A bare operation names no object, so read alone it says nothing --
*parse what, into what?* And a name this repository already removed for either reason
must not come back, which is what `RENAMED_AWAY` is for: a rename with no guard is a
rename that lasts until the next person needs a short name in a hurry.

Private functions are in scope, and the leading underscores are stripped before the
comparison, because AGENTS.md §5 says what the old scope implied was untrue -- *a
private `_` prefix is not an excuse; you still have to read it.* `_note`, `_says`,
`_coerce`, `_turn`, `_leaves` and `_records` all lived in the gap between the rule and
this file.

`declared/` is in scope since it is the surface both axes are configured through, and
`core/` is in scope as of the module-layout pass. `pipeline/` is still out, which is a
scope rather than a clean bill -- there is nothing in it yet.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import SOURCE_ROOT, stage_table

# Both axes, what they are written against, and the package that configures them.
GUARDED_PACKAGES = ("core", "modalities", "profiles", "declared")

# Operations with no object. Every one of them was a member name here before R1.
BARE_OPERATIONS = frozenset(
    {"adapt", "parse", "of", "render", "export", "load", "embed", "measure", "drift"}
)

# Names this repository removed on purpose, so undoing a rename fails here rather than
# depending on a reader who happens to remember. The first eight are the public names the
# module-layout pass replaced -- two of which promised what the other returned,
# `tools_to_catalog` giving text and `catalog_to_tools` giving a Catalog -- and the rest
# are private, which is where they hid: no guard had ever looked at a private name.
RENAMED_AWAY = frozenset(
    {
        "answer_schema_for",
        "build_system_prompt",
        "catalog_to_tools",
        "openai_to_tools",
        "read_catalog",
        "readable_catalog",
        "to_strict_openai",
        "tools_to_catalog",
        "argument_fields",
        "arguments",
        "attribute",
        "call_text",
        "coerce",
        "deduped",
        "effective_required",
        "is_rich",
        "leaves",
        "model",
        "note",
        "one_part",
        "parse_tool",
        "parser",
        "percentile",
        "profile",
        "records",
        "render_tool",
        "says",
        "spec_from",
        "text",
        "turn",
        "usable",
    }
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
    """Every function under a guarded package, keyed by its name without underscores.

    Keyed on the stripped name because the stripped name is what has to be read: `_note`
    and `note` say the same nothing, and the underscore only says who may call it.
    """
    found: dict[str, Path] = {}
    for package in GUARDED_PACKAGES:
        for path in sorted((SOURCE_ROOT / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    found.setdefault(node.name.strip("_"), path)
    return found


def test_no_guarded_function_is_named_after_a_stage() -> None:
    functions = guarded_functions()
    assert len(functions) > 40, "no function was scanned -- this would pass vacuously"
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


def test_no_guarded_function_uses_a_name_this_repo_removed() -> None:
    """A rename is only made once, and this is what makes it stay made."""
    returned = {
        name: str(path.relative_to(SOURCE_ROOT))
        for name, path in guarded_functions().items()
        if name in RENAMED_AWAY
    }
    assert not returned, f"these names were removed on purpose: {returned}"
