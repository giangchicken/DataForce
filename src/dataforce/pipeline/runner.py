"""LOGIC · run_phase -- a phase's stages folded over records, in the table's order.

The order of a phase's stages is engine knowledge. No router and no CLI subcommand names a stage
sequence; both fold through here (Requirement 48, I17).

**A stage is found through the table, not through a list of imports.** A dispatch mapping written
here would name all fifteen stages a second time, and the second copy is the one that goes stale
when a row moves -- so ``flow.py`` stays the only place the flow is written down, and the module a
row lives in is derived from the layout rule ``spec.md`` § *Package layout* states: a phase with one
stage is a module, a phase with several is a directory. ``tests/guards/test_flow_table.py`` reads
the derivation from here, so the rule is stated once and the guard proves the runner will find
every built stage.

**A stage module that has no function of its own name raises ``AttributeError``**, and that is left
alone: Python's own message names the module and the missing attribute, which is exactly the fault.
Every stage is a docstring until Phase 4, so this is the state the tree is in right now.
"""

from collections.abc import Callable, Iterable
from importlib import import_module
from typing import Any

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.record import Record

from .flow import DECLARED_ONLY, FROM_SOURCE, PHASES, STAGES

# The one signature every service has (Requirement 46), named here because the runner is the only
# module that has to say it out loud -- a stage just is a function of this shape.
type Service = Callable[[Engine, Iterable[Record]], ServiceResult]


def stage_module_name(phase: str, stage: str) -> str:
    """The dotted module that stage lives in, by the rule § *Package layout* states.

    A phase with one stage is a module (`pipeline/load_data.py`); a phase with several is a
    directory (`pipeline/data_quality/pii_check.py`). Deriving it beats declaring it: a declared
    path would be a third statement of the flow, after the table and the tree.

    Two strings rather than a `Stage`, because the only other caller is the guard that compares the
    tree to the document, and it has a row of the document rather than a row of the table.
    """
    siblings = [row for row in STAGES if row.phase == phase]
    tail = stage if len(siblings) == 1 else f"{phase}.{stage}"
    return f"dataforce.pipeline.{tail}"


def run_phase(engine: Engine, phase: str, records: Iterable[Record]) -> ServiceResult:
    """Every stage of one phase, run over the records in the order `flow.py` declares.

    Each stage's records are the next stage's, and each stage's side output is kept under its own
    name. A record a stage skips comes back untouched, because a skip is a value on the record and
    never a shorter list (Requirement 41).
    """
    if phase not in PHASES:
        raise ConfigError(f"unknown phase {phase!r}; the flow has {', '.join(PHASES)}")
    if phase in DECLARED_ONLY:
        raise ConfigError(f"{phase!r} is declared in the flow and has no module yet")
    if phase in FROM_SOURCE:
        raise ConfigError(
            f"{phase!r} reads source items rather than records, so there is nothing to "
            "fold; call it directly with the items and the run's own stamp"
        )

    running = tuple(records)
    side_output: dict[str, Any] = {}
    for stage in (row for row in STAGES if row.phase == phase):
        module = import_module(stage_module_name(stage.phase, stage.stage))
        service: Service = getattr(module, stage.stage)
        result = service(engine, running)
        running = result.records
        side_output.update(result.side_output)
    return ServiceResult(records=running, side_output=side_output)
