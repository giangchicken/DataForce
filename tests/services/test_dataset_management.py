"""The arithmetic the store cannot do: the grid the pairs make, and what a corpus's labels come to.

**The zeros are the finding.** A `GROUP BY` answers only for pairs some sample makes, so a matrix
built out of what SQL returned is a matrix with the interesting cells missing. Every test about
`create_joint_distribution_matrix` here is really about a cell no sample produced.

What it does *not* put back is a value nobody has ticked yet: the list of tickable values lives
with the page that draws the tick boxes, so crossing this grid against it is the page's arithmetic
and not tested here.

Nothing here opens a session: these are the functions `H-8` keeps on the far side of the adapter,
and a test that needed a database to drive one would be evidence the boundary had moved.
"""

from typing import Any

from dataforce.services.tool_decision.dataset_management import (
    create_joint_distribution_matrix,
    summarise_labels,
)

# Three pairs, as a `GROUP BY` over `domain` and `call_trigger` would hand them back: three domains
# and three triggers, so the grid they make is nine cells and six of them are empty.
PAIR_COUNTS: dict[tuple[Any, Any], int] = {
    ("debt_collection", ("condition_met",)): 5,
    ("telesale", ("user_utterance",)): 2,
    ("customer_care", ("every_turn",)): 1,
}

LOOKED_UP = [{"name": "Lookup", "arguments": {"id": "KH-1"}}]


def test_the_matrix_is_a_rectangle_so_a_pair_no_sample_makes_reads_zero() -> None:
    """Nine cells out of three pairs. The six zeros are what the page is drawn to show: a domain
    that never triggers one way is a domain the corpus cannot teach that trigger in."""
    matrix = create_joint_distribution_matrix(PAIR_COUNTS)

    cells = [number for columns in matrix.values() for number in columns.values()]
    assert len(cells) == 9
    assert sorted(cells) == [0] * 6 + [1, 2, 5]
    assert matrix["debt_collection"]["every_turn"] == 0


def test_the_axes_are_sorted_so_the_same_rows_always_draw_the_same_grid() -> None:
    """A matrix is read as a grid, and a grid whose axes move between two calls is unreadable."""
    matrix = create_joint_distribution_matrix(PAIR_COUNTS)

    assert tuple(matrix) == ("customer_care", "debt_collection", "telesale")
    assert tuple(matrix["telesale"]) == (
        "condition_met",
        "every_turn",
        "user_utterance",
    )


def test_a_sample_triggered_two_ways_counts_in_both_cells() -> None:
    """`call_trigger` is a set: one value per call, so a sample answering a turn with two calls is
    evidence that this domain triggers both ways, and a cell answers exactly that."""
    matrix = create_joint_distribution_matrix(
        {("telesale", ("user_utterance", "every_turn")): 4}
    )

    assert matrix["telesale"] == {"every_turn": 4, "user_utterance": 4}


def test_one_way_spelled_twice_in_a_set_is_still_one_way() -> None:
    """A cell says *the corpus has such a sample*. Counting a repeat twice would read as two."""
    matrix = create_joint_distribution_matrix(
        {("telesale", ("every_turn", "every_turn")): 1}
    )

    assert matrix["telesale"]["every_turn"] == 1


def test_a_sample_that_triggers_nothing_has_no_cell_to_be_in() -> None:
    """The no-call sample: there is no trigger to describe, so it names no column.

    Its domain still names a row, because the row is a fact about the corpus -- and the row comes
    out empty rather than missing, which is the honest answer when nothing in the corpus triggers
    at all. `number_label_tools` is where that sample is counted.
    """
    assert create_joint_distribution_matrix({("telesale", ()): 7}) == {"telesale": {}}


def test_an_empty_label_and_a_null_one_are_one_answer() -> None:
    """`[]` and `null` are one reading -- no tool call is needed -- and § *Open* leaves only which
    spelling the corpus writes, not whether the two mean different things.

    So they count as one distinct answer between them, and neither counts as an answer given.
    """
    summarised = summarise_labels([[], None, LOOKED_UP])

    assert summarised.total == 3
    assert summarised.number_not_null_label == 1
    assert summarised.number_diff_label == 2


def test_how_many_distinct_answers_the_corpus_holds() -> None:
    """Diversity, counted over the same canonical text the duplicate grouping compares by -- so a
    label written with its keys in another order is the same answer to both, and a thousand rows
    carrying nine answers between them read as a corpus that teaches nine things."""
    reordered = [{"arguments": {"id": "KH-1"}, "name": "Lookup"}]
    summarised = summarise_labels([LOOKED_UP, reordered, []])

    assert summarised.number_diff_label == 2
    assert summarised.number_not_null_label == 2


def test_an_answer_nothing_can_read_is_still_an_answer_given() -> None:
    """A label entry naming no tool is a broken row, not a row that kept its hands in its pockets.

    Counting it as *no answer* would pad the no-call share, which is what irrelevance detection is
    measured from -- so a corpus of broken entries would read as a corpus rich in samples that
    correctly declined. `schema_valid` is what marks such a row broken.
    """
    summarised = summarise_labels([["nonsense"], [], None])

    assert summarised.number_not_null_label == 1
    assert summarised.total == 3


def test_a_corpus_of_no_rows_is_an_answer_and_not_a_division() -> None:
    """Every figure is a count beside its total, so nothing here has a denominator to be zero."""
    summarised = summarise_labels([])

    assert (summarised.total, summarised.number_not_null_label) == (0, 0)
    assert summarised.number_diff_label == 0
