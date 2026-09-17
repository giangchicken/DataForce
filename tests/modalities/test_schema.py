"""What a stored text2text sample is, pinned: the three fields a profile's tables map to columns.

`extra="forbid"` is the load-bearing part. A facet is carried in the `facets` map, so a mistyped
field name would otherwise be accepted here and arrive at the table as a column that is never
written.
"""

import pytest
from pydantic import ValidationError

from dataforce.modalities.text2text.dataset_management import (
    DuplicateGroups,
    StoredSample,
)

ASKED = {"messages": [{"role": "user", "content": "nợ bao nhiêu"}], "tools": ["Lookup"]}


def test_a_stored_sample_is_an_input_a_label_and_the_facets_as_a_map() -> None:
    """The three the profile's tables turn into columns, and nothing else."""
    kept = StoredSample(input=ASKED, label=None, facets={"language": "vi"})
    assert (kept.input, kept.label, kept.facets) == (ASKED, None, {"language": "vi"})


def test_a_field_this_shape_does_not_declare_is_refused() -> None:
    """A facet goes in `facets`. Spelled as a field it would be dropped silently instead."""
    with pytest.raises(ValidationError):
        StoredSample(input=ASKED, label=None, language="vi")  # type: ignore[call-arg]


def test_a_stored_sample_cannot_be_edited_after_it_is_built() -> None:
    """It is what was kept; something rewriting it is rewriting the row."""
    kept = StoredSample(input=ASKED, label=None, facets={})
    with pytest.raises(ValidationError):
        kept.label = ()  # type: ignore[misc]


def test_duplicate_groups_over_nothing_is_two_empty_groups() -> None:
    """The default both fields carry, so a corpus with no repeats reads as an answer."""
    assert DuplicateGroups() == DuplicateGroups(
        duplicate_content_same_label=(), duplicate_content_diff_label=()
    )
