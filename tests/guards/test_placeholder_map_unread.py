"""I13 · the placeholder map is never read by a service, and never committed.

`pii_check` returns a map from placeholder to original value -- the only thing in the pipeline that
holds personal data outside a record. Two halves keep it where it belongs, and neither is about
`pii_check`: it is the *other* stages that would make it dangerous, and version control that would
make it permanent.

**Nothing reads it, structurally.** A service is handed an `Engine` and records, and never another
stage's `ServiceResult` -- the runner folds the side output up to the edge and never back down. So
the scan below is for the one shape that would break that: a `STEP ·` module reading `side_output`
off anything. `runner.py` is the fold and is `LOGIC ·`, so it is not scanned; a stage that grew a
private fold would be.

**And it is not committed.** The map goes to the privacy tier, which `.gitignore` covers by name and
with the reason written next to it. That line is what the second test reads.
"""

import ast

import pytest

from .tree import SRC, Module, module_from_source, modules_in, not_exempt

KIND = "STEP ·"
SIDE_OUTPUT = "side_output"
PRIVACY_TIER = "data/raw/"
GITIGNORE = SRC.parents[1] / ".gitignore"


def stage_modules() -> list[Module]:
    """Every module that serves one stage of the flow, by the kind its docstring declares."""
    return [
        module
        for module in modules_in()
        if (ast.get_docstring(module.tree) or "").startswith(KIND)
    ]


def side_output_findings(module: Module) -> list[str]:
    """Every place this module reads side output -- which is the edge's to read, not a stage's."""
    found = [
        (node.lineno, f"reads {SIDE_OUTPUT}: the placeholder map is the edge's")
        for node in ast.walk(module.tree)
        if isinstance(node, ast.Attribute) and node.attr == SIDE_OUTPUT
    ]
    return not_exempt(module, "I13", found)


@pytest.mark.parametrize("module", stage_modules(), ids=lambda m: m.name)
def test_no_stage_reads_another_stage_s_side_output(module: Module) -> None:
    """I13's first half, over every `STEP ·` module in the tree."""
    assert side_output_findings(module) == []


def test_the_scan_found_the_stages_it_is_supposed_to_scan() -> None:
    """Guards the discovery: a scan over no modules would pass whatever it was pointed at."""
    named = {module.name for module in stage_modules()}

    assert "dataforce.pipeline.load_data" in named
    assert "dataforce.pipeline.data_quality.pii_check" in named


def test_the_scan_rejects_a_stage_that_reads_one() -> None:
    """Proved red: the shape the rule forbids -- a stage folding what the edge is supposed to persist."""
    violation = (
        '"""STEP · pii_check · two-layer detection."""\n'
        "def pii_check(engine, records, earlier):\n"
        "    return earlier.side_output\n"
    )

    assert side_output_findings(module_from_source(violation)) != []


def test_writing_side_output_is_not_reading_it() -> None:
    """The rule is against a second reader. `pii_check` returning one is the whole design."""
    permitted = (
        '"""STEP · pii_check · two-layer detection."""\n'
        "def pii_check(engine, records):\n"
        "    return ServiceResult(records=(), side_output={'pii_check': {}})\n"
    )

    assert side_output_findings(module_from_source(permitted)) == []


def test_the_tier_the_map_is_written_to_is_not_committed() -> None:
    """I13's second half: the privacy tier is ignored by name, with its reason beside it."""
    ignored = GITIGNORE.read_text(encoding="utf-8")

    assert f"\n{PRIVACY_TIER}\n" in ignored
    assert "placeholder map" in ignored
