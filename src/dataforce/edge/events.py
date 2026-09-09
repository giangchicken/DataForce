"""adapter · what the domain says happened, as one JSON object per line on stdout (`H-6`).

The domain logs a record; this turns it into an event. The message names the event and whatever
`extra=` carried are its fields, so a step says *what happened* and nothing about where it goes.
Never a file, and never the console format `agent_toolkit`'s own logger writes to stderr.
"""

import json
import logging
import sys

TREE = "dataforce"

# What a LogRecord always carries. Anything else on it came from `extra=` and is the event's own.
BUILT_IN = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonLines(logging.Handler):
    """One event per line. `sys.stdout` is read at emit, so a captured stream is the one used."""

    def emit(self, record: logging.LogRecord) -> None:
        event = {"event": record.getMessage()}
        event.update(
            {
                name: value
                for name, value in record.__dict__.items()
                if name not in BUILT_IN
            }
        )
        print(
            json.dumps(event, ensure_ascii=False, default=str),
            file=sys.stdout,
            flush=True,
        )


def structured_events(level: int = logging.INFO) -> logging.Logger:
    """Install one `JsonLines` on the `dataforce` tree, replacing one already there."""
    logger = logging.getLogger(TREE)
    for installed in [one for one in logger.handlers if isinstance(one, JsonLines)]:
        logger.removeHandler(installed)
    logger.addHandler(JsonLines())
    logger.setLevel(level)
    logger.propagate = False
    return logger
