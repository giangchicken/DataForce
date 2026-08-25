"""T22 · question_generate: one question per flagged record, and the id it is joined on forever.

The records reach this stage through the real `label_check`, `jury`, `cohesion` and `triage`,
because *which records get a question* is a fact about all four and a hand-written
`ReviewSelection` would let this module and `triage` agree about the flag by luck. It also puts the
Requirement 30 test on a record that has real model output on it to leak.

**The identity tests are the load-bearing ones.** A `question_id` is what the store's unique
constraint is on, so an id that moves when nothing changed republishes a question a person has
already answered, and an id that does not move when the words changed hides the new wording behind
a no-op. Both directions are asserted here, because neither shows up until a store exists.

Every fixture is invented (AGENTS.md §9).
"""

from dataclasses import replace

from dataforce.engine import Engine
from dataforce.pipeline.ai_review.triage import CELLS
from dataforce.pipeline.human_review.question_generate import (
    ID_LENGTH,
    ID_PREFIX,
    QUESTION_NAME,
    question_generate,
    question_id_for,
)
from dataforce.record import HumanReview, Question, Record

from .test_label_check import written_paths
from .test_tool_decision import (
    LOOKED_UP,
    QUESTION,
    SENT,
    TURNS,
    a_profile,
    a_record,
    parts,
)
from .test_triage import an_engine_that, sorted_through

# Nothing is sampled: the quota reaches every record, so a test measures the flag and not the draw.
NOTHING = {cell: {"stratum": "flagged", "quota": 0.0} for cell in CELLS.values()}

# The panel that agrees with the label, which is the ordinary case a question is asked about.
AGREEING = ((SENT,), (SENT,))


def an_engine_asking(*, question: str = QUESTION, **declared: object) -> Engine:
    """The engine all five stages are handed, with the words the edge read for the question."""
    engine = an_engine_that(*AGREEING, **declared)
    return replace(engine, profile=a_profile(question=question))


def another_record() -> Record:
    """A second record with content of its own: `record_id` is over content, so a differing label
    is the same record. Its own last turn asks for a different statement, and its label still
    restates what the conversation asked for, so `label_check` passes it through."""
    return a_record(
        content=parts((*TURNS[:3], ("user", "Gửi sao kê tháng trước nhé.")))
    )


def asked(engine: Engine, *records: Record) -> tuple[Record, ...]:
    """Records through every stage that has to run before this one, and then through it."""
    return question_generate(engine, sorted_through(engine, *records)).records


def questions_of(record: Record) -> tuple[Question, ...]:
    """What this stage wrote on the record."""
    written = record.human_review.question_generate

    assert written is not None
    return written


def the_question(engine: Engine, record: Record | None = None) -> Question:
    """The one question asked about one record."""
    return questions_of(asked(engine, record if record is not None else a_record())[0])[
        0
    ]


# --- the stage's three promises ---


def test_a_flagged_record_gains_exactly_one_key() -> None:
    """I8 at this stage: the question is written and nothing else on the record moves."""
    engine = an_engine_asking()
    placed = sorted_through(engine, a_record())

    written = question_generate(engine, placed).records

    assert written_paths(placed[0].model_dump(), written[0].model_dump()) == {
        "human_review.question_generate"
    }


def test_one_question_is_asked_about_one_record() -> None:
    """Requirement 29, as the count: the key is a list and this profile fills one seat of it."""
    assert len(questions_of(asked(an_engine_asking(), a_record())[0])) == 1


def test_the_question_is_the_words_the_edge_read() -> None:
    """The profile's `question_text`, unedited: this stage picks no words of its own."""
    assert the_question(an_engine_asking()).content == QUESTION


def test_the_permitted_answers_are_the_profiles_capture_half() -> None:
    """`enum` is a copy of one declaration, so the record stays legible against a past answer."""
    engine = an_engine_asking()

    assert (
        the_question(engine).enum == engine.profile.answer_config(a_record()).verdicts
    )


def test_free_text_is_not_a_permitted_answer() -> None:
    """The record's own words for `enum`, asserted rather than trusted: every answer is named."""
    assert all(answer.strip() for answer in the_question(an_engine_asking()).enum)


# --- what it skips, and what it hands on regardless ---


def test_a_record_the_quota_did_not_reach_gets_no_question() -> None:
    """The precondition is the flag: `triage` placed this record and did not select it."""
    written = asked(an_engine_asking(buckets=NOTHING), a_record())[0]

    assert written.ai_review.triage is not None
    assert not written.ai_review.triage.selected_for_review
    assert written.human_review.question_generate is None


