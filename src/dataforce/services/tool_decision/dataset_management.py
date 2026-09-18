"""logic · the arithmetic over what the store counted, and the cells SQL cannot answer for."""

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


def summarise_labels(labels: Sequence[Sequence[Any] | None]) -> DatasetLabelSummary:

    written = {canonical_json(label or ()) for label in labels}
    return DatasetLabelSummary(
        total=len(labels),
        number_not_null_label=sum(1 for label in labels if label),
        number_diff_label=len(written),
    )


def build_dataset_statistics(
    sample_totals: Mapping[str, int],
    counted_distribution_by_facet: Mapping[str, Mapping[str, int]],
    counted_pairs_of_domain_and_call_trigger: Mapping[tuple[Any, Any], int],
    sample_contents: Sequence[ToolDecisionSampleContent],
) -> ToolDecisionDatasetStatistics:
    """§ *The statistics* in full, out of what one read of the labelled table came back with.

    Handed the four reads rather than taking them, because `services/` is `logic` and may not open
    a database: the router is the only layer that holds a session, so it reads and this composes.
    Every figure below is either one of those reads or arithmetic over them, and none of it is
    kept -- two calls with a write between them differ.

    **A parameter handed straight to a field carries that field's name**, so `sample_totals` and
    `counted_distribution_by_facet` are passed through under the name they will answer under, and a
    caller reading the keyword knows where it lands without opening the shape.

    The pair is the one that cannot: `counted_pairs_of_domain_and_call_trigger` is only the pairs
    some row carries, and the field is the **rectangle** those pairs make, zeros included. Two
    different things, so two names -- sharing the stem that says which two variables, which is what
    makes a router crossing a different pair read as wrong against the field it fills.

    A catalog is read out of `input` here and not at the edge, because what a stored `input` holds
    -- `{messages, tools}` for this task -- is the profile's declaration, and a route that reached
    inside one would be a second place that knows it.
    """
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
