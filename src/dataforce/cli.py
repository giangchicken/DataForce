"""The `dataforce` command, and the only place a logging handler is configured.

Every other module calls `get_logger(__name__)` and configures nothing, so
importing dataforce as a library never installs a handler on anyone's root logger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import iter_json_array_file, read_yaml, write_json

from dataforce import __version__
from dataforce.declared.manifest import read_manifest
from dataforce.declared.prompts import read_prompt
from dataforce.declared.thresholds import max_answer_cardinality
from dataforce.modalities.base import Modality
from dataforce.modalities.text import MANIFEST_NAME as TEXT_MANIFEST
from dataforce.modalities.text import TextModality
from dataforce.profiles.tool_decision import MANIFEST_NAME as TOOL_DECISION_MANIFEST
from dataforce.profiles.tool_decision import ToolDecisionProfile, measure_corpus
from dataforce.shared.gates.runner import (
    GateFailed,
    GateResult,
    assert_gates,
)
from dataforce.shared.registry import Registry

# Where the committed policy is, relative to the directory the command is run from.
# The engine never sees these: it is handed what they parse to.
CONFIG = Path("config")
PARAMS = Path("params.yaml")
BASELINE = Path("metrics/corpus_profile.json")

# Every file the engine is not allowed to open, and this is the only module that does
# until `api/` arrives. Read in blocks, so a 126 MiB source never becomes a 126 MiB
# string: `compute_hash` hashes text already in memory, which is what this must not do.
_DIGEST_BLOCK = 1 << 20

GATE_FAILED_FILENAME = "GATE_FAILED.json"
METRICS_FILENAME = "metrics.json"

# Which profile knows how to measure its own corpus. A profile is not required to:
# the four validity counts and the group sizes are generic, everything else here is
# what this corpus specifically contains. The reading around it is this module's.
_MEASURERS: dict[str, Callable[..., dict[str, Any]]] = {
    "tool_decision": measure_corpus.corpus_measurements,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataforce",
        description="Turn a raw corpus into a versioned, documented dataset.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="log at DEBUG instead of INFO",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the pipeline for one modality and profile")
    run.add_argument("--modality", required=True)
    run.add_argument("--profile", required=True)

    profile = sub.add_parser("profile", help="measure a corpus and report drift")
    profile.add_argument("--profile", required=True)
    profile.add_argument(
        "--accept",
        action="store_true",
        help="write the measurement as the new baseline even where counts moved",
    )

    requeue = sub.add_parser(
        "requeue", help="re-admit records quarantined by one validity check"
    )
    requeue.add_argument("--check", required=True)

    return parser


def text_modality(*, config_root: Path = CONFIG) -> TextModality:
    """The `text` modality, from the manifest that declares what it is."""
    return TextModality(read_manifest("modalities", TEXT_MANIFEST, root=config_root))


def tool_decision_profile(
    *, config_root: Path = CONFIG, params: Path = PARAMS
) -> ToolDecisionProfile:
    """The `tool_decision` profile, with the question template and ceiling it declares."""
    declared = read_manifest("profiles", TOOL_DECISION_MANIFEST, root=config_root)
    return ToolDecisionProfile(
        declared,
        question_template=read_prompt(
            declared.require("prompts")["question"], root=config_root / "prompts"
        ),
        ceiling=max_answer_cardinality(params=params),
    )


def _register_implementations(
    *, config_root: Path = CONFIG, params: Path = PARAMS
) -> Registry:
    """The composition root: the one place a concrete modality or profile is named.

    No module under `pipeline/` or `shared/` may import one, and neither axis is
    built at import time, so this is where both arrive -- and the only place that
    turns a committed file into an object. Registration resolves a name and checks
    nothing else.
    """
    registry = Registry()
    registry.register_modality(text_modality(config_root=config_root))
    registry.register_profile(
        tool_decision_profile(config_root=config_root, params=params)
    )
    return registry


def source_digest(path: Path) -> str:
    """The file's SHA-256, without reading the file into memory."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256", _bufsize=_DIGEST_BLOCK).hexdigest()


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

    The engine raises and writes nothing, so writing the verdict is here. `api/` takes
    this over, along with `require_upstream_ok` and `source_digest` above.
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
    modality: Modality,
    profile: ToolDecisionProfile,
    *,
    measurer: Callable[..., dict[str, Any]] = measure_corpus.corpus_measurements,
    accept: bool = False,
    baseline: Path = BASELINE,
    params: Path = PARAMS,
) -> tuple[dict[str, Any], list[str]]:
    """Measure the declared source, and write the baseline only if nothing moved.

    Returns the measurement and the drift. A drift is not written over: the point of
    the file is to be the last agreed measurement, and agreeing to a new one is a
    commit, which is what `accept` stands for.

    The source is streamed into the measurer as an iterator, so the 126 MiB file is
    never held whole and the engine never learns what a path is.
    """
    declared = read_yaml(params)["source"]
    source = Path(declared["path"])
    measured = measurer(
        iter_json_array_file(source),
        modality,
        profile,
        digest=source_digest(source),
        size=source.stat().st_size,
    )
    if not baseline.exists() or accept:
        write_json(baseline, measured)
        return measured, []
    moved = measure_corpus.moved_measurements(read_yaml(baseline), measured)
    if not moved:
        write_json(baseline, measured)
    return measured, moved


def _profile(args: argparse.Namespace) -> int:
    registry = _register_implementations()
    profile = registry.profile(args.profile)
    measurer = _MEASURERS.get(profile.name)
    if measurer is None:
        print(
            f"{profile.name} has no corpus profiler; the ones that do: "
            f"{sorted(_MEASURERS)}",
            file=sys.stderr,
        )
        return 2

    measured, moved = profile_corpus(
        registry.modality(profile.modality),
        profile,  # type: ignore[arg-type]
        measurer=measurer,
        accept=args.accept,
    )
    print(json.dumps({**measured["source"], "records": measured["records"]}, indent=2))
    if not moved:
        return 0
    print(
        f"{len(moved)} measurement(s) moved since the committed profile:",
        *moved,
        sep="\n  ",
        file=sys.stderr,
    )
    print(
        "\nthe source file changed. re-run with --accept to declare the new counts.",
        file=sys.stderr,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.command == "profile":
        return _profile(args)
    print(f"dataforce {args.command}: not implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
