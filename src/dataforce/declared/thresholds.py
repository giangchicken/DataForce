"""What a gate compares against, read off disk.

`shared/gates/runner.py` is the engine: it holds no number of its own, and it does
not read one either. A threshold is a committed, reviewable decision, so it lives in
`config/gates.yaml` -- and the run manifest records that file's SHA-256, which is
what makes the number attributable to a run afterwards.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_yaml

from dataforce.shared.errors import DataForceError

__all__ = ["thresholds"]


def thresholds(gate: str, *, path: Path) -> dict[str, Any]:
    """What one gate compares against, by gate name. Absent means nothing declared."""
    config = read_yaml(path) or {}
    declared = config.get(gate) or {}
    if not isinstance(declared, dict):
        raise DataForceError(
            f"{path}: gate {gate!r} must be a mapping, got {declared!r}"
        )
    return declared
