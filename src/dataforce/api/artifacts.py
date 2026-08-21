"""The only place an artifact is read or written, and the run's own record of it.

The engine raises and computes; everything that touches the filesystem on the way in
or out is here. That is what makes the layering checkable: `test_layering.py` scans
the engine for a file read, and this module is where each one it used to find went.

`run_manifest` is what replaces `dvc repro`'s declared dependencies. DVC no longer
orchestrates, so nothing outside this codebase records what a run consumed -- the
manifest does, by naming every policy file's SHA-256, both axes' `name@version`, and
the digest of every artifact written. Two runs agreeing is two manifests agreeing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import iter_json_array_file, read_yaml, write_json

from dataforce.api.engine import Engine
from dataforce.core.errors import ConfigError
from dataforce.core.gates import GateFailed, GateResult, assert_gates
from dataforce.profiles.tool_decision import measure_corpus

__all__ = [
    "GATE_FAILED_FILENAME",
    "METRICS_FILENAME",
    "RUN_MANIFEST_FILENAME",
    "file_digest",
    "profile_corpus",
    "record_gates",
    "require_upstream_ok",
    "run_manifest",
]

GATE_FAILED_FILENAME = "GATE_FAILED.json"
METRICS_FILENAME = "metrics.json"
RUN_MANIFEST_FILENAME = "run.json"

# Read in blocks, so a 126 MiB source never becomes a 126 MiB string. `compute_hash`
# hashes text already in memory, which is the one thing this must not do.
_DIGEST_BLOCK = 1 << 20

# Which profile knows how to measure its own corpus. A profile is not required to:
# the validity counts and the group sizes are generic, everything else a
# measurement holds is what one corpus specifically contains.
_MEASURERS: dict[str, Callable[..., dict[str, Any]]] = {
    "tool_decision": measure_corpus.corpus_measurements,
}


def file_digest(path: Path) -> str:
    """One file's SHA-256, without reading the file into memory."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256", _bufsize=_DIGEST_BLOCK).hexdigest()


def run_manifest(engine: Engine, *, artifacts: Mapping[str, Path]) -> dict[str, Any]:
    """What one run read and what it wrote, as digests.

    Diffing two of these is the reproducibility check: same policy, same producer,
    same artifact digests means the run reproduced. It is what invariant 14 asserts
    now that no `dvc.lock` records it.
    """
    return {
        "producer": engine.producer,
        "policy": {str(path): file_digest(path) for path in engine.policy},
        "artifacts": {
            name: file_digest(path) for name, path in sorted(artifacts.items())
        },
    }


def require_upstream_ok(*stage_dirs: Path) -> None:
    """Refuse to read an artifact whose own stage failed its gate."""
    for stage_dir in stage_dirs:
        marker = stage_dir / GATE_FAILED_FILENAME
        if marker.exists():
            raise GateFailed(
                str(stage_dir),
                [
                    GateResult(
                        name="upstream_ok",
                        assertion=f"{GATE_FAILED_FILENAME} is absent",
                        ok=False,
                        observed=f"{GATE_FAILED_FILENAME} is present",
                        expected="the upstream stage passed its gates",
                    )
                ],
            )


def record_gates(stage: str, results: Sequence[GateResult], *, out_dir: Path) -> None:
    """Every gate's verdict on disk, and the run stopped if any of them failed.

    The engine raises and writes nothing, so the writing is here -- which is also
    what lets an in-process caller take the exception and have no files appear.
    """
    write_json(
        out_dir / METRICS_FILENAME,
        {"stage": stage, "gates": [result.as_dict() for result in results]},
    )
    marker = out_dir / GATE_FAILED_FILENAME
    try:
        assert_gates(stage, results)
    except GateFailed as failed:
        first = failed.failures[0].as_dict()
        write_json(
            marker,
            {
                "stage": stage,
                "assertion": first["assertion"],
                "observed": first["observed"],
                "expected": first["expected"],
                "offending_rids": first["offending_rids"],
                "failures": [result.as_dict() for result in failed.failures],
            },
        )
        raise
    marker.unlink(missing_ok=True)  # a previous run's failure, now fixed


def profile_corpus(
    engine: Engine, *, accept: bool = False, baseline: Path, params: Path
) -> tuple[dict[str, Any], list[str]]:
    """Measure the declared source, and write the baseline only if nothing moved.

    Returns the measurement and the drift. A drift is not written over: the point of
    the file is to be the last agreed measurement, and agreeing to a new one is a
    commit, which is what `accept` stands for.

    The source is streamed into the measurer as an iterator, so the 126 MiB file is
    never held whole and the engine never learns what a path is.
    """
    measurer = _MEASURERS.get(engine.profile.name)
    if measurer is None:
        raise ConfigError(
            f"{engine.profile.name} has no corpus profiler; "
            f"the ones that do: {sorted(_MEASURERS)}"
        )

    source = Path(read_yaml(params)["source"]["path"])
    measured = measurer(
        iter_json_array_file(source),
        engine.modality,
        engine.profile,
        digest=file_digest(source),
        size=source.stat().st_size,
    )
    if not baseline.exists() or accept:
        write_json(baseline, measured)
        return measured, []
    moved = measure_corpus.moved_measurements(read_yaml(baseline), measured)
    if not moved:
        write_json(baseline, measured)
    return measured, moved
