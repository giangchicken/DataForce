"""The four validity checks, all provable by counting. No person decides any of them.

Each returns True when its named failure holds, so the name reads as what is wrong with
the record and `Record.invalid` is the list of names that fired.

The names are declared identifiers -- they appear in `params.yaml` and in the profile
spec's table -- but the *fields* they read are not: which turn restates the answer and
where the answer is stated both come from the source contract.

Two of the four read 0 on the current file, and that is a measurement rather than an
omission: `empty_catalog` and `label_not_in_catalog` count records the catalog format
resolves, and the 841 and 722 the profile spec quotes are what a stricter name pattern
reports about names carrying a dot, hyphen, space or tab. They stay as gates, the way
`label_assistant_mismatch` stayed at 0 after it was fixed upstream: a check that reads 0
is what tells you when it stops reading 0.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_yaml

from dataforce.profiles.tool_decision.adapter import catalog_names
from dataforce.profiles.tool_decision.answers import delta
from dataforce.profiles.tool_decision.source import SourceContract
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import Record, TextPart

__all__ = ["PARAMS", "CHECK_NAMES", "max_answer_cardinality", "validity_checks"]

PARAMS = Path("params.yaml")

# The order they are reported in, and the keys `params.yaml` declares counts against.
CHECK_NAMES = (
    "label_assistant_mismatch",
    "label_not_in_catalog",
    "empty_catalog",
    "label_cardinality_anomaly",
)


def max_answer_cardinality(*, params: Path = PARAMS) -> int:
    """The largest answer this source is declared to contain."""
    declared = (read_yaml(params) or {}).get("max_answer_cardinality")
    if not isinstance(declared, int):
        raise ConfigError(
            f"{params}: max_answer_cardinality must be declared as an integer, got "
            f"{declared!r} -- thresholds are committed, not inferred"
        )
    return declared


def _restated_answer(record: Record, role: str) -> Any:
    """The label as the restating turn states it, or None if it does not."""
    text = next(
        (
            part.text
            for part in reversed(record.content)
            if isinstance(part, TextPart) and part.role == role
        ),
        None,
    )
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def validity_checks(
    contract: SourceContract, *, params: Path = PARAMS
) -> dict[str, Callable[[Record], bool]]:
    """The four, bound to one source's vocabulary and one declared ceiling.

    The ceiling is read once here rather than once per record, so an undeclared threshold
    fails when a stage builds its checks and not on the first row of 21,172.
    """
    restating_role = contract.role(contract.label_restated_in)
    ceiling = max_answer_cardinality(params=params)

    def label_assistant_mismatch(record: Record) -> bool:
        """The two statements of the target disagree.

        The restating turn *is* the training target, so a record where it and the label
        differ would train a model on the losing side of two disagreeing sources. Was 48
        records; upstream drove it to 0 and the gate expects 0.
        """
        stated = _restated_answer(record, restating_role)
        if stated is None:
            return True
        try:
            return delta(stated, record.label) != 0.0
        except TypeError:
            return True

    def label_not_in_catalog(record: Record) -> bool:
        """The target names a tool the record never offered -- unlearnable, and it
        teaches hallucination. Never truncated to the catalog: that would be a guess
        about which of two disagreeing sources is right, applied invisibly at scale."""
        offered = set(catalog_names(record))
        return any(name not in offered for name in record.label or [])

    def empty_catalog(record: Record) -> bool:
        """The record offers no tools. A quarantine for triage, not a verdict."""
        return not catalog_names(record)

    def label_cardinality_anomaly(record: Record) -> bool:
        """More tools in the answer than this source is declared to contain."""
        return len(record.label or []) > ceiling

    return {
        "label_assistant_mismatch": label_assistant_mismatch,
        "label_not_in_catalog": label_not_in_catalog,
        "empty_catalog": empty_catalog,
        "label_cardinality_anomaly": label_cardinality_anomaly,
    }
