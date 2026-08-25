"""T17 · duplicate_check: what counts as a duplicate, and which of the two groups it lands in.

The row is § *Per-service contracts*' fourth: reads `content` and `label`, writes
`data_quality.duplicate_check`, skips nothing, removes nothing. What this module has to pin down is
the *definition*, because the task's own note says to settle it before writing either half.

**The encoder is a lookup table here, and that is what makes a cosine assertable.** A static
embedding model returns a fixed-length vector, so the fixtures are hand-written unit vectors two
decimal places apart and the threshold is passed in per test — a real model's numbers would make
every assertion below a measurement of the model rather than of the grouping. What is this stage's to
get right is which pairs are *compared*, and that is asserted directly.

Every fixture is invented (AGENTS.md §9).
"""

from collections.abc import Sequence
from typing import Any

import pytest

from dataforce.engine import Engine, Registry
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text import Text2Text
from dataforce.pipeline.data_quality.duplicate_check import duplicate_check
from dataforce.record import Part, Record

from .test_label_check import written_paths
from .test_tool_decision import CATALOG, SENT, TICKETED, a_profile, a_record

ASKED = "Cho mình xem số dư tài khoản."
ASKED_AGAIN = "Cho mình xem số dư tài khoản nhé."
ASKED_OTHERWISE = "Mở giúp mình một ticket."

# Hand-written unit vectors: the first two are 0.96 apart, the third is orthogonal to both.
VECTORS: dict[str, Sequence[float]] = {
    ASKED: (1.0, 0.0),
    ASKED_AGAIN: (0.96, 0.28),
    ASKED_OTHERWISE: (0.0, 1.0),
}
UNKNOWN: Sequence[float] = (0.0, 0.0)

# One catalog entry, so a second scenario can be built without inventing a second tool shape.
ONE_TOOL = CATALOG[:1]


def a_vector(document: str) -> Sequence[float]:
    """The stand-in encoder: fixed length, and the same vector for the same document every run."""
    return VECTORS.get(document, UNKNOWN)


def an_engine(near: Any = 0.95) -> Engine:
    """Both axes resolved, with an encoder whose numbers a test can reason about."""
    modality = Text2Text(
        Manifest(
            name="text2text",
            version="1",
            declarations={
                "embedding": {"model": "m", "exclude_roles": []},
                "language": "vi",
            },
        ),
        a_vector,
    )
    profile = a_profile()
    registry = Registry()
    registry.register_modality(modality.name, modality)
    registry.register_profile(profile.name, profile)
    return Engine(
        modality=modality,
        profile=profile,
        registry=registry,
        thresholds={"thresholds": {"duplicate_check": {"near_duplicate_cosine": near}}},
        policy_digests={},
    )


def a_record_saying(text: str, **written: Any) -> Record:
    """One record whose whole content is that turn, so its vector is that turn's."""
    return a_record(content=(Part(type="text", role="user", text=text),), **written)


def grouped(*records: Record, engine: Engine | None = None) -> list[Any]:
    """What this stage wrote on each record, in the order the records were handed over."""
    return [
        record.data_quality.duplicate_check
        for record in duplicate_check(engine or an_engine(), records).records
    ]


# --- what counts as a duplicate ---


def test_the_same_content_is_a_duplicate_and_lists_the_other_record_s_id() -> None:
    """Identical content shares a `record_id` (Requirement 6), so the id it lists is its own.

    Written down rather than tidied away: the alternative -- excluding an id equal to one's own --
    would hide exactly the pair that most needs finding.
    """
    twice = (a_record_saying(ASKED), a_record_saying(ASKED))

    both = grouped(*twice)

    assert both[0].duplicate_content_same_label == (twice[0].record_id,)
    assert both[1].duplicate_content_same_label == (twice[1].record_id,)


def test_the_same_content_with_a_different_label_is_the_other_group() -> None:
    """*One of them is wrong*, which is a different decision from *drop one of them*."""
    both = grouped(
        a_record_saying(ASKED, label=(SENT,)),
        a_record_saying(ASKED, label=(TICKETED,)),
    )

    assert both[0].duplicate_content_same_label == ()
    assert both[1].duplicate_content_diff_label != ()


def test_near_identical_content_is_a_duplicate_at_the_declared_threshold() -> None:
    """Requirement 23: near-duplicates use the modality's embedding, and the number is declared."""
    pair = (a_record_saying(ASKED), a_record_saying(ASKED_AGAIN))

    both = grouped(*pair, engine=an_engine(near=0.95))

    assert both[0].duplicate_content_same_label == (pair[1].record_id,)


