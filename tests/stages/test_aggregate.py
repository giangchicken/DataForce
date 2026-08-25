"""T25 · aggregate: an overlap becomes one verdict, a confidence and an agreement statistic.

The records reach this stage through the real `question_generate`, `publish` and
`annotator_answers`, because what is folded here is what people actually said and a hand-written
`AnnotatorResponse` would let this module and the profile agree about a correction by luck.

**α is hand-worked, not sampled.** Four small cases with arithmetic anyone can redo on paper —
unanimous, chance, systematic disagreement, and one unit — because a statistic nobody can check by
hand is a statistic nobody notices going wrong. The numbers below are the formula's, not this
implementation's.

Every fixture is invented (AGENTS.md §9).
"""

from dataclasses import replace

import pytest

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.human_review.aggregate import (
    METHOD,
    aggregate,
    krippendorff_alpha,
)
from dataforce.pipeline.human_review.annotator_answers import annotator_answers
from dataforce.pipeline.human_review.publish import publish
from dataforce.record import OverlapVerdict, Record

from .test_annotator_answers import an_annotation_of, an_engine_reading, store_of
from .test_label_check import written_paths
from .test_question_generate import asked
from .test_tool_decision import LOOKED_UP, SENT, a_record
from .test_triage import thresholds

# A correction naming the same tool with one argument different: δ puts it near, not far.
SENT_NEARLY = [
    '{"SendStatement": {"ma_khach": "480215", "ky": "thang_truoc"}}',
]
# A correction naming a different tool entirely.
LOOKED_UP_INSTEAD = ['{"LookupBalance": {"ma_khach": "480215"}}']


def an_engine_folding(overlap_floor: int = 1) -> Engine:
    """The engine all eight stages are handed, with the rung's overlap declared."""
    engine = an_engine_reading()
    declared = dict(thresholds()["thresholds"])
    declared["aggregate"] = {"overlap_floor": overlap_floor}
    return replace(engine, thresholds={"thresholds": declared})


def folded(
    engine: Engine, *annotations: object, record: Record | None = None
) -> Record:
    """One record published, answered by those annotations, read back and folded."""
    published = publish(engine, asked(engine, record or a_record())).records
    question_id = published[0].human_review.publish.stored[0]  # type: ignore[union-attr]
    store_of(engine).answers.extend(
        making(question_id)  # type: ignore[operator]
        for making in annotations
    )
    read = annotator_answers(engine, published).records
    return aggregate(engine, read).records[0]


def saying(**controls: object) -> object:
    """One annotation waiting for the `question_id` it answers."""
    return lambda question_id: an_annotation_of(question_id, **controls)


def by(annotator_id: str, **controls: object) -> object:
    """The same, from a named annotator."""
    return lambda question_id: an_annotation_of(
        question_id, annotator_id=annotator_id, **controls
    )


def verdict_of(record: Record) -> OverlapVerdict:
    """What this stage wrote on the record."""
    written = record.human_review.aggregate

    assert written is not None
    return written


# --- the key it owns ---


def test_an_answered_record_gains_exactly_one_key() -> None:
    """I8 at this stage: the verdict is written and nothing else on the record moves."""
    engine = an_engine_folding()
    published = publish(engine, asked(engine, a_record())).records
    store_of(engine).answers.append(
        an_annotation_of(published[0].human_review.publish.stored[0])  # type: ignore[union-attr]
    )
    read = annotator_answers(engine, published).records

    written = aggregate(engine, read).records

    assert written_paths(read[0].model_dump(), written[0].model_dump()) == {
        "human_review.aggregate"
    }


def test_the_verdict_is_what_most_of_them_said() -> None:
    """A count and not a δ fold: the verdicts are an enum and there is no *nearly correct*."""
    written = folded(
        an_engine_folding(),
        by("u_1", verdict=["correct"]),
        by("u_2", verdict=["correct"]),
        by("u_3", verdict=["incorrect"]),
    )

    assert verdict_of(written).verdict == "correct"
    assert verdict_of(written).overlap == 3


def test_a_tie_goes_to_whoever_answered_first() -> None:
    """Two people, two verdicts: something has to be written, and order is the only tiebreak there is."""
    written = folded(
        an_engine_folding(),
        by("u_1", verdict=["incorrect"]),
        by("u_2", verdict=["correct"]),
    )

    assert verdict_of(written).verdict == "incorrect"


def test_the_estimator_is_named_on_the_record() -> None:
    """What makes two runs comparable, and tells two numbers apart from two measurements."""
    assert verdict_of(folded(an_engine_folding(), saying())).method == METHOD


# --- confidence, which is where δ is used ---


def test_two_people_who_said_the_same_thing_agree_completely() -> None:
    """Same verdict, same correction: nothing between them."""
    written = folded(an_engine_folding(), by("u_1"), by("u_2"))

    assert verdict_of(written).confidence == 1.0


def test_two_people_who_disagreed_about_the_verdict_agree_about_nothing() -> None:
    """The verdicts are apart, so nothing below them is asked."""
    written = folded(
        an_engine_folding(),
        by("u_1", verdict=["correct"]),
        by("u_2", verdict=["incorrect"]),
    )

    assert verdict_of(written).confidence == 0.0


def test_a_near_miss_scores_above_a_different_tool() -> None:
    """Requirement 34's acceptance: agreement is the profile's δ, not string equality.

    String equality would score both of these zero. δ is name-first, so naming a different tool
    *is* complete disagreement, and naming the same one with one argument different is not.
    """
    engine, other = an_engine_folding(), an_engine_folding()

    near = folded(engine, by("u_1"), by("u_2", corrected_arguments=SENT_NEARLY))
    far = folded(
        other,
        by("u_1"),
        by(
            "u_2",
            corrected_names=["LookupBalance"],
            corrected_arguments=LOOKED_UP_INSTEAD,
        ),
    )

    assert verdict_of(far).confidence == 0.0
    assert 0.0 < verdict_of(near).confidence < 1.0


