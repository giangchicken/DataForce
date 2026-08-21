"""Every function is named for its result, not for an operation. Private ones too.

Four objectively checkable parts of that convention; the fifth -- whether a name actually
reads as its result -- needs a person, so it is not here.

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

The fourth part is that a name is a name and not a phrase. A joining word --
`from`, `with`, `by`, `as`, `and` -- makes a name describe a relation between two things
instead of naming one, and then the call site has to be read as a sentence. Measured when
the rule arrived: 153 functions, no conjunction among them, and thirteen prepositions. Five
were phrases and were renamed; the other eight are in `JOINED_ALLOWED` with the reason each
is not one, because an allowlist whose entries carry no reason is how a rule decays into a
list of exceptions.

`declared/` is in scope since it is the surface both axes are configured through, and
`core/` is in scope as of the module-layout pass. `pipeline/` joined them with stage 0,
which is the first time there was anything in it -- and it is the package where a name
shared with a stage is most likely, since every module in it is named for one.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import SOURCE_ROOT, stage_table

# Both axes, what they are written against, the stages, and the package that configures
# them.
GUARDED_PACKAGES = ("core", "modalities", "pipeline", "profiles", "declared")

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
        # Phrases rather than names: each described a relation between two things.
        "schema_for",
        "calls_by_name",
        "with_provenance",
        "raw_with_records",
        "turn_as_part",
    }
)

# Words that turn a name into a phrase. `of` is absent on purpose: `list_of_x` is a phrase
# but `part_of_speech` is one noun, and no name here uses either.
JOINING_WORDS = frozenset(
    {"and", "or", "but", "nor", "with", "from", "by", "as", "for", "in", "to", "than"}
)

# The joined names that stay, and why each one is not a phrase. Three reasons only:
# it is a term the spec itself uses, it is a Python idiom, or it is a declared identifier
# that appears in `params.yaml`, a filename or a document table -- where renaming the
# function renames a data contract.
JOINED_ALLOWED = {
    "catalog_from_text": "shared decision 10: a conversion is `Y_from_X`",
    "catalog_from_openai": "shared decision 10",
    "catalog_from_source": "shared decision 10",
    "tool_from_text": "shared decision 10",
    "content_is_by_reference": "`by reference` is the core spec's own term for media",
    "part_is_by_reference": "same term",
    "as_dict": "the `dataclasses.asdict` idiom",
    "label_not_in_catalog": "a `params.yaml` key and a quarantine filename",
}


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


def test_no_guarded_function_name_is_a_phrase() -> None:
    """A name names one thing. A joining word makes it a relation between two."""
    functions = guarded_functions()
    joined = {
        name: str(path.relative_to(SOURCE_ROOT))
        for name, path in functions.items()
        if set(name.split("_")) & JOINING_WORDS and name not in JOINED_ALLOWED
    }
    assert not joined, f"these read as phrases rather than names: {joined}"

    # The allowlist is not a place names accumulate: every entry has to still exist, so
    # deleting one of these functions deletes its exemption rather than leaving it here.
    stale = sorted(set(JOINED_ALLOWED) - set(functions))
    assert not stale, f"{stale} is exempt from a rule it no longer needs exempting from"
