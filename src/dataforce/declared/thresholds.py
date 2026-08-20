"""Every number the pipeline compares against, read off disk.

`shared/gates/runner.py` is the engine: it holds no number of its own, and it does
not read one either. A threshold is a committed, reviewable decision, so it lives in
`config/gates.yaml` or `params.yaml` -- and the run manifest records each of those
files' SHA-256, which is what makes the number attributable to a run afterwards.

Two files because they answer to different questions: `config/gates.yaml` is per
gate, and `params.yaml` holds what one source is declared to contain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_yaml

from dataforce.shared.errors import ConfigError, DataForceError

__all__ = ["max_answer_cardinality", "thresholds"]


def thresholds(gate: str, *, path: Path) -> dict[str, Any]:
    """What one gate compares against, by gate name. Absent means nothing declared."""
    config = read_yaml(path) or {}
    declared = config.get(gate) or {}
    if not isinstance(declared, dict):
        raise DataForceError(
            f"{path}: gate {gate!r} must be a mapping, got {declared!r}"
        )
    return declared


def max_answer_cardinality(*, params: Path) -> int:
    """The largest answer this source is declared to contain."""
    declared = (read_yaml(params) or {}).get("max_answer_cardinality")
    if not isinstance(declared, int):
        raise ConfigError(
            f"{params}: max_answer_cardinality must be declared as an integer, got "
            f"{declared!r} -- thresholds are committed, not inferred"
        )
    return declared