def test_the_same_pair_is_not_a_duplicate_at_a_tighter_threshold() -> None:
    """The threshold is what decides, so a tuning pass re-runs this stage and nothing else."""
    both = grouped(
        a_record_saying(ASKED),
        a_record_saying(ASKED_AGAIN),
        engine=an_engine(near=0.97),
    )

    assert both[0].duplicate_content_same_label == ()
    assert both[0].duplicate_content_diff_label == ()


def test_different_content_is_not_a_duplicate() -> None:
    """The orthogonal pair, which is what the threshold is protecting."""
    both = grouped(a_record_saying(ASKED), a_record_saying(ASKED_OTHERWISE))

    assert both[0].duplicate_content_same_label == ()


# --- the decision this task existed to make ---


def test_near_identical_content_offering_different_tools_is_not_a_duplicate() -> None:
    """*Not duplicates for this task*: two prompts with different catalogs are two questions.

    `scenario_hash` already names *these two records pose the same task*, so it is the blocking key
    for the near pass — which is also what keeps a quadratic comparison affordable.
    """
    both = grouped(
        a_record_saying(ASKED),
        a_record_saying(ASKED_AGAIN, tools=ONE_TOOL),
    )

    assert both[0].duplicate_content_same_label == ()
    assert both[1].duplicate_content_same_label == ()


def test_the_same_content_offering_different_tools_is_still_a_duplicate() -> None:
    """`record_id` is over content alone, so a shared one is a fact before any scenario is read."""
    pair = (a_record_saying(ASKED), a_record_saying(ASKED, tools=ONE_TOOL))

    both = grouped(*pair)

    assert both[0].duplicate_content_same_label == (pair[1].record_id,)


def test_the_label_side_is_the_profile_s_own_distance_and_not_equality() -> None:
    """δ says a bare name and the same call with no arguments are one answer; `==` would not."""
    both = grouped(
        a_record_saying(ASKED, label=("OpenTicket",)),
        a_record_saying(ASKED, label=({"name": "OpenTicket", "arguments": {}},)),
    )

    assert both[0].duplicate_content_same_label != ()
    assert both[0].duplicate_content_diff_label == ()


# --- the stage's own promises ---


def test_a_record_gains_exactly_one_key() -> None:
    """I8, and Requirement 41: a group is a value on the record, never a shorter list."""
    record = a_record_saying(ASKED)

    written = duplicate_check(an_engine(), [record]).records[0]

    assert written_paths(record.model_dump(), written.model_dump()) == {
        "data_quality.duplicate_check"
    }


def test_a_record_with_no_duplicates_still_gets_the_key() -> None:
    """Two empty groups is a report, and its absence is what a precondition downstream reads."""
    only = grouped(a_record_saying(ASKED))[0]

    assert only.duplicate_content_same_label == ()
    assert only.duplicate_content_diff_label == ()


def test_no_record_is_removed() -> None:
    """I11, over a corpus that is nothing but duplicates."""
    records = [a_record_saying(ASKED) for _ in range(3)]

    assert len(duplicate_check(an_engine(), records).records) == 3


def test_two_runs_over_one_corpus_group_identically() -> None:
    """Requirement 23: the embedding is static, so the groups are a function of the corpus."""
    records = [
        a_record_saying(ASKED),
        a_record_saying(ASKED_AGAIN),
        a_record_saying(ASKED_OTHERWISE),
    ]

    once = duplicate_check(an_engine(), records).records
    twice = duplicate_check(an_engine(), records).records

    assert [record.data_quality for record in once] == [
        record.data_quality for record in twice
    ]


def test_the_stage_returns_no_side_output() -> None:
    """A group is a value on the record; there is nothing here for the edge to persist."""
    assert duplicate_check(an_engine(), [a_record_saying(ASKED)]).side_output == {}


@pytest.mark.parametrize(
    "near", [None, "0.95", 2.0, True], ids=["absent", "text", "above-one", "true"]
)
def test_a_threshold_that_is_not_a_ratio_is_refused_before_any_record(
    near: Any,
) -> None:
    """No defensible default: 0 groups everything and 1 groups nothing, so it refuses to guess."""
    with pytest.raises(ConfigError, match="near_duplicate_cosine"):
        duplicate_check(an_engine(near=near), [a_record_saying(ASKED)])
