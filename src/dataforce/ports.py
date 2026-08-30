"""DEFINITION · QuestionStore, PersonalDataVerifier and JuryPanel -- what the engine demands of the edge.

Three ports. The abstraction belongs to the layer that consumes it, so each is declared here and
implemented in ``edge/`` -- an adapter declaring its own port is how a clean-looking layer
diagram turns out to be false.

**A port is what the engine calls *back* into during a run; what it is constructed with is a
value.** Since T12 an axis implementation is *built with* what only the edge can produce --
``text2text`` with the encoder behind its declared model, ``tool_decision`` with the question template
out of ``config/prompts/`` -- and those are constructor arguments ``edge/bootstrap.py`` hands over,
not interfaces anything implements. That is the line this module is drawn on, and it is why an
encoder is not declared here.

**``PersonalDataVerifier`` arrived with a caller, which is the only reason it is here.** This module
said *one port, because a port with no adapter is a guess about a future caller*, and the
sentence stands: what changed is that Requirement 18's second layer is a model pass, a model call
opens a socket, and ``pii_check`` may not make one. So the engine slices the window and decides what
to do with the answer, and the edge makes the call. Two adapters are what would make the seam real, and **today there is one**: the stand-in every test in ``make check`` runs against, which is
not a convenience -- *no network in `make check`* is § *Testing Strategy*'s rule. The client belongs
to ``edge/bootstrap.py``, which is a docstring; T27 is where it lands and until then the second
adapter is a claim.

**``JuryPanel`` is the same argument at a larger size, and it draws the line in a different
place.** ``jury`` cannot call N models for the same reason ``pii_check`` cannot call one, so the
panel is the edge's, and an adapter of it *will* hold the composition, the task statement out of
``config/prompts/``, the retries and the rate limiting -- none of which exists yet either. What
crosses is the *filled slots* and the record's materialised answer **space** -- never the record, so
nothing about provenance, quarantine or a previous scan leaves with the prompt (Requirement 51: the
template is policy's and the values are the profile's).

*Space* and not *schema*, because the space is what the record's answer is judged against and the
schema is only the part of it a schema can express -- the distinction the member below is here for.

**Whether a vote is usable is not the panel's to say.** The panel reports what each juror answered
and the engine decides, because ``vote_consensus`` already refuses an answer the profile does not
permit -- and a schema cannot say *at most one call per tool name*, which is the case the two
notions part on. Two notions of *valid* on one record is how ``invalid_votes: 0`` comes to sit
beside ``final_prediction: null``, and nothing in the record would say which one was wrong.

**A port reaches a stage through the ``Engine``**, because every service's signature is
``(engine, records)`` and there is no other channel. ``Engine.personal_data_verifier`` and
``Engine.jury_panel`` are that, and ``Engine.question_store`` is how ``QuestionStore`` reaches
``publish`` and ``annotator_answers``. It landed with its first reader in T23 and not before,
because a field with no reader is a guess and this module is where that rule is kept.

**``QuestionStore`` is the one port whose absence Requirement 32 settled rather than this module.**
Whether a stage reaches the store through a port at all or hands rows back as side output was open
until T23 -- § *Engine and edge* says the engine returns rows and the edge writes them, which reads
like the second. Requirement 32 says ``publish`` writes *through a port supplied at the edge* **and
records the receipt on the record**, and only the first shape can do both: a receipt names a write
that has already happened, so a stage that only returned rows could not write its own key, and the edge
would be writing ``human_review.publish`` -- a second writer for one key.

**What crosses is a row and never a record.** The store holds one question's payload and one
annotation's control values; it holds no content, no label and no verdict of any earlier phase,
because nothing there is answerable and Requirement 30 is asserted on what reaches a person.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from dataforce.record import StoredAnswer


class PersonalDataVerifier(Protocol):
    """Layer two: which of layer one's candidates are personal data, and as what."""

    def confirmed_personal_data(
        self, window: str, found: Mapping[str, str]
    ) -> Mapping[str, str]:
        """The candidates this window confirms, each under the class it confirms it as.

        `found` maps every value layer one flagged inside `window` to the class it guessed. The
        result is a **subset** of those values: one left out is a hit this layer could not confirm,
        which the record carries as `verified: false` and counts in `unverified` -- the number
        `export`'s precondition reads. A class may come back different from the guess, because layer
        one is tuned for recall and its patterns overlap on purpose: a ten-digit run is a phone
        number *and* a customer id until something reads the sentence around it.

        The window is one part's text, bounded by the caller. Layer two sees the turn a hit is in and
        no more, so setting the precision of one hit never sends a whole conversation anywhere.

        **It may not raise.** A model call that failed after the library's own retries is one missing
        answer, not a reason to stop a run of twenty thousand records (Requirement 43): the caller
        reads *no confirmation* out of an empty result and out of a failure alike, and the record
        says `unverified` either way.
        """
        ...


@dataclass(frozen=True)
class JurorAnswer:
    """What one juror said, before the engine decides whether the record can use it.

    Not a `JurorVote`: that is what `ai_review.jury` holds and it carries `valid`, which this
    layer does not decide. The two shapes differ by exactly that field, and the difference is the
    seam -- the edge reports, the engine judges.
    """

    model_name: str  # which juror; the panel's own name for the model it called
    label_is_right: bool  # its verdict on the label the record already carries
    answer: StoredAnswer | None  # its own, or None where nothing decodable came back
    reasoning: str  # why, for the human who reads a disagreement


