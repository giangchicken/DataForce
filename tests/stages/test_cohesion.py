"""T20 · cohesion: two numbers over what the jury wrote, and no model call at all.

The panel is the same stand-in `test_jury.py` uses, and the records reach this stage through the
real `label_check` and `jury` -- the arithmetic is what is under test, but *which votes it is over*
is a fact about two stages, and a fixture that hand-wrote a `PanelVerdict` would let the two agree
about `valid` by luck.

**The test that keeps δ soft is `test_a_near_miss_scores_above_a_wrong_tool`.** Every number this
pipeline produces is written on δ (§ *The answer, and the three operations over it*), so a cohesion
figure that ranked *right tool, one argument wrong* level with *wrong tool* would put both in one
triage bucket and no threshold change would separate them again.

Every fixture is invented.
"""

import pytest

from dataforce.engine import Engine
from dataforce.pipeline.ai_review.cohesion import METHOD, cohesion
from dataforce.pipeline.ai_review.jury import jury
from dataforce.pipeline.data_quality.label_check import label_check
from dataforce.record import AgreementScores, Record, StoredAnswer

from .test_jury import a_panel_of, an_engine_that
from .test_label_check import written_paths
from .test_tool_decision import LOOKED_UP, SENT, TICKETED, a_record

# The same tool as `SENT` with one argument wrong, which δ scores above a different tool and a
# verdict count would score identically. One key of two agrees, so δ is 0.5.
SENT_NEARLY = {
    "name": "SendStatement",
    "arguments": {"ma_khach": "480215", "ky": "thang_truoc"},
}
# A bare name is not in the answer space, so a juror that answers one casts an invalid vote.
BARE = "LookupBalance"


def measured(
    *votes: StoredAnswer | None, record: Record | None = None
) -> AgreementScores:
    """One record through all three stages, and the two numbers the last of them wrote."""
    engine = an_engine_that(a_panel_of(*votes))
    given = [record if record is not None else a_record()]
    written = cohesion(engine, jury(engine, label_check(engine, given).records).records)
    scores = written.records[0].ai_review.cohesion

    assert scores is not None
    return scores


def judged(*records: Record, engine: Engine | None = None) -> tuple[Record, ...]:
    """Records through the phase's first two stages, which is what this one is handed."""
    running = engine or an_engine_that(a_panel_of((SENT,)))
    return jury(running, label_check(running, records).records).records


# --- the stage's own three promises ---


def test_a_record_gains_exactly_one_key() -> None:
    """I8. `ai_review.cohesion` and nothing else -- not the votes it read, not the label."""
    engine = an_engine_that(a_panel_of((SENT,)))
    before = judged(a_record(), engine=engine)[0]
    after = cohesion(engine, [before]).records[0]

    assert written_paths(before.model_dump(), after.model_dump()) == {
        "ai_review.cohesion"
    }


def test_every_record_comes_back() -> None:
    """I11, including the one this stage has nothing to measure for."""
    engine = an_engine_that(a_panel_of((SENT,)))
    given = judged(a_record(), a_record(tools=[]), engine=engine)

    assert len(cohesion(engine, given).records) == len(given)


def test_there_is_no_side_output() -> None:
    """Two numbers are values on the record; the fold a human reads is the edge's."""
    engine = an_engine_that(a_panel_of((SENT,)))

    assert cohesion(engine, judged(a_record(), engine=engine)).side_output == {}


# --- what it measures, and over which votes ---


def test_a_unanimous_panel_agrees_with_itself_completely() -> None:
    """Three jurors, one answer: `1 - δ` is 1.0 for every pair there is."""
    assert measured((SENT,), (SENT,), (SENT,)).self_agreement == pytest.approx(1.0)


def test_a_split_panel_is_the_mean_over_its_pairs_and_not_over_its_jurors() -> None:
    """Two jurors of three agree: one pair of the three scores 1.0 and the other two score 0.0."""
    scores = measured((SENT,), (SENT,), (LOOKED_UP,))

    assert scores.self_agreement == pytest.approx(1.0 / 3.0)


