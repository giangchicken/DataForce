"""δ and consensus: the two pieces every disagreement statistic is written on.

This is where `tool_decision` proves rules 1, 2 and 3 of the core spec's § *Rules a
profile must satisfy*, which no shared code checks: δ is a metric, `vote_consensus` is
deterministic and honours unanimity, and an answer survives a JSON round trip.
Rules 4 and 5 are in `test_build_record.py` and `test_tool_decision.py`.

`answer_distance(∅, ∅) = 0` gets its own tests because it is load-bearing on 35.4% of this
corpus, and because the two natural wrong answers -- raising on `0/0`, or calling
two empty answers maximally distant -- both fail silently as a plausible number.
"""

from __future__ import annotations

import json
import math
import random

import pytest

from dataforce.profiles.tool_decision.answer import answer_distance, vote_consensus
from dataforce.profiles.tool_decision.schema import Catalog, Tool

TOOLS = [f"Lookup{i:02d}_{i:x}a" for i in range(8)]

# Every fixture tool takes no required argument unless a test says otherwise, so a
# consensus is never dropped for a reason the test did not ask for.
FREE = Catalog(tools=tuple(Tool(name=name, description="") for name in TOOLS))
LETTERS = Catalog(
    tools=tuple(Tool(name=name, description="") for name in ("a", "b", "c"))
)


def agreed(votes: list[object], catalog: Catalog = LETTERS) -> object:
    """The consensus, as the names it called -- what the names-only version returned.

    Consensus now returns calls, and most of the rules below are about *which tools*
    survive a majority. Reading the names back keeps those tests about the rule they
    were written for; the argument rules get their own assertions further down.
    """
    calls = vote_consensus(votes, catalog)
    return None if calls is None else [call["name"] for call in calls]


def random_answers(seed: int, count: int) -> list[list[str]]:
    """Seeded, so a pair that breaks δ breaks it again on the next run."""
    generator = random.Random(seed)
    return [
        generator.sample(TOOLS, generator.randint(0, len(TOOLS))) for _ in range(count)
    ]


# --- the axioms ---------------------------------------------------------------


def test_two_empty_answers_agree_perfectly() -> None:
    assert answer_distance([], []) == 0.0


def test_an_empty_answer_and_a_non_empty_one_are_maximally_distant() -> None:
    assert answer_distance([], ["Lookup00_0a"]) == 1.0


def test_delta_is_a_metric_over_random_pairs() -> None:
    pairs = random_answers(seed=20260819, count=200)

    for left in pairs:
        assert answer_distance(left, left) == 0.0
        for right in pairs:
            forward, backward = (
                answer_distance(left, right),
                answer_distance(right, left),
            )
            assert forward == backward
            assert not math.isnan(forward)
            assert 0.0 <= forward <= 1.0


def test_order_within_an_answer_does_not_matter() -> None:
    """An answer is a set carried as an array, so two orderings are one answer."""
    assert answer_distance(["a", "b"], ["b", "a"]) == 0.0


def test_a_repeated_tool_is_the_same_answer() -> None:
    assert answer_distance(["a", "a", "b"], ["a", "b"]) == 0.0


def test_the_distance_is_jaccard() -> None:
    assert answer_distance(["a", "b"], ["b", "c"]) == pytest.approx(1 - 1 / 3)


# --- requirement 72: δ is soft, and the softness is specified ------------------