class JuryPanel(Protocol):
    """N models answering one record's task, and the composition that produced the answers."""

    # Facts about the panel and not about any record, so they are read once rather than returned
    # per call. A change to either invalidates comparison, which is why both reach the record.
    panel_version: int
    prompt_version: str

    def votes(
        self, slots: Mapping[str, Any], answer_schema: Mapping[str, Any]
    ) -> Sequence[JurorAnswer]:
        """Every juror that answered, in the panel's own order.

        `slots` is what `jury_slots(record)` gave: the values this panel's task statement is filled
        with, and the whole of what leaves the engine. `answer_schema` is the record's materialised
        answer space, which is what a structured call constrains against -- the panel does not
        materialise one of its own, because a second copy of an answer space is the copy that goes
        stale.

        **A juror that never answered is absent, not an empty vote.** A call exhausted by the
        library's own retries is one missing vote; a call that came back with nothing decodable is
        a vote whose `answer` is None. The record can tell those apart -- one changes the vote
        count and the other changes `invalid_votes`.

        **It may not raise**, for `confirmed_personal_data`'s reason: a panel that failed after the
        retries is a record with no votes, not a stopped run of twenty thousand (Requirement 43).
        """
        ...


@dataclass(frozen=True)
class QuestionToStore:
    """One question as the store takes it: the join keys, the task payload, and what composed it.

    Flat rather than the record's `Question` plus a payload, because the store's own row is flat and
    an adapter that had to reshape one would be a second place the row's shape is written down. The
    pair and the run travel with it for the reason `Provenance` carries them: a store outlives a run
    and a question answered under one pair cannot be read under another.
    """

    question_id: str  # what everything joins on; minted by `question_generate`
    record_id: str  # which record it asks about, for joining an answer back to the bus
    run_id: str  # which pipeline run published it; a store outlives any one of them
    modality: str  # the pair this question was composed under, stamped `name@version`
    profile: str  # the other half of that pair, stamped the same way
    payload: Mapping[
        str, Any
    ]  # the task payload: `data` and nothing else (Requirement 30)
    config_digest: str  # of the annotation config the payload was composed against


@dataclass(frozen=True)
class StoreReceipt:
    """What the store did with a batch of questions: which it now holds, under which write, when.

    The two stamps are the store's and not the engine's, because both are I/O -- a clock and an
    identity for one write -- and no engine module holds either (I1). `publish` writes them onto the
    record verbatim, which is what makes a re-publish visible as a second `store_run_id` rather than
    as a silently identical key.
    """

    stored: tuple[str, ...]  # the `question_id`s the store holds after this write
    store_run_id: str  # which write; the adapter mints it, the record carries it
    published_at: datetime  # when the store wrote them, by the store's clock


@dataclass(frozen=True)
class StoredAnnotation:
    """One person's answer as the store holds it: the control values, and the tool's own metadata.

    **`result` is verbatim and undecomposed.** Requirement 49 makes `annotation_response` the only
    place an annotation tool's shape is read, so a `verdict` column filled by whatever wrote the row
    would be a second reader of that shape -- in the layer furthest from the capture half that
    defines it. The envelope is a different fact and is decomposed: `was_skipped` and
    `lead_time_seconds` are the pilot's instruments and are not an answer to anything.

    `external_annotation_id` does not cross. It is the store's own idempotency key and no stage has
    a use for it, which is the whole of a narrow interface.
    """

    answer_id: str  # the store's id for this answer; unique within the store
    question_id: str  # which question it answers, joined back to `question_generate`
    annotator_id: str  # who answered
    result: tuple[Mapping[str, Any], ...]  # the annotation's control values, verbatim
    was_skipped: bool  # the annotator saw it and declined; a skip is not a verdict
    lead_time_seconds: float | None  # how long they took, where the tool reported it
    submitted_at: datetime  # when they submitted it, by the annotation tool's clock


class QuestionStore(Protocol):
    """The questions a run published, and the answers people gave them."""

    def stored_questions(self, questions: Sequence[QuestionToStore]) -> StoreReceipt:
        """Every question the store holds after writing these, and the stamps of the write.

        **Writing a question the store already has is not an error.** The id is a pure function of
        the question (`question_generate`), so a second publish of an unchanged corpus is the same
        rows -- and a store that raised would make re-running a phase something a caller has to be
        careful about, which is the error to design out. The receipt names every id the
        store holds for this batch, whether this call wrote it or an earlier one did, because that
        is what `publish` records and what a person auditing a re-run reads.

        **It may not raise about one question.** A batch that reached a store and a batch that did
        not are different facts, and the second is a `ConfigError` about the configuration:
        an unreachable database is one thing wrong, not twenty thousand.
        """
        ...

    def answers_to(self, question_ids: Sequence[str]) -> Sequence[StoredAnnotation]:
        """Every answer the store holds to any of those questions, in no promised order.

        Answers and not answer: a question is asked of as many annotators as the rung's overlap
        says, and `aggregate` is what folds them. A question nobody has answered contributes
        nothing rather than an empty answer -- the two are told apart by counting.

        Ids rather than records, because the store joins on `question_id` and has never seen a
        record. A caller with no ids gets nothing back and makes no query.
        """
        ...
