"""The `dataforce` command, and the only place a logging handler is configured.

Every other module calls `get_logger(__name__)` and configures nothing, so
importing dataforce as a library never installs a handler on anyone's root logger.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from dataforce import __version__


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

    requeue = sub.add_parser(
        "requeue", help="re-admit records quarantined by one validity check"
    )
    requeue.add_argument("--check", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    print(f"dataforce {args.command}: not implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
