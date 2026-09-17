"""logic · the arithmetic over what the store counted, and the cells SQL cannot answer for.

**It may not open a session.** `services/` is `logic`, the profile's `schema.py` is an `adapter`,
and `H-8` sends that import the other way -- so every function here is handed rows and answers a
figure. The router is where the reading and the arithmetic meet.

The grid is a **joint distribution of two variables** and nothing narrower. It is handed the pairs
one `GROUP BY` found and it rectangles them, so *which* two facets are crossed is the caller's
argument and never a choice baked in here: a second cross, over any two facets, is another call
rather than another function.

**Which values those two offer is not read anywhere below the edge**: a tick list belongs with the
page that draws the tick boxes, so the axes here are the values the corpus actually carries, and
crossing them with what a labeller *could* have ticked is the page's.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.modalities.text2text.dataset_management import LabelSummary
from dataforce.modalities.text2text.dataset_management.duplicate_data_checking import (
    canonical_json,
)


def list_categories(stored: Any) -> tuple[str, ...]:
    if isinstance(stored, tuple):
        return tuple(dict.fromkeys(str(one) for one in stored))
    return (str(stored),)


def create_joint_distribution_matrix(
    pair_counts: Mapping[tuple[Any, Any], int],
) -> Mapping[str, Mapping[str, int]]:

    counted: Counter[tuple[str, str]] = Counter()
    for (row, column), number in pair_counts.items():
        for one_row in list_categories(row):
            for one_column in list_categories(column):
                counted[(one_row, one_column)] += number

    rows = sorted({one for row, _ in pair_counts for one in list_categories(row)})
    columns = sorted(
        {one for _, column in pair_counts for one in list_categories(column)}
    )
    return {row: {column: counted[(row, column)] for column in columns} for row in rows}


def describe_labels(labels: Sequence[Sequence[Any] | None]) -> LabelSummary:

    written = {canonical_json(label or ()) for label in labels}
    return LabelSummary(
        total=len(labels),
        number_not_null_label=sum(1 for label in labels if label),
        number_diff_label=len(written),
    )
