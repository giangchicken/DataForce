"""T25 · curate: the verdict becomes the label that ships, or says nobody could decide.

The records reach this stage through every stage of the phase, because what curate decides is what
people said and a hand-written `OverlapVerdict` would let this module and `aggregate` agree about a
verdict string by luck.

**The three statuses are the three tests that matter.** `original` is the label standing, `corrected`
is it being replaced by something a majority of the annotators named, and `unresolved` is every way
of not being able to say — a verdict of *unsure*, a correction nobody agreed on, and Requirement
49's malformed one, which all arrive here by different routes and must all leave by the same one.

Every fixture is invented (AGENTS.md §9).
"""

from dataforce.engine import Engine
from dataforce.pipeline.human_review.aggregate import aggregate
from dataforce.pipeline.human_review.curate import curate
from dataforce.record import FinalLabel, Record

from .test_aggregate import LATER, an_engine_folding, by, folded
from .test_label_check import written_paths
from .test_tool_decision import LOOKED_UP, SENT, TICKETED, a_record

# Two annotators typing the same correction, which is what a strict majority per tool name needs.
BOTH_SAY_LOOKUP = ['{"LookupBalance": {"ma_khach": "480215"}}']
# A correction that calls nothing at all: a real answer, and the one `()` vs `None` is about.
CALL_NOTHING: list[str] = ["{}"]


def curated(
    engine: Engine, *annotations: object, record: Record | None = None
) -> Record:
    """One record through the whole phase, and then through this stage."""
    return curate(engine, [folded(engine, *annotations, record=record)]).records[0]


def label_of(record: Record) -> FinalLabel:
    """What this stage wrote on the record."""
    written = record.human_review.curate

    assert written is not None
    return written


# --- the key it owns ---


def test_a_record_with_a_verdict_gains_exactly_one_key() -> None:
    """I8 at this stage: the final label is written and nothing else on the record moves."""
    engine = an_engine_folding()
    folded_record = folded(engine, by("u_1"))

    written = curate(engine, [folded_record]).records

    assert written_paths(folded_record.model_dump(), written[0].model_dump()) == {
        "human_review.curate"
    }


def test_who_decided_it_and_when_come_off_the_answers() -> None:
    """No engine module holds a clock (I1): *when it was decided* is when the last person submitted."""
    engine = an_engine_folding()

    written = curated(engine, by("u_1"), by("u_2"))

    responses = written.human_review.annotator_answers
    assert responses is not None
    assert label_of(written).validators == ("u_1", "u_2")
    assert label_of(written).decided_at == max(
        said.submitted_at for said in responses.responses
    )


def test_one_person_answering_twice_is_one_validator() -> None:
    """De-duplicated in the order they came back: a validator is a person, not an answer."""
    written = curated(an_engine_folding(), by("u_1"), by("u_1", verdict=["correct"]))

    assert label_of(written).validators == ("u_1",)


# --- the label stands ---


def test_a_verdict_that_endorses_the_label_ships_the_label() -> None:
    """Which verdict means that is the capture half's to declare, not this module's to name."""
    written = curated(an_engine_folding(), by("u_1", verdict=["correct"]))

    assert label_of(written).status == "original"
    assert label_of(written).label == (SENT,)


# --- the label is replaced ---


def test_a_correction_a_majority_named_becomes_the_label() -> None:
    """`vote_consensus` needs a strict majority per tool name; at an overlap of two, both."""
    written = curated(
        an_engine_folding(),
        by(
            "u_1",
            corrected_names=["LookupBalance"],
            corrected_arguments=BOTH_SAY_LOOKUP,
        ),
        by(
            "u_2",
            corrected_names=["LookupBalance"],
            corrected_arguments=BOTH_SAY_LOOKUP,
        ),
    )

    assert label_of(written).status == "corrected"
    assert label_of(written).label == (LOOKED_UP,)


def test_one_annotator_correcting_alone_is_still_a_majority_of_one() -> None:
    """Whether one person is enough is the overlap floor's question, and it was met."""
    written = curated(an_engine_folding(), by("u_1"))

    assert label_of(written).status == "corrected"
    assert label_of(written).label == (SENT,)


def test_a_correction_of_calling_nothing_is_a_correction() -> None:
    """`()` is *call nothing* and `None` is *nothing defensible*; testing for truth would merge them."""
    written = curated(
        an_engine_folding(),
        by("u_1", corrected_names=[], corrected_arguments=CALL_NOTHING),
    )

    assert label_of(written).status == "corrected"
    assert label_of(written).label == ()


