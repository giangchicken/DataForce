"""logic · the same input twice, over a whole corpus."""

import json
from collections.abc import Mapping, Sequence
from functools import partial
from typing import Any

from agent_toolkit.string_utils import compute_hash

from .schema import DuplicateGroups

# One key ordering and one spelling, so two writers of the same content write the same string.
canonical_json = partial(
    json.dumps, sort_keys=True, ensure_ascii=False, separators=(",", ":")
)


def calculate_duplicates(
    keys: Sequence[str],
    inputs: Sequence[Mapping[str, Any]],
    labels: Sequence[Sequence[Any] | None],
) -> DuplicateGroups:

    grouped: dict[str, tuple[list[str], set[str]]] = {}
    for key, input, label in zip(keys, inputs, labels, strict=True):
        digest = compute_hash(canonical_json(input))
        rows, readings = grouped.setdefault(digest, ([], set()))
        rows.append(key)
        readings.add(canonical_json(label or ()))
    repeated = [
        (tuple(rows), readings) for rows, readings in grouped.values() if len(rows) > 1
    ]
    return DuplicateGroups(
        duplicate_content_same_label=tuple(
            rows for rows, readings in repeated if len(readings) == 1
        ),
        duplicate_content_diff_label=tuple(
            rows for rows, readings in repeated if len(readings) > 1
        ),
    )
