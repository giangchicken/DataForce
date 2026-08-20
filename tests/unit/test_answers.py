"""δ and consensus: the two pieces every disagreement statistic is written on.

This is where `tool_decision` proves rules 1, 2 and 3 of the core spec's § *Rules a
profile must satisfy*, which no shared code checks: δ is a metric, `consensus` is
deterministic and honours unanimity, and an answer survives a JSON round trip.
Rules 4 and 5 are in `test_tool_decision_adapter.py` and `test_tool_decision.py`.

`delta(∅, ∅) = 0` gets its own tests because it is load-bearing on 35.4% of this
corpus, and because the two natural wrong answers -- raising on `0/0`, or calling
two empty answers maximally distant -- both fail silently as a plausible number.
"""

from __future__ import annotations

import json
import math
import random

import pytest

from dataforce.profiles.tool_decision.answers import consensus, delta

TOOLS = [f"Lookup{i:02d}_{i:x}a" for i in range(8)]


def random_answers(seed: int, count: int) -> list[list[str]]:
    """Seeded, so a pair that breaks δ breaks it again on the next run."""
    generator = random.Random(seed)
    return [
        generator.sample(TOOLS, generator.randint(0, len(TOOLS))) for _ in range(count)
    ]


# --- the axioms ---------------------------------------------------------------


def test_two_empty_answers_agree_perfectly() -> None:
    assert delta([], []) == 0.0


def test_an_empty_answer_and_a_non_empty_one_are_maximally_distant() -> None:
    assert delta([], ["Lookup00_0a"]) == 1.0


def test_delta_is_a_metric_over_random_pairs() -> None:
    pairs = random_answers(seed=20260819, count=200)

    for left in pairs:
        assert delta(left, left) == 0.0
        for right in pairs:
            forward, backward = delta(left, right), delta(right, left)
            assert forward == backward
            assert not math.isnan(forward)
            assert 0.0 <= forward <= 1.0


def test_order_within_an_answer_does_not_matter() -> None:
    """An answer is a set carried as an array, so two orderings are one answer."""
    assert delta(["a", "b"], ["b", "a"]) == 0.0


def test_a_repeated_tool_is_the_same_answer() -> None:
    assert delta(["a", "a", "b"], ["a", "b"]) == 0.0


def test_the_distance_is_jaccard() -> None:
    assert delta(["a", "b"], ["b", "c"]) == pytest.approx(1 - 1 / 3)


def test_a_bare_string_is_not_an_answer() -> None:
    """Otherwise `set("SendMail")` would make δ compare spellings, silently."""
    with pytest.raises(TypeError, match="array of tool names"):
        delta("SendMail", ["SendMail"])


# --- consensus ---------------------------------------------------------------


def test_consensus_over_unanimous_votes_is_that_vote() -> None:
    assert consensus([["a", "b"]] * 3) == ["a", "b"]


def test_consensus_over_unanimous_empty_votes_is_the_empty_answer() -> None:
    """Not None: a strict majority did vote, and they voted for no tool."""
    assert consensus([[], [], []]) == []


def test_no_votes_is_no_consensus_which_is_not_the_empty_answer() -> None:
    assert consensus([]) is None


def test_a_strict_majority_is_needed_not_a_tie() -> None:
    assert consensus([["a"], ["b"]]) == []
    assert consensus([["a"], ["a"], ["b"], ["b"]]) == []


def test_consensus_can_be_a_set_no_juror_proposed() -> None:
    """Acceptable for a ranking signal, and why it may never become a label alone."""
    votes = [["a", "b"], ["b", "c"], ["a", "c"]]

    agreed = consensus(votes)

    assert agreed == ["a", "b", "c"]
    assert all(agreed != vote for vote in votes)


def test_consensus_drops_a_tool_only_one_juror_saw() -> None:
    assert consensus([["a", "b"], ["a"], ["a"]]) == ["a"]


def test_consensus_is_sorted_so_two_runs_agree() -> None:
    assert consensus([["c", "a", "b"]] * 3) == ["a", "b", "c"]


def test_an_answer_survives_a_json_round_trip() -> None:
    """Rule 3. Every artifact is JSONL, so an answer that comes back as something
    else -- a set, a tuple -- makes every distance computed after it wrong, and
    wrong one stage later rather than here."""
    for answer in random_answers(seed=20260820, count=50):
        restored = json.loads(json.dumps(answer))

        assert restored == answer
        assert delta(restored, answer) == 0.0


def test_consensus_returns_the_unanimous_answer_for_every_sampled_answer() -> None:
    """Rule 2's unanimity clause, over sampled answers rather than two chosen ones:
    three identical votes come back δ-0 from the vote, the empty answer included."""
    for answer in random_answers(seed=20260820, count=50):
        agreed = consensus([answer] * 3)

        assert agreed is not None
        assert delta(agreed, answer) == 0.0
