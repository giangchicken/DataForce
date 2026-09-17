"""`duplicate_groups` pinned: which rows are one input, and which of those disagree.

The two groups are different findings. Same input under one label is redundancy, and dropping all
but one of them is safe. Same input under two labels is a queue: one of them is wrong, or the task
is arguable where the guideline said it was not.
"""

import hashlib
import json
from typing import Any

import pytest

from dataforce.modalities.text2text.dataset_management import duplicate_groups

ASKED = {"messages": [{"role": "user", "content": "nợ bao nhiêu"}], "tools": ["Lookup"]}
OTHER = {"messages": [{"role": "user", "content": "cảm ơn"}], "tools": ["Lookup"]}
LOOKUP = ({"name": "Lookup", "arguments": {"id": "KH-1"}},)


def digest_of(one_input: Any) -> str:
    """What the grouping must key by, written out here rather than imported.

    Asserting against the module's own digest would pin the grouping and nothing else -- md5, or
    a key ordering that only sorts the outer level, would both still pass.
    """
    written = json.dumps(
        one_input, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(written.encode("utf-8")).hexdigest()


def test_one_input_under_one_label_is_redundancy() -> None:
    """Two rows saying the same thing and answering it the same way: keep one."""
    found = duplicate_groups([ASKED, ASKED], [LOOKUP, LOOKUP])
    assert found.duplicate_content_same_label == (digest_of(ASKED),)
    assert found.duplicate_content_diff_label == ()


def test_one_input_under_two_labels_is_a_queue_to_inspect() -> None:
    """The finding the corpus is scaled on: one of the two is wrong."""
    found = duplicate_groups([ASKED, ASKED], [LOOKUP, ()])
    assert found.duplicate_content_diff_label == (digest_of(ASKED),)
    assert found.duplicate_content_same_label == ()


def test_a_group_where_two_agree_and_one_does_not_is_one_group_to_inspect() -> None:
    """Dropping all but one is unsafe the moment any reading in the group differs."""
    found = duplicate_groups([ASKED, ASKED, ASKED], [LOOKUP, LOOKUP, ()])
    assert found.duplicate_content_diff_label == (digest_of(ASKED),)
    assert found.duplicate_content_same_label == ()


def test_the_key_order_inside_an_input_does_not_change_the_grouping() -> None:
    """Two rows written by two writers are one input, at every depth the input nests to.

    The reorder is inside `messages[0]` as well as at the top level: a canonicalisation that
    sorted only the outer keys would group these two apart, and a real input always nests.
    """
    reordered = {
        "tools": ASKED["tools"],
        "messages": [{"content": "nợ bao nhiêu", "role": "user"}],
    }
    found = duplicate_groups([ASKED, reordered], [LOOKUP, LOOKUP])
    assert found.duplicate_content_same_label == (digest_of(ASKED),)


def test_the_key_order_inside_a_label_does_not_split_a_group() -> None:
    """The same rule on the other side: two spellings of one call are one reading."""
    reordered = ({"arguments": {"id": "KH-1"}, "name": "Lookup"},)
    found = duplicate_groups([ASKED, ASKED], [LOOKUP, reordered])
    assert found.duplicate_content_same_label == (digest_of(ASKED),)
    assert found.duplicate_content_diff_label == ()


def test_a_corpus_with_no_repeat_answers_two_empty_groups() -> None:
    """Empty groups, not `None`: nothing found is an answer here, unlike the batch check."""
    found = duplicate_groups([ASKED, OTHER], [LOOKUP, ()])
    assert found.duplicate_content_same_label == ()
    assert found.duplicate_content_diff_label == ()


def test_no_call_written_as_null_and_as_empty_is_one_reading() -> None:
    """Both say no call was needed, so these two rows agree and one of them can go.

    Which spelling the corpus writes is open; that they mean the same thing is not, and a group
    reported as *one of them is wrong* costs a person a re-review it did not need.
    """
    found = duplicate_groups([ASKED, ASKED], [None, ()])
    assert found.duplicate_content_same_label == (digest_of(ASKED),)
    assert found.duplicate_content_diff_label == ()


def test_a_label_for_every_input_or_the_corpus_was_read_wrong() -> None:
    """The two come out of one query as two columns; a length apart means they did not."""
    with pytest.raises(ValueError):
        duplicate_groups([ASKED, OTHER], [LOOKUP])
