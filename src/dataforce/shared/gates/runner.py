"""The gate engine: what stops a run instead of passing bad data downstream.

92% of ML teams hit a data cascade -- an upstream data problem amplifying
through everything after it -- and the response this pipeline makes is that every
stage has a gate that fails the run. A gate is a named predicate over a stage's
inputs and outputs, with any number it compares against handed in by the caller
that read it -- `declared/thresholds.py`. This module holds the engine, no
thresholds, and no filesystem: it raises its verdict, and persisting one is what
`api/` does with it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_toolkit.logging import get_logger

from dataforce.shared.errors import DataForceError

__all__ = [
    "MAX_OFFENDING_RIDS",
    "GateFailed",
    "GateResult",
    "assert_gates",
    "conservation",
]

log = get_logger(__name__)

# Enough offending ids to find the pattern, few enough to read. A gate failing on
# every record would otherwise write the corpus into its own failure report.
MAX_OFFENDING_RIDS = 100


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict: what it asserted, and what it saw instead."""

    name: str
    assertion: str
    ok: bool
    observed: Any
    expected: Any
    offending_rids: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.name,
            "assertion": self.assertion,
            "ok": self.ok,
            "observed": self.observed,
            "expected": self.expected,
            "offending_rids": list(self.offending_rids[:MAX_OFFENDING_RIDS]),
        }


class GateFailed(DataForceError):
    """A gate did not pass, so the run stops here.

    Raised rather than returned: an uncaught exception exits non-zero, which is
    what halts the run instead of letting the next stage read an artifact nobody
    checked. Every result is attached, passing ones included, so the caller can
    record the whole verdict and not just what broke.
    """

    def __init__(self, stage: str, results: Sequence[GateResult]) -> None:
        self.stage = stage
        self.results = tuple(results)
        self.failures = tuple(result for result in results if not result.ok)
        named = ", ".join(result.name for result in self.failures)
        super().__init__(f"gate failed in stage {stage!r}: {named}")


def conservation(
    *,
    input_count: int,
    output_count: int,
    quarantined: int = 0,
    deduped_out: int = 0,
    offending_rids: Iterable[str] = (),
) -> GateResult:
    """Nothing is lost between stages. The one gate that runs on every stage.

    A record either came out, was quarantined with a reason, or was dropped by an
    explicit dedup filter. Anything else is a record that disappeared, which is
    the failure mode a count alone hides.
    """
    accounted = output_count + quarantined + deduped_out
    return GateResult(
        name="conservation",
        assertion="output + quarantined + deduped_out == input",
        ok=accounted == input_count,
        observed={
            "output": output_count,
            "quarantined": quarantined,
            "deduped_out": deduped_out,
            "accounted": accounted,
        },
        expected={"input": input_count},
        offending_rids=tuple(offending_rids),
    )


def assert_gates(stage: str, results: Sequence[GateResult]) -> None:
    """Stop the run if any gate failed. Writes nothing: that is the caller's job."""
    failures = [result for result in results if not result.ok]
    if not failures:
        log.info("stage %s: %d gates passed", stage, len(results))
        return
    log.error("stage %s: %d gates failed", stage, len(failures))
    raise GateFailed(stage, results)
