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
    inputs: Sequence[Mapping[str, Any]],
    labels: Sequence[Sequence[Any] | None],
) -> DuplicateGroups:
    """Every input more than one row carries, split by whether all of its labels agree.

    The input is hashed because its digest is what comes back; the label is only ever compared,
    so its canonical text is enough. `None` and `()` are one reading -- both say no call was
    needed -- so two rows agreeing that way are redundancy rather than a disagreement to
    re-review, and a group holding two readings anywhere in it is a whole group to inspect.

    Hashed in Python rather than grouped in SQL: two JSON columns are not comparable for equality
    across dialects. A stored digest column is the change to make when this stops being instant.
    """
    seen_labels: dict[str, list[str]] = {}
    for one_input, label in zip(inputs, labels, strict=True):
        digest = compute_hash(canonical_json(one_input))
        seen_labels.setdefault(digest, []).append(canonical_json(label or ()))
    repeated = {
        digest: set(readings)
        for digest, readings in seen_labels.items()
        if len(readings) > 1
    }
    return DuplicateGroups(
        duplicate_content_same_label=tuple(
            digest for digest, readings in repeated.items() if len(readings) == 1
        ),
        duplicate_content_diff_label=tuple(
            digest for digest, readings in repeated.items() if len(readings) > 1
        ),
    )