def test_the_final_label_validates_against_the_records_answer_space() -> None:
    """T25's acceptance criterion, on the answer that actually ships.

    Two calls, and they come back in the profile's own order rather than the annotator's: the
    consensus is built per tool name, sorted. δ is over the *set* of names, so nothing downstream
    can tell the two orderings apart — but `==` on the stored form can, which is why it is stated.
    """
    engine = an_engine_folding()
    written = curated(
        engine,
        by(
            "u_1",
            corrected_names=["SendStatement", "OpenTicket"],
            corrected_arguments=[
                '{"SendStatement": {"ma_khach": "480215", "ky": "thang_nay"},'
                ' "OpenTicket": {"noi_dung": "khách cần hỗ trợ"}}'
            ],
        ),
    )

    assert label_of(written).label == (TICKETED, SENT)
    assert engine.profile.answer_is_permitted(label_of(written).label, written)


def test_one_person_cannot_outvote_another_by_answering_twice() -> None:
    """`vote_consensus` needs a strict majority per tool name, and two rows from one person is one.

    Undeduplicated this is three votes with `LookupBalance` in two of them — a majority, and a
    label shipped on one annotator's say-so against another's.
    """
    written = curated(
        an_engine_folding(),
        by(
            "u_1",
            corrected_names=["LookupBalance"],
            corrected_arguments=BOTH_SAY_LOOKUP,
        ),
        by(
            "u_1",
            corrected_names=["LookupBalance"],
            corrected_arguments=BOTH_SAY_LOOKUP,
            submitted_at=LATER,
        ),
        by("u_2"),
    )

    assert label_of(written).status == "unresolved"
    assert label_of(written).validators == ("u_1", "u_2")


# --- nobody could decide ---


def test_a_verdict_of_unsure_is_unresolved() -> None:
    """*Unsure* is a real answer and not a skip, and what it answers is *I cannot say*."""
    written = curated(an_engine_folding(), by("u_1", verdict=["unsure"]))

    assert label_of(written).status == "unresolved"
    assert label_of(written).label == (SENT,)


def test_a_malformed_correction_is_unresolved_and_never_coerced() -> None:
    """Requirement 49 arriving here: the correction did not validate, so there is nothing to ship."""
    written = curated(
        an_engine_folding(), by("u_1", corrected_arguments=['{"SendStatement": '])
    )

    assert label_of(written).status == "unresolved"
    assert label_of(written).label == (SENT,)


def test_two_annotators_naming_different_tools_are_unresolved() -> None:
    """No strict majority for either name, so neither is defensible and a person is needed."""
    written = curated(
        an_engine_folding(),
        by("u_1"),
        by(
            "u_2",
            corrected_names=["LookupBalance"],
            corrected_arguments=BOTH_SAY_LOOKUP,
        ),
    )

    assert label_of(written).status == "unresolved"


def test_nothing_adjudicates_yet_and_the_field_says_so() -> None:
    """A gap rather than a design: a disagreement is unresolved and goes back to a person."""
    written = curated(an_engine_folding(), by("u_1"), by("u_2", verdict=["unsure"]))

    assert label_of(written).adjudicated_by is None


# --- what it skips ---


def test_a_record_with_no_verdict_gets_no_final_label() -> None:
    """The precondition, which is `aggregate`'s key and nothing else."""
    engine = an_engine_folding()

    written = curate(engine, [a_record()]).records

    assert written[0].human_review.curate is None


def test_a_verdict_with_no_answers_under_it_is_not_curated() -> None:
    """Unreachable through the flow and reachable through a hand-made body; the clock has no value."""
    engine = an_engine_folding()
    hollow = folded(engine, by("u_1"))
    hollow = hollow.model_copy(
        update={
            "human_review": hollow.human_review.model_copy(
                update={"annotator_answers": None}
            )
        }
    )

    written = curate(engine, [hollow]).records

    assert written[0].human_review.aggregate is not None
    assert written[0].human_review.curate is None


def test_every_record_comes_back_whether_it_was_curated_or_not() -> None:
    """I11: a skip is a record with no key, never a shorter list."""
    engine = an_engine_folding()

    written = curate(engine, [folded(engine, by("u_1")), a_record()]).records

    assert len(written) == 2
    assert written[1].human_review.curate is None


def test_running_it_twice_writes_the_same_label() -> None:
    """Arithmetic over what is already on the record: re-running is free and changes nothing."""
    engine = an_engine_folding()
    once = curated(engine, by("u_1"))

    twice = curate(engine, [once]).records[0]

    assert label_of(twice) == label_of(once)


def test_the_phase_runs_end_to_end_in_the_flows_order() -> None:
    """Every stage of `human_review`, over one record, ending in a label that ships."""
    engine = an_engine_folding()

    written = curated(engine, by("u_1", verdict=["correct"]))

    said = written.human_review
    assert said.question_generate and said.publish and said.annotator_answers
    assert said.aggregate and said.curate
    assert aggregate(engine, [written]).records[0].human_review.curate is not None