def test_the_label_number_is_over_the_votes_and_the_label_they_were_cast_on() -> None:
    """A panel that agrees with itself and not with the label is the case triage exists for."""
    scores = measured((LOOKED_UP,), (LOOKED_UP,))

    assert scores.self_agreement == pytest.approx(1.0)
    assert scores.label_agreement == pytest.approx(0.0)


def test_a_near_miss_scores_above_a_wrong_tool() -> None:
    """§ *The answer, and the three operations over it*: δ is soft, so *right tool, one argument
    wrong* is not *wrong tool*. A verdict count would rank them identically and put both in one
    bucket."""
    near = measured((SENT_NEARLY,)).label_agreement
    wrong = measured((LOOKED_UP,)).label_agreement

    assert near == pytest.approx(0.5)
    assert wrong == pytest.approx(0.0)
    assert near > wrong


def test_an_invalid_vote_is_not_measured() -> None:
    """A distance to a point outside the answer space is evidence about the plumbing, and
    `invalid_votes` already carries that. One valid vote is left, and it matches the label."""
    scores = measured((SENT,), (BARE,), (BARE,))

    assert scores.label_agreement == pytest.approx(1.0)


# --- absent evidence, which is where a NaN would have come from ---


def test_a_panel_of_one_does_not_read_as_unanimous() -> None:
    """No pair, no evidence of agreement. `1.0` here is a broken panel wearing a confident
    record's clothes, and it is `triage` that would then route it away from a person."""
    assert measured((SENT,)).self_agreement == pytest.approx(0.0)


def test_a_panel_with_no_usable_vote_scores_zero_rather_than_nothing() -> None:
    """A mean over an empty sequence is the other way this stage could have produced `NaN`."""
    scores = measured((BARE,))

    assert (scores.self_agreement, scores.label_agreement) == (0.0, 0.0)


def test_a_failed_panel_is_measured_rather_than_skipped() -> None:
    """The precondition is the key, not what is in it: `jury` wrote one, so there is a record
    with no evidence and it carries `0.0` into a bucket instead of an absence."""
    scores = measured()

    assert (scores.self_agreement, scores.label_agreement) == (0.0, 0.0)


def test_the_empty_answer_population_produces_no_nan() -> None:
    """`δ(∅, ∅) = 0` is load-bearing rather than tidy: the empty answer is a large share of a
    real corpus, and a jury that agreed to call nothing on a record labelled *call nothing*
    agrees completely."""
    scores = measured((), (), record=a_record(label=()))

    assert scores.self_agreement == pytest.approx(1.0)
    assert scores.label_agreement == pytest.approx(1.0)


# --- the precondition, and what makes re-running free ---


def test_a_record_the_jury_skipped_is_skipped_here_too() -> None:
    """§ *Per-service contracts*: `ai_review.jury` is absent, so there is nothing to fold."""
    engine = an_engine_that(a_panel_of((SENT,)))
    before = judged(a_record(tools=[]), engine=engine)[0]
    after = cohesion(engine, [before]).records[0]

    assert after.ai_review.cohesion is None
    assert after.model_dump() == before.model_dump()


def test_the_method_is_recorded_so_two_runs_can_be_compared() -> None:
    """A change to what these numbers mean changes this string, which is what it is for."""
    assert measured((SENT,), (TICKETED,)).method == METHOD


def test_running_it_twice_writes_the_same_two_numbers() -> None:
    """Requirement 25: re-running costs nothing, which is only true if it changes nothing."""
    engine = an_engine_that(a_panel_of((SENT,), (LOOKED_UP,)))
    once = cohesion(engine, judged(a_record(), engine=engine)).records
    twice = cohesion(engine, once).records

    assert twice[0].model_dump() == once[0].model_dump()


def test_it_makes_no_model_call() -> None:
    """Requirement 25 in the form a test can hold: the panel is not asked a second time."""
    panel = a_panel_of((SENT,))
    engine = an_engine_that(panel)
    given = judged(a_record(), engine=engine)
    asked = len(panel.asked)
    cohesion(engine, given)

    assert len(panel.asked) == asked
