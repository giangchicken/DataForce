"""T24 · publish: the two config halves composed, and the questions handed across the port.

The records reach this stage through the real `label_check`, `jury`, `cohesion`, `triage` and
`question_generate`, because what gets published is what got asked and a hand-written `Question`
would let this module and `question_generate` agree about an id by luck.

**The store here is a second adapter, and that is what makes the seam real** (P20). `AStore` holds
its rows in a dict and records what crossed; `SqlQuestionStore` holds them in a database. The two
tests at the bottom run this stage against the real one, so *the two fit* is asserted rather than
assumed -- an in-memory double that agrees with nothing is how a port comes to describe only its
fake. They take `conftest.py`'s `sessions`, so they run on both backends like every store test.

Every fixture is invented (AGENTS.md §9).
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from dataforce.edge.store.repository import SqlQuestionStore
from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.human_review.publish import (
    QUESTION,
    QUESTION_ID,
    annotation_config,
    publish,
)
from dataforce.ports import QuestionToStore, StoredAnnotation, StoreReceipt
from dataforce.record import PublishedQuestions, Record

from .test_label_check import written_paths
from .test_question_generate import an_engine_asking, asked, questions_of
from .test_tool_decision import LOOKED_UP, a_record

# The stamps the double returns, so a test can assert what reached the record without a clock in it.
WROTE_AT = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
STORE_RUN = "sr_000000000000test"


class AStore:
    """A `QuestionStore` that holds its rows in a dict and remembers every call.

    It keeps the port's two promises and nothing else: a question already held is not written twice,
    and the receipt names every id in the batch whoever wrote it. The stamps are constants, because
    what a test of *this* stage asserts is that the store's stamps reach the record — not what a
    clock said while it ran.
    """

    def __init__(self) -> None:
        self.held: dict[str, QuestionToStore] = {}
        self.batches: list[tuple[QuestionToStore, ...]] = []

    def stored_questions(self, questions: Sequence[QuestionToStore]) -> StoreReceipt:
        self.batches.append(tuple(questions))
        for question in questions:
            self.held.setdefault(question.question_id, question)
        return StoreReceipt(
            stored=tuple(question.question_id for question in questions),
            store_run_id=STORE_RUN,
            published_at=WROTE_AT,
        )

    def answers_to(self, question_ids: Sequence[str]) -> Sequence[StoredAnnotation]:
        return ()


class AForgetfulStore(AStore):
    """A store that held fewer questions than it was handed, which the receipt is allowed to say."""

    def stored_questions(self, questions: Sequence[QuestionToStore]) -> StoreReceipt:
        super().stored_questions(questions)
        return StoreReceipt(stored=(), store_run_id=STORE_RUN, published_at=WROTE_AT)


def an_engine_publishing(store: AStore | None = None, **declared: object) -> Engine:
    """The engine all six stages are handed, with the store's port on it."""
    return replace(
        an_engine_asking(**declared), question_store=store if store else AStore()
    )


def published(engine: Engine, *records: Record) -> tuple[Record, ...]:
    """Records through every stage that has to run before this one, and then through it."""
    return publish(engine, asked(engine, *records)).records


def receipt_of(record: Record) -> PublishedQuestions:
    """What this stage wrote on the record."""
    written = record.human_review.publish

    assert written is not None
    return written


def store_of(engine: Engine) -> AStore:
    """The double behind the port, for a test that asserts what crossed it."""
    store = engine.question_store

    assert isinstance(store, AStore)
    return store


# --- the key it owns ---


def test_a_published_record_gains_exactly_one_key() -> None:
    """I8 at this stage: the receipt is written and nothing else on the record moves."""
    engine = an_engine_publishing()
    ready = asked(engine, a_record())

    written = publish(engine, ready).records

    assert written_paths(ready[0].model_dump(), written[0].model_dump()) == {
        "human_review.publish"
    }


def test_the_record_names_the_questions_the_store_holds() -> None:
    """`stored` is the store's answer, not this stage's list of what it sent."""
    engine = an_engine_publishing()

    written = published(engine, a_record())[0]

    assert receipt_of(written).stored == (questions_of(written)[0].question_id,)


def test_every_record_that_published_carries_the_same_two_stamps() -> None:
    """One write, one `store_run_id`: a call per record would make a batch twenty thousand writes."""
    engine = an_engine_publishing()

    written = published(engine, a_record(), a_record(label=(LOOKED_UP,)))

    assert [receipt_of(record).store_run_id for record in written] == [STORE_RUN] * 2
    assert [receipt_of(record).published_at for record in written] == [WROTE_AT] * 2


def test_a_store_that_held_fewer_makes_a_shorter_list_not_a_wrong_one() -> None:
    """The record records what the store confirmed, which is why the two are intersected."""
    engine = an_engine_publishing(AForgetfulStore())

    assert receipt_of(published(engine, a_record())[0]).stored == ()


# --- what crosses the port ---


def test_the_store_is_handed_one_row_per_question_in_one_call() -> None:
    """`store_run_id` names a write, so a batch is a write."""
    engine = an_engine_publishing()

    published(engine, a_record(), a_record(label=(LOOKED_UP,)))

    assert len(store_of(engine).batches) == 1
    assert len(store_of(engine).batches[0]) == 2


def test_a_row_carries_the_pair_and_the_run_off_the_record() -> None:
    """A store outlives a run, so a row that did not carry them could not be read back safely."""
    engine = an_engine_publishing()

    written = published(engine, a_record())[0]

    row = store_of(engine).held[questions_of(written)[0].question_id]
    assert (row.modality, row.profile) == ("text2text@1", "tool_decision@1")
    assert row.run_id == written.provenance.run_id
    assert row.record_id == written.record_id


