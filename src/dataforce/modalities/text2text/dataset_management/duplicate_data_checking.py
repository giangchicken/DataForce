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


def duplicate_groups(
    keys: Sequence[str],
    inputs: Sequence[Mapping[str, Any]],
    labels: Sequence[Sequence[Any] | None],
) -> DuplicateGroups:
    """Every input more than one row carries, as row keys, split by whether all labels agree.

    Keys rather than digests: `duplicate_content_diff_label` is a queue somebody opens, and a
    digest of the input opens nothing. The digest stays as what groups the rows and is not part
    of the answer.

    The input is hashed because it is what rows are grouped by; the label is only ever compared,
    so its canonical text is enough. `None` and `()` are one reading -- both say no call was
    needed -- so two rows agreeing that way are redundancy rather than a disagreement to
    re-review, and a group holding two readings anywhere in it is a whole group to inspect.

    Hashed in Python rather than grouped in SQL: two JSON columns are not comparable for equality
    across dialects. A stored digest column is the change to make when this stops being instant.
    """
    grouped: dict[str, tuple[list[str], set[str]]] = {}
    for key, one_input, label in zip(keys, inputs, labels, strict=True):
        digest = compute_hash(canonical_json(one_input))
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
