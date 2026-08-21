"""What one `dataforce run` does: for each named stage, its inputs, its gates, its files.

`artifacts.py` holds the primitives every stage needs -- a file's digest, a run manifest,
a gate's verdict on disk. This module holds the sequence: which stages are built, which
phase directory each writes into, and the wiring that turns a pure stage function into
files. Two jobs, two modules, so each stays nameable as one; the fourteen stages still to
come arrive along that same seam.

There is no stage cache. Naming stages is how a person re-does one without re-doing the
corpus -- shared decision 14 -- so `dataforce run load` twice reads the source twice and
is expected to. What it must *not* do is produce a different artifact the second time,
which is why nothing here reads a clock.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from agent_toolkit.file_utils import (
    iter_json_array_file,
    read_yaml,
    write_json,
    write_jsonlines,
)
from agent_toolkit.logging import get_logger

from dataforce.api.artifacts import (
    RUN_MANIFEST_FILENAME,
    file_digest,
    record_gates,
    run_manifest,
)
from dataforce.api.engine import Engine
from dataforce.core.errors import ConfigError
from dataforce.core.flow import PHASES
from dataforce.core.gates import conservation
from dataforce.core.record import Record
from dataforce.pipeline.data_quality import load

__all__ = ["STAGES", "Stage", "interim_directory", "stage_outputs"]

log = get_logger(__name__)

# Where a phase's artifacts go, numbered by its place in the flow so that a listing of
# `interim/` reads in stage order. The name comes from `core/flow.py` rather than being
# spelled here, which is the whole reason that module exists.
INTERIM = "interim"
_PHASE_ORDER = {phase.name: index for index, phase in enumerate(PHASES, start=1)}

# The tally key for source elements read, kept apart from the two `parse_status` values
# the same counter holds, because comparing them is the conservation gate.
_ITEMS = "items"

# Stage 0, by the name the spec's stage table gives it and the CLI takes.
_LOAD = "load"

# Whatever is being counted on its way past: source elements, then records.
T = TypeVar("T")


@dataclass(frozen=True)
class Stage:
    """One built stage: whose directory it writes into, and what it writes there."""

    phase: str
    # Typed by what it returns rather than by what it takes: the fifteen do not share a
    # signature -- `jury` needs a panel, `publish` a client -- so the table pins the
    # return shape every caller here relies on and each call site is checked on its own.
    artifacts: Callable[..., dict[str, Path]]


def interim_directory(phase: str, *, data_root: Path) -> Path:
    """Where one phase's interim artifacts go: `interim/<n>_<phase>`."""
    return data_root / INTERIM / f"{_PHASE_ORDER[phase]}_{phase}"


def _tallied(rows: Iterable[T], tally: Counter[str], key: str) -> Iterator[T]:
    """Every row, counted on the way past.

    The input and the output of a stage are counted at two independent points, so
    `conservation` is a claim about the loop between them rather than a restatement of
    one number.
    """
    for row in rows:
        tally[key] += 1
        yield row


def _record_rows(
    records: Iterable[Record], tally: Counter[str]
) -> Iterator[dict[str, Any]]:
    """Every record as the JSON row it is written as, counted by how it was read."""
    for record in records:
        tally[record.parse_status] += 1
        yield record.model_dump(mode="json")


def _source_written_at(source: Path) -> str:
    """The source file's own last-modified time, UTC, to the second.

    This is stage 0's `ingested_at`, and it is deliberately not the wall clock --
    `pipeline/data_quality/load.py` states the requirement it deviates from and why. A
    time derived from the input is a time two runs over one input agree about.
    """
    written = datetime.fromtimestamp(source.stat().st_mtime, tz=UTC)
    return written.isoformat(timespec="seconds").replace("+00:00", "Z")


def _declared_source(params: Path) -> tuple[Path, str]:
    """The file a run reads and the digest it is pinned at, both from the policy."""
    declared = (read_yaml(params) or {}).get("source") or {}
    try:
        return Path(declared["path"]), str(declared["sha256"])
    except KeyError as missing:
        raise ConfigError(
            f"{params}: source.{missing} is not declared; a run reads the file the "
            "policy names, at the digest the policy pins"
        ) from None


def _loaded_artifact(engine: Engine, *, params: Path, out_dir: Path) -> dict[str, Path]:
    """Stage 0: the declared source as `loaded.jsonl`, behind its two gates.

    The identity gate is asserted on its own before the stream opens, so a source that
    is not the declared one costs a digest rather than 21,172 parses. The conservation
    gate can only be asserted afterwards, which is the honest order: it is a claim about
    what the loop did.
    """
    source, declared = _declared_source(params)
    digest = file_digest(source)
    identity = load.source_identity(digest=digest, declared=declared)
    if not identity.ok:
        # Writes the marker and re-raises `GateFailed`, so there is deliberately nothing
        # after this line: the wrong file is not parsed and no artifact is written.
        record_gates(_LOAD, [identity], out_dir=out_dir)

    tally: Counter[str] = Counter()
    written = out_dir / "loaded.jsonl"
    write_jsonlines(
        written,
        _record_rows(
            load.loaded_records(
                _tallied(iter_json_array_file(source), tally, _ITEMS),
                engine.modality,
                engine.profile,
                digest=digest,
                ingested_at=_source_written_at(source),
            ),
            tally,
        ),
    )
    log.info("stage %s read %s", _LOAD, dict(tally))
    record_gates(
        _LOAD,
        [
            identity,
            conservation(
                input_count=tally[_ITEMS],
                output_count=tally["ok"] + tally["unparsed"],
            ),
        ],
        out_dir=out_dir,
    )
    return {"loaded": written}


# The stages that are built, in flow order -- which is the order they run in whatever
# order they were named, because a stage reads what the one before it wrote. The spec's
# stage table declares fifteen; a name it holds and this does not is not yet code, and
# saying so is better than a missing-file error.
STAGES: dict[str, Stage] = {
    _LOAD: Stage(phase="data_quality", artifacts=_loaded_artifact),
}


def stage_outputs(
    engine: Engine,
    stages: Sequence[str] = (),
    *,
    params: Path,
    data_root: Path,
) -> dict[str, Path]:
    """Run the named stages, or every built stage, and say what each one wrote.

    Every artifact by its name in `core/artifacts/`, plus `run` -- the run manifest,
    which is what records the policy each stage read now that no `dvc.lock` does.
    """
    requested = set(stages) or set(STAGES)
    unknown = sorted(requested - set(STAGES))
    if unknown:
        raise ConfigError(f"no stage is built for {unknown}; these are: {list(STAGES)}")

    written: dict[str, Path] = {}
    for stage, wiring in STAGES.items():
        if stage not in requested:
            continue
        written.update(
            wiring.artifacts(
                engine,
                params=params,
                out_dir=interim_directory(wiring.phase, data_root=data_root),
            )
        )

    manifest = data_root / RUN_MANIFEST_FILENAME
    write_json(manifest, run_manifest(engine, artifacts=written))
    return {**written, "run": manifest}
