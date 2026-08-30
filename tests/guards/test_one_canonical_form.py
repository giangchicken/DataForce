"""I24 · every JSON serialisation in the package is the same one.

`record_id_for` hashes the string `json.dumps` returns, so those three keyword arguments are not a
formatting preference -- they are part of what a `record_id` *is* (Requirements 6-8). Flip
`ensure_ascii` and every Vietnamese record in the corpus gets a new id; drop `sort_keys` and a
record's id starts depending on the order a mapping happened to be built in. I9 cannot see either:
it re-derives both sides of its comparison through the same call, so a change that moves every id
together moves its expectations with them.

**The form was written three times until T56 and is written once now.** It was inline in
`record_id_for` and a `canonical_json` in each axis, and the duplication was deliberate: § *The two
axes* says the two contracts share `name`, `version`, `Part` and one separator *and nothing else*, so
a shared one was a further shared thing and wanted an argument. The argument is that a `record_id`
**is** the hash of the string this form produces, so the form is part of what a record is rather than
a preference two axes happen to share -- it belongs in `record.py`, which both axes already import,
and this rule now has one definition to hold rather than three to keep equal.

**Both halves, because either alone passes the wrong thing.** The scan reads source text and would be
satisfied by a function nobody calls; the comparison runs `canonical_json` over values chosen to tell
each option apart, and would be satisfied by a scan-shaped agreement while the function returned
something else. The scan is over the whole package, so the half that used to matter most -- a fourth
copy appearing somewhere -- is still what `DEFINING_MODULES` says out loud.

`dump` is scanned beside `dumps` because a value written to a file with other options is the same
drift wearing a different name. A call that genuinely wants other options -- a manifest laid out for
a person to read -- is what the exemption hatch is for, annotated on the line; what it may not be is
unremarked.
"""

import ast
import json
from typing import Any

import pytest

from dataforce.record import canonical_json

from .tree import Module, called_name, module_from_source, modules_in, not_exempt

SERIALISERS = ("dump", "dumps")
# The canonical form, as `ast.unparse` spells it. Keys sorted so two mappings that mean one value
# are one string, no incidental whitespace so nothing depends on a formatter, and no `\uXXXX`
# escaping so Vietnamese text is hashed as itself.
CANONICAL = {
    "sort_keys": "True",
    "separators": "(',', ':')",
    "ensure_ascii": "False",
}
CANONICAL_KWARGS: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
}
# The one module that may serialise. A second is a decision about what a `record_id` covers, not an
# import someone added, so it fails here and gets made on purpose.
DEFINING_MODULES = {"dataforce.record"}

# One value per option, each differing from its own canonical string in exactly that option, so a
# comparison that agreed for the wrong reason has nowhere to hide.
DISCRIMINATING: tuple[Any, ...] = (
    {"b": 1, "a": 2},
    {"a": [1, 2], "b": {"c": 3}},
    {"khách": "Nguyễn Văn A"},
    {"b": ["một", {"d": 1, "c": 2}], "a": "hai"},
)


def serialising_calls(module: Module) -> list[tuple[int, ast.Call]]:
    """Every `json.dumps`-shaped call in this module, by line.

    Matched on the last segment of the dotted name rather than on `json.dumps` exactly: `from json
    import dumps` is the same call spelled to evade a scan for the qualified one, and I6 already
    keeps the other libraries that own a `dump` out of `src/`.
    """
    return [
        (node.lineno, node)
        for node in ast.walk(module.tree)
        if isinstance(node, ast.Call)
        and called_name(node).split(".")[-1] in SERIALISERS
    ]


def form_findings(module: Module) -> list[str]:
    """Every serialising call in this module that does not write the canonical form."""
    found = []
    for line, call in serialising_calls(module):
        written = {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}
        if written != CANONICAL:
            found.append((line, f"serialises as {written} rather than {CANONICAL}"))
    return not_exempt(module, "I24", found)


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_every_serialisation_writes_the_canonical_form(module: Module) -> None:
    """I24, over the whole package."""
    assert form_findings(module) == []


def test_the_scan_reads_the_calls_it_is_supposed_to_find() -> None:
    """Guards the discovery: a scan resolving no call would pass every module above."""
    defining = {module.name for module in modules_in() if serialising_calls(module)}

    assert defining == DEFINING_MODULES


@pytest.mark.parametrize(
    "violation",
    [
        "import json\n\n\ndef f(v):\n    return json.dumps(v)",
        "import json\n\n\ndef f(v):\n    return json.dumps(v, sort_keys=True)",
        "import json\n\n\ndef f(v):\n    return json.dumps(v, sort_keys=False, separators=(',', ':'), ensure_ascii=False)",
        "import json\n\n\ndef f(v):\n    return json.dumps(v, sort_keys=True, separators=(', ', ': '), ensure_ascii=False)",
        "import json\n\n\ndef f(v):\n    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True)",
        "import json\n\n\ndef f(v):\n    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, indent=2)",
        "import json\n\n\ndef f(v, opts):\n    return json.dumps(v, **opts)",
        "from json import dumps\n\n\ndef f(v):\n    return dumps(v)",
    ],
    ids=[
        "no-options",
        "one-option",
        "unsorted",
        "spaced",
        "escaped",
        "indented",
        "options-from-elsewhere",
        "imported-bare",
    ],
)
def test_the_scan_rejects_a_serialisation_that_is_not_the_canonical_one(
    violation: str,
) -> None:
    """Proved red: one per option, plus the two spellings that would slip past a shallower scan."""
    assert form_findings(module_from_source(violation)) != []


def test_an_annotated_exemption_covers_a_layout_meant_for_a_person() -> None:
    """The hatch exists so the first human-readable dump argues for itself instead of
    quietly widening the rule for the calls that define a `record_id`."""
    excused = (
        "import json\n\n\ndef f(v):\n"
        "    return json.dumps(v, indent=2)"
        "  # guard-exempt: I24 · a manifest a person reads · the edge · 2026-08-25"
    )

    assert form_findings(module_from_source(excused)) == []


@pytest.mark.parametrize("value", DISCRIMINATING, ids=range(len(DISCRIMINATING)))
def test_the_form_serialises_a_value_the_way_the_options_say(value: Any) -> None:
    """The half the AST cannot see: what the function returns, not how its call site is spelled.

    It compared the two axes' copies against each other and against the options until T56 merged
    them. With one definition left the comparison that means something is against the options
    themselves -- `CANONICAL` is how the scan above spells them and `CANONICAL_KWARGS` is what they
    do, and this is the only thing that says those two are the same three options.
    """
    assert canonical_json(value) == json.dumps(value, **CANONICAL_KWARGS)


@pytest.mark.parametrize(
    ("option", "other"),
    [("sort_keys", False), ("separators", (", ", ": ")), ("ensure_ascii", True)],
    ids=["sort_keys", "separators", "ensure_ascii"],
)
def test_each_option_changes_at_least_one_of_the_values(
    option: str, other: Any
) -> None:
    """The proof for the comparison above: values that agreed under any options would prove nothing."""
    flipped = {**CANONICAL_KWARGS, option: other}

    assert any(
        canonical_json(value) != json.dumps(value, **flipped)
        for value in DISCRIMINATING
    )