def test_one_answer_is_not_a_corroborated_one() -> None:
    """`cohesion`'s rule: absent evidence reads as absent agreement, and `overlap` says which."""
    written = folded(an_engine_folding(), saying())

    assert verdict_of(written).confidence == 0.0
    assert verdict_of(written).overlap == 1


# --- Krippendorff's α, hand-worked ---


def test_a_corpus_nobody_disagreed_about_scores_one() -> None:
    """Observed disagreement is zero and so is expected: α is 1, not undefined."""
    assert krippendorff_alpha([["correct", "correct"], ["correct", "correct"]]) == 1.0


def test_two_units_agreeing_on_different_values_still_score_one() -> None:
    """Every pair inside a unit agrees; that the units differ is what α wants them to."""
    assert krippendorff_alpha([["correct", "correct"], ["unsure", "unsure"]]) == 1.0


def test_one_disagreeing_unit_in_two_scores_chance() -> None:
    """n=4, three `correct` and one `incorrect`: 1 - 3·2/6 = 0, which is chance exactly."""
    assert krippendorff_alpha([["correct", "correct"], ["correct", "incorrect"]]) == 0.0


def test_units_that_always_disagree_score_below_chance() -> None:
    """n=4, two of each, every pair split: 1 - 3·4/8 = -0.5. Systematic, not random."""
    assert (
        krippendorff_alpha([["correct", "incorrect"], ["correct", "incorrect"]]) == -0.5
    )


def test_a_unit_of_one_measures_nothing() -> None:
    """One value has nothing to disagree with, so it is not a unit α can use."""
    assert krippendorff_alpha([["correct"], ["incorrect"]]) == 0.0
    assert krippendorff_alpha([]) == 0.0


def test_alpha_is_the_batch_and_the_same_on_every_record_of_it() -> None:
    """A corpus statistic, on the record because the records are the report."""
    engine = an_engine_folding()
    published = publish(engine, asked(engine, a_record())).records
    question_id = published[0].human_review.publish.stored[0]  # type: ignore[union-attr]
    store_of(engine).answers.extend(
        [
            an_annotation_of(question_id, annotator_id="u_1"),
            an_annotation_of(question_id, annotator_id="u_2"),
        ]
    )
    read = annotator_answers(engine, published).records

    written = aggregate(engine, read).records

    assert verdict_of(written[0]).alpha == 1.0


def test_a_record_answered_once_carries_the_alpha_of_a_corpus_of_one() -> None:
    """Stated rather than hidden: α is the batch's, and a batch with no measurable unit is 0.0."""
    assert verdict_of(folded(an_engine_folding(), saying())).alpha == 0.0


# --- the floor ---


def test_a_record_under_the_floor_keeps_its_answers_and_gets_no_verdict() -> None:
    """Raising the floor loses nothing: the next run with more answers folds them."""
    engine = an_engine_folding(overlap_floor=2)

    written = folded(engine, saying())

    assert written.human_review.aggregate is None
    assert written.human_review.annotator_answers is not None


def test_a_record_that_meets_the_floor_is_folded() -> None:
    """The same corpus, one answer more."""
    written = folded(an_engine_folding(overlap_floor=2), by("u_1"), by("u_2"))

    assert verdict_of(written).overlap == 2


def test_a_record_nobody_answered_gets_no_verdict() -> None:
    """The precondition: absent and empty are one fact, which is *nobody has answered*."""
    engine = an_engine_folding()

    written = aggregate(engine, [a_record()]).records

    assert written[0].human_review.aggregate is None


def test_every_record_comes_back_whether_it_was_folded_or_not() -> None:
    """I11: a skip is a record with no key, never a shorter list."""
    engine = an_engine_folding(overlap_floor=2)

    written = aggregate(engine, [a_record(), a_record(label=(LOOKED_UP,))]).records

    assert len(written) == 2


def test_a_floor_that_is_not_a_count_stops_the_run() -> None:
    """P23: read before the first record, because it is a fact about the configuration."""
    engine = replace(
        an_engine_folding(),
        thresholds={"thresholds": {"aggregate": {"overlap_floor": 0}}},
    )

    with pytest.raises(ConfigError, match="overlap_floor"):
        aggregate(engine, [a_record()])


def test_a_floor_declared_true_is_not_a_floor_of_one() -> None:
    """`True` is an `int` in Python, which is the coercion `declared_ratio` was taught to refuse."""
    engine = replace(
        an_engine_folding(),
        thresholds={"thresholds": {"aggregate": {"overlap_floor": True}}},
    )

    with pytest.raises(ConfigError, match="overlap_floor"):
        aggregate(engine, [a_record()])


def test_the_params_file_this_repository_ships_declares_a_floor() -> None:
    """P31: the shipped declaration is read by the reader that refuses a bad one."""
    from pathlib import Path

    from agent_toolkit.file_utils import read_yaml

    shipped = read_yaml(Path(__file__).resolve().parents[2] / "params.yaml")

    assert shipped["thresholds"]["aggregate"]["overlap_floor"] >= 1


def test_the_correction_is_read_back_as_the_answer_that_went_in() -> None:
    """The fold does not touch a correction; it only measures how far two of them are apart."""
    written = folded(an_engine_folding(), by("u_1"), by("u_2"))

    responses = written.human_review.annotator_answers
    assert responses is not None
    assert [said.corrected_value for said in responses.responses] == [(SENT,), (SENT,)]
