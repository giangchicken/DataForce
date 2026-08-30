"""T24 · annotator_answers: what people said, read back out of the store and onto the record.

The records reach this stage through the real `question_generate` and `publish`, because what can
be answered is what was published and the join is the `question_id` those two minted between them.

**I18 round-trips here, end to end.** `test_publish.py` asserts what crosses to the store;
`test_tool_decision.py` asserts the capture half's inverse on a synthetic `result`. This file puts
the two together — a config and payload composed for a fixture, an annotation fed back in Label
Studio's shape, and the answer that comes out is the one that went in.

Every fixture is invented.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.human_review.annotator_answers import annotator_answers
from dataforce.pipeline.human_review.publish import publish
from dataforce.ports import QuestionToStore, StoredAnnotation, StoreReceipt
from dataforce.record import AnnotatorResponse, Record, ReturnedAnswers

from .test_label_check import written_paths
from .test_publish import AStore, an_engine_publishing, receipt_of
from .test_question_generate import asked
from .test_tool_decision import SENT, TICKETED, a_record, an_annotation

ANSWERED_AT = datetime(2026, 8, 25, 14, 5, tzinfo=UTC)


class AnAnsweredStore(AStore):
    """A `QuestionStore` that also holds answers, keyed by the question they answer.

    Subclassing the publish double rather than writing a second one: what a test here needs is the
    *same* store the questions went into, because the join is the id `publish` recorded.
    """

    def __init__(self) -> None:
        super().__init__()
        self.answers: list[StoredAnnotation] = []
        self.asked_about: list[tuple[str, ...]] = []

    def answers_to(self, question_ids: Sequence[str]) -> Sequence[StoredAnnotation]:
        self.asked_about.append(tuple(question_ids))
        wanted = set(question_ids)
        return [answer for answer in self.answers if answer.question_id in wanted]


def an_annotation_of(
    question_id: str,
    *,
    annotator_id: str = "u_14",
    was_skipped: bool = False,
    submitted_at: datetime = ANSWERED_AT,
    **controls: Any,
) -> StoredAnnotation:
    """One answer as the store holds it: the control values verbatim, and the tool's envelope.

    `answer_id` carries the clock as well as the answerer, because the store's key is per *answer*
    and a person answering twice about one question is two rows there — which is the whole of what
    `aggregate.one_answer_each` is about.
    """
    return StoredAnnotation(
        answer_id=f"a_{annotator_id}_{question_id}_{int(submitted_at.timestamp())}",
        question_id=question_id,
        annotator_id=annotator_id,
        result=tuple(an_annotation(**controls)),
        was_skipped=was_skipped,
        lead_time_seconds=41.5,
        submitted_at=submitted_at,
    )


def an_engine_reading() -> Engine:
    """The engine all seven stages are handed, with a store that can hold answers too."""
    return replace(an_engine_publishing(), question_store=AnAnsweredStore())


def store_of(engine: Engine) -> AnAnsweredStore:
    """The double behind the port."""
    store = engine.question_store

    assert isinstance(store, AnAnsweredStore)
    return store


def answered(engine: Engine, *annotations: Any, record: Record | None = None) -> Record:
    """One record published, then answered by those annotations, then read back.

    The annotations are built here rather than passed in because they need the `question_id`
    `publish` recorded, which does not exist until it has run.
    """
    published = publish(engine, asked(engine, record or a_record())).records
    question_id = receipt_of(published[0]).stored[0]
    store_of(engine).answers.extend(
        making(question_id) for making in annotations or (an_annotation_of,)
    )
    return annotator_answers(engine, published).records[0]


def making(**controls: Any) -> Any:
    """An annotation waiting for the `question_id` it answers."""
    return lambda question_id: an_annotation_of(question_id, **controls)


def responses_of(record: Record) -> tuple[AnnotatorResponse, ...]:
    """What this stage wrote on the record."""
    written = record.human_review.annotator_answers

    assert written is not None
    return written.responses


# --- the key it owns ---


def test_an_answered_record_gains_exactly_one_key() -> None:
    """I8 at this stage: the answers are written and nothing else on the record moves."""
    engine = an_engine_reading()
    published = publish(engine, asked(engine, a_record())).records
    store_of(engine).answers.append(
        an_annotation_of(receipt_of(published[0]).stored[0])
    )

    written = annotator_answers(engine, published).records

    assert written_paths(published[0].model_dump(), written[0].model_dump()) == {
        "human_review.annotator_answers"
    }


def test_the_answer_lands_with_who_gave_it_and_when() -> None:
    """The envelope is the store's; the verdict and the correction are the profile's."""
    written = answered(an_engine_reading())

    said = responses_of(written)[0]
    assert said.annotator_id == "u_14"
    assert said.submitted_at == ANSWERED_AT
    assert said.question_id == written.human_review.publish.stored[0]  # type: ignore[union-attr]


def test_two_annotators_answering_one_question_are_two_responses() -> None:
    """The overlap `aggregate` folds: one question, as many answers as the rung asked for."""
    engine = an_engine_reading()

    written = answered(
        engine,
        making(),
        lambda question_id: an_annotation_of(question_id, annotator_id="u_15"),
    )

    assert {said.annotator_id for said in responses_of(written)} == {"u_14", "u_15"}


# --- what the profile decides, and this stage does not ---


def test_the_verdict_is_the_one_the_annotator_chose() -> None:
    """This stage names no verdict value: it copies what the capture half's inverse read."""
    written = answered(an_engine_reading(), making(verdict=["correct"]))

    assert responses_of(written)[0].verdict == "correct"