def test_every_record_is_published_under_one_config() -> None:
    """A Label Studio project holds one config for every task in it, which is why the catalog is data."""
    engine = an_engine_publishing()

    published(engine, a_record(), a_record(label=(LOOKED_UP,)))

    assert len({row.config_digest for row in store_of(engine).held.values()}) == 1


# --- the config, composed from two halves this module does not write ---


def test_the_config_is_both_halves_inside_one_view() -> None:
    """Display first, because that is reading order: the content, the question, then the controls."""
    assert annotation_config("<A/>", "<B/>") == "<View>\n<A/>\n<B/>\n</View>"


def test_the_composed_config_carries_each_half_and_neither_half_carries_the_other() -> (
    None
):
    """Requirement 31, on the composition and on the pieces."""
    engine = an_engine_publishing()
    record = asked(engine, a_record())[0]
    display = engine.modality.display_config(record)
    capture = engine.profile.answer_config(record)

    composed = annotation_config(display.tags, capture.tags)

    assert "<Paragraphs" in composed and '<Choices name="verdict"' in composed
    assert "<Choices" not in display.tags
    assert "<Paragraphs" not in capture.tags


def test_the_two_halves_own_disjoint_payload_keys() -> None:
    """A key emitted by both would silently drop one; Requirement 31 is why nothing guards it."""
    engine = an_engine_publishing()
    record = asked(engine, a_record())[0]

    display = engine.modality.display_config(record)
    capture = engine.profile.answer_config(record)

    assert not display.data.keys() & capture.data.keys()


# --- the payload ---


def test_the_payload_carries_both_halves_data_and_the_questions_two_keys() -> None:
    """`question_id` rides inside `data`, because Label Studio assigns its own task ids."""
    engine = an_engine_publishing()

    written = published(engine, a_record())[0]

    question = questions_of(written)[0]
    payload = store_of(engine).held[question.question_id].payload
    assert payload[QUESTION_ID] == question.question_id
    assert payload[QUESTION] == question.content
    assert [turn["role"] for turn in payload["conversation"]] == [
        part.role for part in written.content
    ]
    assert payload["tool_names"] == [
        {"value": "LookupBalance"},
        {"value": "SendStatement"},
        {"value": "OpenTicket"},
    ]


def test_no_model_output_reaches_the_payload() -> None:
    """I12, at the stage that composes what a person is shown.

    The panel here disagrees with the label, so the record carries a plurality, two agreement
    figures, a bucket and a juror's reasoning — none of which appears in what crosses to the store.
    """
    engine = an_engine_publishing()
    written = published(engine, a_record(label=(LOOKED_UP,)))[0]
    said = written.ai_review

    assert said.jury is not None and said.cohesion is not None
    assert said.triage is not None
    printed = str(store_of(engine).held[questions_of(written)[0].question_id].payload)
    for model_output in (
        said.triage.bucket,
        said.triage.stratum,
        said.jury.llm_votes[0].model_name,
        said.jury.llm_votes[0].reasoning,
        said.cohesion.method,
        str(said.cohesion.self_agreement),
    ):
        assert model_output not in printed


# --- what it skips, and what stops it ---


def test_a_record_with_no_question_gets_no_key() -> None:
    """The precondition: absent and empty are one fact — there is nothing to publish."""
    engine = an_engine_publishing()

    written = publish(engine, [a_record()]).records

    assert written[0].human_review.question_generate is None
    assert written[0].human_review.publish is None


def test_a_phase_that_selected_nothing_does_not_touch_the_store() -> None:
    """An empty batch would mint an id over nothing and stamp a clock nobody reads."""
    engine = an_engine_publishing()

    publish(engine, [a_record()])

    assert store_of(engine).batches == []


def test_every_record_comes_back_whether_it_published_or_not() -> None:
    """I11: a skip is a record with no key, never a shorter list."""
    engine = an_engine_publishing()
    corpus = (a_record(), a_record(label=(LOOKED_UP,)))

    written = publish(engine, [*asked(engine, *corpus), a_record()]).records

    assert len(written) == 3
    assert written[-1].human_review.publish is None


def test_an_engine_with_no_store_refuses_before_the_first_record() -> None:
    """P23: a fact about the configuration, and a receipt for a write nobody made would be a lie."""
    engine = replace(an_engine_publishing(), question_store=None)

    with pytest.raises(ConfigError, match="publish needs a question store"):
        publish(engine, asked(an_engine_publishing(), a_record()))


# --- the two adapters, against each other ---


def test_the_stage_publishes_into_the_real_store(
    sessions: sessionmaker[Session],
) -> None:
    """P20: one adapter is a hypothetical seam, and this is the test that makes it two.

    The `sessions` fixture is `test_store.py`'s, so this runs on SQLite in `make check` and on a
    real Postgres under `-m integration` like every other test that touches the store.
    """
    engine = replace(an_engine_asking(), question_store=SqlQuestionStore(sessions))

    written = publish(engine, asked(engine, a_record())).records

    receipt = receipt_of(written[0])
    assert receipt.stored == (questions_of(written[0])[0].question_id,)
    assert receipt.store_run_id.startswith("sr_")
    assert engine.question_store is not None
    assert engine.question_store.answers_to(list(receipt.stored)) == ()


def test_the_real_store_and_the_double_agree_about_a_republish(
    sessions: sessionmaker[Session],
) -> None:
    """Both keep the port's promise: the same batch twice is the same receipt, not an error."""
    engine = replace(an_engine_asking(), question_store=SqlQuestionStore(sessions))
    ready = asked(engine, a_record())

    once = publish(engine, ready).records
    twice = publish(engine, ready).records

    assert receipt_of(once[0]).stored == receipt_of(twice[0]).stored
    assert receipt_of(once[0]).store_run_id == receipt_of(twice[0]).store_run_id
