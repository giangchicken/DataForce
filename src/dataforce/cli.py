"""The `dataforce` command, and the only place a logging handler is configured.

Every other module calls `get_logger(__name__)` and configures nothing, so
importing dataforce as a library never installs a handler on anyone's root logger.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from dataforce import __version__
from dataforce.declared.manifest import read_manifest
from dataforce.declared.prompts import read_prompt
from dataforce.modalities.text import MANIFEST_NAME as TEXT_MANIFEST
from dataforce.modalities.text import TextModality
from dataforce.profiles.tool_decision import MANIFEST_NAME as TOOL_DECISION_MANIFEST
from dataforce.profiles.tool_decision import ToolDecisionProfile
from dataforce.profiles.tool_decision.measure_corpus import profile_corpus
from dataforce.shared.registry import Registry

# Where the committed policy is, relative to the directory the command is run from.
# The engine never sees these: it is handed what they parse to.
CONFIG = Path("config")

# Which profile knows how to measure its own corpus. A profile is not required to:
# the four validity counts and the group sizes are generic, everything else here is
# what this corpus specifically contains.
_PROFILERS: dict[str, Callable[..., tuple[dict[str, Any], list[str]]]] = {
    "tool_decision": profile_corpus,
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


def tool_decision_profile(*, config_root: Path = CONFIG) -> ToolDecisionProfile:
    """The `tool_decision` profile, with the question template its manifest names."""
    declared = read_manifest("profiles", TOOL_DECISION_MANIFEST, root=config_root)
    return ToolDecisionProfile(
        declared,
        question_template=read_prompt(
            declared.require("prompts")["question"], root=config_root / "prompts"
        ),
    )


def _register_implementations(*, config_root: Path = CONFIG) -> Registry:
    """The composition root: the one place a concrete modality or profile is named.

    No module under `pipeline/` or `shared/` may import one, and neither axis is
    built at import time, so this is where both arrive -- and the only place that
    turns a committed file into an object. Registration resolves a name and checks
    nothing else.
    """
    registry = Registry()
    registry.register_modality(text_modality(config_root=config_root))
    registry.register_profile(tool_decision_profile(config_root=config_root))
    return registry


def _profile(args: argparse.Namespace) -> int:
    registry = _register_implementations()
    profile = registry.profile(args.profile)
    measurer = _PROFILERS.get(profile.name)
    if measurer is None:
        print(
            f"{profile.name} has no corpus profiler; the ones that do: "
            f"{sorted(_PROFILERS)}",
            file=sys.stderr,
        )
        return 2

    measured, moved = measurer(
        registry.modality(profile.modality), profile, accept=args.accept
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