def test_a_correction_comes_back_as_the_answer_that_went_in() -> None:
    """I18, end to end: composed, published, answered in Label Studio's shape, read back."""
    written = answered(an_engine_reading(), making(verdict=["incorrect"]))

    assert responses_of(written)[0].corrected_value == (SENT,)


def test_a_correction_that_does_not_validate_is_recorded_as_none() -> None:
    """Requirement 49: never coerced. What the person typed stays verbatim in the store."""
    engine = an_engine_reading()

    written = answered(engine, making(corrected_arguments=['{"SendStatement": ']))

    assert responses_of(written)[0].verdict == "incorrect"
    assert responses_of(written)[0].corrected_value is None
    assert store_of(engine).answers[0].result[2]["value"]["text"] == [
        '{"SendStatement": '
    ]


def test_a_verdict_of_correct_carries_no_correction() -> None:
    """The gate is `visibleWhen` in the config and the verdict in its inverse."""
    written = answered(an_engine_reading(), making(verdict=["correct"]))

    assert responses_of(written)[0].corrected_value is None


def test_the_note_reaches_the_record_unparsed() -> None:
    """Free text, and the record's own word for it is *never parsed*."""
    written = answered(an_engine_reading(), making(note=["Khách hỏi hai việc."]))

    assert responses_of(written)[0].note == "Khách hỏi hai việc."


def test_an_answer_naming_two_tools_is_read_as_two() -> None:
    """The correction is validated against this record's space, ceiling and all."""
    written = answered(
        an_engine_reading(),
        making(
            corrected_names=["SendStatement", "OpenTicket"],
            corrected_arguments=[
                '{"SendStatement": {"ma_khach": "480215", "ky": "thang_nay"},'
                ' "OpenTicket": {"noi_dung": "khách cần hỗ trợ"}}'
            ],
        ),
    )

    assert responses_of(written)[0].corrected_value == (SENT, TICKETED)


# --- a skip is not an answer (Requirement 50) ---


def test_a_skip_is_not_a_response() -> None:
    """The annotator saw the question and declined: evidence about the question, not the label."""
    written = answered(an_engine_reading(), making(was_skipped=True))

    assert responses_of(written) == ()


def test_a_record_whose_only_answer_was_a_skip_still_gets_the_key() -> None:
    """*Asked and declined* and *asked and waiting* are different, and the key is the difference."""
    written = answered(an_engine_reading(), making(was_skipped=True))

    assert written.human_review.annotator_answers == ReturnedAnswers(responses=())


def test_a_skip_beside_an_answer_leaves_the_answer() -> None:
    """One annotator declined and one did not; the overlap is one, not two and not none."""
    written = answered(
        an_engine_reading(),
        making(was_skipped=True),
        lambda question_id: an_annotation_of(
            question_id, annotator_id="u_15", was_skipped=False
        ),
    )

    assert [said.annotator_id for said in responses_of(written)] == ["u_15"]


