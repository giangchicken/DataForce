"""I17 · a phase's stage order exists once, in `pipeline/flow.py`.

`POST /data-quality` runs three services in the order the flow declares, folded by
`pipeline/runner.py`. A router or a CLI subcommand that calls them itself has written that order
down a second time, and the second copy is the one that is wrong after a stage is inserted
(Requirement 48).

**A function body, not a module.** A `data_quality` router legitimately *mentions* three stages --
it serves `/data-quality/label-check`, `/pii-check` and `/duplicate-check`, one handler each -- and
a rule counting mentions would forbid the routes the spec requires. What is an order is two stages
called from one function.

The other half of I17, that a phase endpoint reaches `run_phase`, arrives with the routers: there
is no handler yet to assert it of, and a rule that passes because there is nothing to check is a
rule nobody has tested (AGENTS.md §8).
"""

import ast

import pytest

from dataforce.pipeline.flow import STAGES

from .tree import (
    SRC,
    Module,
    called_name,
    module_at,
    module_from_source,
    modules_in,
    not_exempt,
)

STAGE_NAMES = frozenset(stage.stage for stage in STAGES)


def stage_order_findings(module: Module) -> list[str]:
    """Every function in this module that calls more than one stage, and which ones."""
    found = []
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        reached = (
            called_name(inner).split(".")[-1]
            for inner in ast.walk(node)
            if isinstance(inner, ast.Call)
        )
        called = sorted({name for name in reached if name in STAGE_NAMES})
        if len(called) > 1:
            found.append(
                (node.lineno, f"{node.name}() calls {', '.join(called)} itself")
            )
    return not_exempt(module, "I17", found)


def order_writing_modules() -> list[Module]:
    """The two shells that would write an order down twice: the routers, and the CLI."""
    return [*modules_in("edge/routers"), module_at(SRC / "edge" / "cli.py")]


def test_the_scan_has_the_two_places_to_look() -> None:
    """Guards the selection: I17 is about the edge, and an empty list would find nothing."""
    names = {module.name for module in order_writing_modules()}

    assert "dataforce.edge.cli" in names
    assert "dataforce.edge.routers.data_quality" in names


@pytest.mark.parametrize("module", order_writing_modules(), ids=lambda m: m.name)
def test_no_edge_module_folds_a_phase_itself(module: Module) -> None:
    """I17, over every router module and the CLI."""
    assert stage_order_findings(module) == []


def test_the_scan_rejects_a_handler_that_runs_a_phase_by_hand() -> None:
    """§39: the thing this is here to stop."""
    by_hand = (
        "def data_quality(engine, records):\n"
        "    records = label_check(engine, records).records\n"
        "    records = pii_check(engine, records).records\n"
        "    return duplicate_check(engine, records)"
    )

    assert stage_order_findings(module_from_source(by_hand)) != []


def test_the_scan_rejects_two_stages_however_they_are_reached() -> None:
    """§39: through a module attribute, which is the same order spelled differently."""
    qualified = (
        "def data_quality(engine, records):\n"
        "    out = label_check.label_check(engine, records)\n"
        "    return pii_check.pii_check(engine, out.records)"
    )

    assert stage_order_findings(module_from_source(qualified)) != []


def test_the_scan_permits_one_stage_per_handler() -> None:
    """The sub-endpoints. Three stages in one module is the shape the routes require."""
    routed = (
        "def label_check_route(engine, records):\n"
        "    return label_check(engine, records)\n"
        "\n"
        "def pii_check_route(engine, records):\n"
        "    return pii_check(engine, records)\n"
        "\n"
        "def duplicate_check_route(engine, records):\n"
        "    return duplicate_check(engine, records)"
    )

    assert stage_order_findings(module_from_source(routed)) == []


def test_the_scan_permits_a_phase_folded_through_the_runner() -> None:
    """The main endpoint, done the way Requirement 48 says: the table supplies the order."""
    folded = "def data_quality(engine, records):\n    return run_phase('data_quality', engine, records)"

    assert stage_order_findings(module_from_source(folded)) == []


def test_the_scan_permits_a_route_path_that_merely_spells_a_stage() -> None:
    """A URL is not a call. `/data-quality/pii-check` names a stage and orders nothing."""
    declared = (
        "def register(router):\n"
        "    router.post('/data-quality/label-check')\n"
        "    router.post('/data-quality/pii-check')\n"
        "    router.post('/data-quality/duplicate-check')"
    )

    assert stage_order_findings(module_from_source(declared)) == []