def test_a_record_that_never_reached_triage_gets_no_question() -> None:
    """Two absences, one skip: nothing placed it, so nothing said a person should see it."""
    engine = an_engine_asking()

    written = question_generate(engine, [a_record()]).records

    assert written[0].ai_review.triage is None
    assert written[0].human_review.question_generate is None


def test_every_record_comes_back_whether_it_was_asked_about_or_not() -> None:
    """I11: a skip is a record with no key, never a shorter list."""
    engine = an_engine_asking(buckets=NOTHING)
    corpus = (a_record(), another_record())

    written = asked(engine, *corpus)

    assert [record.record_id for record in written] == [
        record.record_id for record in corpus
    ]


def test_a_key_a_previous_run_wrote_is_replaced_and_not_appended() -> None:
    """Re-running the stage over its own output writes one question, not two."""
    engine = an_engine_asking()
    once = asked(engine, a_record())

    twice = question_generate(engine, once).records

    assert len(questions_of(twice[0])) == 1
    assert questions_of(twice[0]) == questions_of(once[0])


# --- the id: what it covers, and what it must not move for ---


def test_an_id_is_the_prefix_and_sixteen_hex() -> None:
    """A question id is read by people, in a store row and in a task payload."""
    minted = the_question(an_engine_asking()).question_id

    assert minted.startswith(ID_PREFIX)
    digest = minted.removeprefix(ID_PREFIX)
    assert len(digest) == ID_LENGTH
    assert set(digest) <= set("0123456789abcdef")


def test_the_same_question_mints_the_same_id_on_a_second_run() -> None:
    """Requirement 23: two runs over one corpus publish once, because the id did not move."""
    engine = an_engine_asking()

    assert the_question(engine).question_id == the_question(engine).question_id


def test_two_records_get_two_ids() -> None:
    """The record is in the id, so one question about two records is two questions."""
    engine = an_engine_asking()
    corpus = (a_record(), another_record())

    written = asked(engine, *corpus)

    assert corpus[0].record_id != corpus[1].record_id
    assert (
        questions_of(written[0])[0].question_id
        != questions_of(written[1])[0].question_id
    )


def test_rewording_the_question_mints_a_new_id() -> None:
    """The one the store cannot catch: an id that stayed would hide the rewording behind a no-op."""
    asked_one_way = the_question(an_engine_asking())
    asked_another = the_question(an_engine_asking(question="Tool nào đúng?"))

    assert asked_one_way.content != asked_another.content
    assert asked_one_way.question_id != asked_another.question_id


def test_changing_the_permitted_answers_mints_a_new_id() -> None:
    """A question offering a fourth verdict is a different question, even in the same words."""
    three = question_id_for(
        "3f9a1c0b7e4d2856", QUESTION_NAME, QUESTION, ("a", "b", "c")
    )
    four = question_id_for(
        "3f9a1c0b7e4d2856", QUESTION_NAME, QUESTION, ("a", "b", "c", "d")
    )

    assert three != four


def test_the_name_of_the_question_is_in_its_id() -> None:
    """What a second *kind* of question about one record would differ by."""
    one = question_id_for("3f9a1c0b7e4d2856", QUESTION_NAME, QUESTION, ())
    another = question_id_for("3f9a1c0b7e4d2856", "arguments_are_right", QUESTION, ())

    assert one != another


# --- Requirement 30 / I12, at the stage that mints the question ---


def test_nothing_the_panel_or_the_triage_said_reaches_the_question() -> None:
    """No model output may reach an annotator, asserted where the words are chosen.

    The panel here disagrees with the label, so the record carries a plurality, two agreement
    figures and a bucket -- every one of which is a string or a number this stage could have put in
    a question, and none of which appears in one.
    """
    engine = an_engine_asking()
    written = asked(engine, a_record(label=(LOOKED_UP,)))[0]
    said = written.ai_review

    assert said.jury is not None and said.cohesion is not None
    assert said.triage is not None
    printed = questions_of(written)[0].model_dump_json()
    for model_output in (
        said.triage.bucket,
        said.triage.stratum,
        said.triage.reason,
        said.jury.llm_votes[0].model_name,
        said.jury.llm_votes[0].reasoning,
        str(SENT["name"]),
        str(said.cohesion.self_agreement),
        said.cohesion.method,
    ):
        assert model_output not in printed


def test_the_question_holds_nothing_the_record_does_not_already_carry() -> None:
    """The other half: the payload is composed at `publish`, so `HumanReview` gains one key."""
    engine = an_engine_asking()
    written = asked(engine, a_record())[0]

    assert written.human_review == HumanReview(
        question_generate=questions_of(written),
    )