def test_an_annotation_with_no_verdict_is_not_a_response() -> None:
    """`required="true"` means the tool refuses one, so a row without it is not an answer."""
    written = answered(an_engine_reading(), making(verdict=None))

    assert responses_of(written) == ()


# --- what it skips, and what stops it ---


def test_a_record_the_store_holds_no_answers_for_gets_no_key() -> None:
    """The precondition, and the difference from a record whose answers were all skips."""
    engine = an_engine_reading()
    published = publish(engine, asked(engine, a_record())).records

    written = annotator_answers(engine, published).records

    assert written[0].human_review.annotator_answers is None


def test_a_record_that_never_published_asks_the_store_nothing() -> None:
    """Two absences, one skip: a question never published cannot have been answered."""
    engine = an_engine_reading()

    written = annotator_answers(engine, [a_record()]).records

    assert written[0].human_review.annotator_answers is None
    assert store_of(engine).asked_about == []


def test_every_record_comes_back_whether_it_was_answered_or_not() -> None:
    """I11: a skip is a record with no key, never a shorter list."""
    engine = an_engine_reading()
    published = publish(engine, asked(engine, a_record())).records

    written = annotator_answers(engine, [*published, a_record()]).records

    assert len(written) == 2


def test_the_whole_batch_is_one_query() -> None:
    """A call per record is twenty thousand round trips for a phase with one question each."""
    engine = an_engine_reading()
    published = publish(engine, asked(engine, a_record())).records

    annotator_answers(engine, published)

    assert len(store_of(engine).asked_about) == 1


def test_an_engine_with_no_store_refuses_before_the_first_record() -> None:
    """Reading no answers from nowhere would write *nobody has answered* onto an unasked corpus."""
    engine = an_engine_reading()
    published = publish(engine, asked(engine, a_record())).records

    with pytest.raises(ConfigError, match="annotator_answers needs a question store"):
        annotator_answers(replace(engine, question_store=None), published)


def test_reading_twice_writes_the_same_answers() -> None:
    """Re-reading is free and idempotent, which is half of why this is not one stage with publish."""
    engine = an_engine_reading()
    once = answered(engine)

    twice = annotator_answers(engine, [once]).records[0]

    assert responses_of(twice) == responses_of(once)


# --- the real store, so the double is not the only thing the port describes ---


def test_answers_written_to_the_real_store_reach_the_record(sessions: Any) -> None:
    """The same stage, the same port, the other adapter — on both backends."""
    from dataforce.edge.store.models import AnnotatorAnswer
    from dataforce.edge.store.repository import SqlQuestionStore

    engine = replace(an_engine_reading(), question_store=SqlQuestionStore(sessions))
    published = publish(engine, asked(engine, a_record())).records
    question_id = receipt_of(published[0]).stored[0]
    with sessions.begin() as session:
        session.add(
            AnnotatorAnswer(
                answer_id="a_1",
                question_id=question_id,
                annotator_id="u_14",
                result=an_annotation(),
                was_skipped=False,
                lead_time_seconds=41.5,
                submitted_at=ANSWERED_AT,
                external_annotation_id="ls_88",
            )
        )

    written = annotator_answers(engine, published).records[0]

    assert responses_of(written)[0].corrected_value == (SENT,)
    assert responses_of(written)[0].submitted_at == ANSWERED_AT


def test_the_double_and_the_real_store_hand_back_one_shape() -> None:
    """Both return `StoredAnnotation`s, which is the only shape the stage can read."""
    engine = an_engine_reading()
    published = publish(engine, asked(engine, a_record())).records
    store_of(engine).answers.append(
        an_annotation_of(receipt_of(published[0]).stored[0])
    )

    handed = store_of(engine).answers_to(list(receipt_of(published[0]).stored))

    assert all(isinstance(answer, StoredAnnotation) for answer in handed)
    assert isinstance(store_of(engine).batches[0][0], QuestionToStore)
    assert isinstance(
        store_of(engine).stored_questions([]),
        StoreReceipt,
    )