LOOKUP = {"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}
LOOKUP_ONE_ARGUMENT_OFF = {
    "name": "Lookup",
    "arguments": {"ma_khach": "480215", "ky": "thang_truoc"},
}
SEND = {"name": "Send", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}


def test_the_four_hand_worked_distances_are_ordered() -> None:
    """Requirement 72's whole point: the two failures are not equally wrong.

    A jury that scored "right tool, wrong argument" the same as "wrong tool" would
    rank them the same, and the argument error is the one a human can fix in a second.
    """
    same_call = answer_distance([LOOKUP], [LOOKUP])
    one_argument = answer_distance([LOOKUP], [LOOKUP_ONE_ARGUMENT_OFF])
    other_tool = answer_distance([LOOKUP], [SEND])

    assert same_call == 0.0
    assert one_argument == pytest.approx(0.5)
    assert other_tool == 1.0
    assert 0 == same_call < one_argument < other_tool <= 1


def test_one_differing_argument_of_two_is_half_disagreement() -> None:
    """Over the *union* of keys, so a key present in only one side is a disagreement."""
    assert answer_distance(
        [{"name": "a", "arguments": {"x": 1, "y": 2}}],
        [{"name": "a", "arguments": {"x": 1, "y": 3}}],
    ) == pytest.approx(0.5)
    assert answer_distance(
        [{"name": "a", "arguments": {"x": 1}}],
        [{"name": "a", "arguments": {"x": 1, "y": 2}}],
    ) == pytest.approx(0.5)


def test_a_call_with_no_arguments_agrees_perfectly_with_another() -> None:
    """The clause the exact Jaccard reduction rests on."""
    assert answer_distance([{"name": "a"}], [{"name": "a", "arguments": {}}]) == 0.0
    assert answer_distance([{"name": "a"}], ["a"]) == 0.0


def test_delta_reduces_to_jaccard_over_names_to_the_bit() -> None:
    """Requirement 72's degradation clause, over the sampled answers the names-only
    implementation was measured on -- so every number taken before arguments existed
    still describes this δ rather than approximately describing it."""
    answers = random_answers(seed=20260819, count=120)

    for left in answers:
        for right in answers:
            union = set(left) | set(right)
            jaccard = (
                0.0 if not union else 1.0 - len(set(left) & set(right)) / len(union)
            )

            assert answer_distance(left, right) == jaccard


def test_a_compound_answer_is_still_a_metric_and_still_bounded() -> None:
    """Rule 1's four properties on the compound type. The triangle inequality is not
    asserted -- core requirement 4 says why it is deliberately excluded."""
    answers: list[list[dict[str, object]]] = [
        [],
        [LOOKUP],
        [SEND],
        [LOOKUP_ONE_ARGUMENT_OFF],
        [LOOKUP, SEND],
        [{"name": "Lookup"}],
    ]

    for left in answers:
        assert answer_distance(left, left) == 0.0
        for right in answers:
            forward = answer_distance(left, right)

            assert forward == answer_distance(right, left)
            assert not math.isnan(forward)
            assert 0.0 <= forward <= 1.0


def test_argument_order_inside_a_call_does_not_matter() -> None:
    assert (
        answer_distance(
            [{"name": "a", "arguments": {"x": 1, "y": 2}}],
            [{"name": "a", "arguments": {"y": 2, "x": 1}}],
        )
        == 0.0
    )


def test_a_bare_string_is_not_an_answer() -> None:
    """Otherwise `set("SendMail")` would make δ compare spellings, silently."""
    with pytest.raises(TypeError, match="array of calls"):
        answer_distance("SendMail", ["SendMail"])


# --- vote_consensus ----------------------------------------------------------


def test_consensus_over_unanimous_votes_is_that_vote() -> None:
    assert agreed([["a", "b"]] * 3) == ["a", "b"]


def test_consensus_over_unanimous_empty_votes_is_the_empty_answer() -> None:
    """Not None: a strict majority did vote, and they voted for no tool."""
    assert vote_consensus([[], [], []], LETTERS) == []


def test_no_votes_is_no_consensus_which_is_not_the_empty_answer() -> None:
    assert vote_consensus([], LETTERS) is None


def test_a_strict_majority_is_needed_not_a_tie() -> None:
    assert agreed([["a"], ["b"]]) == []
    assert agreed([["a"], ["a"], ["b"], ["b"]]) == []


def test_consensus_can_be_a_set_no_juror_proposed() -> None:
    """Acceptable for a ranking signal, and why it may never become a label alone."""
    votes = [["a", "b"], ["b", "c"], ["a", "c"]]

    consensus = agreed(votes)

    assert consensus == ["a", "b", "c"]
    assert all(consensus != vote for vote in votes)


def test_consensus_drops_a_tool_only_one_juror_saw() -> None:
    assert agreed([["a", "b"], ["a"], ["a"]]) == ["a"]


def test_consensus_is_sorted_so_two_runs_agree() -> None:
    assert agreed([["c", "a", "b"]] * 3) == ["a", "b", "c"]


def test_an_answer_survives_a_json_round_trip() -> None:
    """Rule 3. Every artifact is JSONL, so an answer that comes back as something
    else -- a set, a tuple -- makes every distance computed after it wrong, and
    wrong one stage later rather than here."""
    for answer in random_answers(seed=20260820, count=50):
        restored = json.loads(json.dumps(answer))

        assert restored == answer
        assert answer_distance(restored, answer) == 0.0


def test_consensus_returns_the_unanimous_answer_for_every_sampled_answer() -> None:
    """Rule 2's unanimity clause, over sampled answers rather than two chosen ones:
    three identical votes come back δ-0 from the vote, the empty answer included."""
    for answer in random_answers(seed=20260820, count=50):
        consensus = vote_consensus([answer] * 3, FREE)

        assert consensus is not None
        assert answer_distance(consensus, answer) == 0.0


# --- requirement 74: consensus is per name, then per argument ------------------


LOOKUP_CATALOG = Catalog(
    tools=(
        Tool(
            name="Lookup",
            description="",
            parameters={
                "type": "object",
                "properties": {
                    "ma_khach": {"type": "string"},
                    "ky": {"type": "string"},
                },
                "required": ["ma_khach"],
            },
        ),
    )
)


def test_a_two_one_split_on_one_argument_takes_the_majority_value() -> None:
    votes = [
        [{"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_truoc"}}],
    ]

    assert vote_consensus(votes, LOOKUP_CATALOG) == [
        {"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}
    ]


def test_an_argument_with_no_majority_is_absent_rather_than_guessed() -> None:
    """`ky` is not `required`, so the call survives without it -- carrying only what a
    majority actually said."""
    votes = [
        [{"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "thang_truoc"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "480215", "ky": "nam_nay"}}],
    ]

    assert vote_consensus(votes, LOOKUP_CATALOG) == [
        {"name": "Lookup", "arguments": {"ma_khach": "480215"}}
    ]


def test_a_required_argument_with_no_majority_drops_the_call_entirely() -> None:
    """Requirement 74's last clause. Half-building it would put a value no juror
    proposed into a ranking signal, and it would fail requirement 71's schema."""
    votes = [
        [{"name": "Lookup", "arguments": {"ma_khach": "111111"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "222222"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "333333"}}],
    ]

    assert vote_consensus(votes, LOOKUP_CATALOG) == []


def test_arguments_are_agreed_among_the_jurors_who_named_the_tool() -> None:
    """A juror who did not call the tool has no opinion about its arguments, so the
    argument majority is over the three who named it, not over all five."""
    votes = [
        [{"name": "Lookup", "arguments": {"ma_khach": "480215"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "480215"}}],
        [{"name": "Lookup", "arguments": {"ma_khach": "999999"}}],
        [],
        [],
    ]

    assert vote_consensus(votes, LOOKUP_CATALOG) == [
        {"name": "Lookup", "arguments": {"ma_khach": "480215"}}
    ]


def test_an_object_valued_argument_can_reach_a_majority() -> None:
    """Counted through canonical JSON, because a `Counter` cannot key on a dict."""
    nested = {"name": "Lookup", "arguments": {"ma_khach": {"loai": "ca_nhan"}}}

    assert vote_consensus([[nested]] * 3, LOOKUP_CATALOG) == [nested]
