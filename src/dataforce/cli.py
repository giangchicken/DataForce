"""The `dataforce` command, and the only place a logging handler is configured.

Argument parsing, logging setup and exit codes. Nothing else: every behaviour it
invokes is `api/`'s, so an in-process caller and this command run the same code
rather than two implementations kept in step by hand.

Every other module calls `get_logger(__name__)` and configures nothing, so
importing dataforce as a library never installs a handler on anyone's root logger.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from dataforce import __version__, api
from dataforce.core.errors import DataForceError

# Where the committed policy is, relative to the directory the command is run from.
# An in-process caller passes its own; only a command line has a working directory
# it can reasonably assume.
CONFIG = Path("config")
PARAMS = Path("params.yaml")
BASELINE = Path("metrics/corpus_profile.json")


def _argument_parser() -> argparse.ArgumentParser:
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
    run.add_argument(
        "stages",
        nargs="*",
        help="the stages to run, in order; all of them when none is named",
    )

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


def _profile_command(args: argparse.Namespace) -> int:
    engine = api.open_engine(profile=args.profile, config_root=CONFIG, params=PARAMS)
    measured, moved = api.profile_corpus(
        engine, accept=args.accept, baseline=BASELINE, params=PARAMS
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
    args = _argument_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        if args.command == "profile":
            return _profile_command(args)
    except DataForceError as failed:
        print(failed, file=sys.stderr)
        return 2
    print(f"dataforce {args.command}: not implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
