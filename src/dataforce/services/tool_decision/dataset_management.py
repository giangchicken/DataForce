"""logic · the arithmetic over what the store counted, and what a file of raw samples reads as."""

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.modalities.text2text.dataset_management import (
    DatasetLabelSummary,
    calculate_duplicates,
)
from dataforce.modalities.text2text.dataset_management.duplicate_data_checking import (
    canonical_json,
)
from dataforce.profile.tool_decision.label_statistics import (
    count_tool_calls,
    list_offered_tools,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionDatasetStatistics,
    ToolDecisionSampleContent,
)


def read_queued_samples(
    text: str,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[int, ...]]:
    """One file of JSON-per-line, as the samples it holds and the numbers of the lines that are not.

    A line is unreadable if it is not JSON, or is JSON that is not an object: a bare string or a
    list is valid JSON and is not a sample, and letting one through would put a row in the queue
    that every route downstream would refuse one at a time.

    An unreadable line never stops the ones around it. A corpus assembled by hand has a bad line in
    it more often than not, and an import that refuses the file wholesale makes the reviewer find
    the line with no help at all -- so the readable ones land and the rest come back by number.

    Blank lines are not counted at all. A trailing newline is how every file ends, and reporting it
    as line 341 of 340 is a fault the reader would have to learn to ignore.
    """
    samples: list[Mapping[str, Any]] = []
    unreadable: list[int] = []
    for at, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            read = json.loads(line)
        except ValueError:
            unreadable.append(at)
            continue
        if isinstance(read, dict):
            samples.append(read)
        else:
            unreadable.append(at)
    return tuple(samples), tuple(unreadable)


def list_categories(stored: Any) -> tuple[str, ...]:
    if isinstance(stored, tuple):
        return tuple(dict.fromkeys(str(one) for one in stored))
    return (str(stored),)


def create_joint_distribution_matrix(
    pair_counts: Mapping[tuple[Any, Any], int],
) -> Mapping[str, Mapping[str, int]]:

    number_by_cell: Counter[tuple[str, str]] = Counter()
    for (row, column), number in pair_counts.items():
        for one_row in list_categories(row):
            for one_column in list_categories(column):
                number_by_cell[(one_row, one_column)] += number

    rows = sorted({one for row, _ in pair_counts for one in list_categories(row)})
    columns = sorted(
        {one for _, column in pair_counts for one in list_categories(column)}
    )
    return {
        row: {column: number_by_cell[(row, column)] for column in columns}
        for row in rows
    }


def summarise_labels(labels: Sequence[Sequence[Any] | None]) -> DatasetLabelSummary:

    label_texts = {canonical_json(label or ()) for label in labels}
    return DatasetLabelSummary(
        total=len(labels),
        number_not_null_label=sum(1 for label in labels if label),
        number_diff_label=len(label_texts),
    )


def build_dataset_statistics(
    sample_totals: Mapping[str, int],
    counted_distribution_by_facet: Mapping[str, Mapping[str, int]],
    counted_pairs_of_domain_and_call_trigger: Mapping[tuple[Any, Any], int],
    sample_contents: Sequence[ToolDecisionSampleContent],
) -> ToolDecisionDatasetStatistics:

    labels = [one.label for one in sample_contents]
    catalogs = [one.input.get("tools") or () for one in sample_contents]
    return ToolDecisionDatasetStatistics(
        sample_totals=sample_totals,
        counted_distribution_by_facet=counted_distribution_by_facet,
        counted_distribution_by_domain_and_call_trigger=create_joint_distribution_matrix(
            counted_pairs_of_domain_and_call_trigger
        ),
        label_summary=summarise_labels(labels),
        number_tools_offered=len(list_offered_tools(catalogs)),
        tool_call_counts=count_tool_calls(labels, catalogs),
        duplicate_groups=calculate_duplicates(
            [one.key for one in sample_contents],
            [one.input for one in sample_contents],
            labels,
        ),
    )
