"""DEFINITION · QuestionStore, PersonalDataVerifier and JuryPanel -- what the engine demands of the edge.

Three ports. The abstraction belongs to the layer that consumes it, so each is declared here and
implemented in ``edge/`` (P18) -- an adapter declaring its own port is how a clean-looking layer
diagram turns out to be false.

**A port is what the engine calls *back* into during a run; what it is constructed with is a
value.** Since T12 an axis implementation is *built with* what only the edge can produce --
``text2text`` with the encoder behind its static model, ``tool_decision`` with the question template
out of ``config/prompts/`` -- and those are constructor arguments ``edge/bootstrap.py`` hands over,
not interfaces anything implements. That is the line this module is drawn on, and it is why an
encoder is not declared here.

**``PersonalDataVerifier`` arrived with a caller, which is the only reason it is here.** This module
said *one port, because a port with no adapter is a guess about a future caller* (P20), and the
sentence stands: what changed is that Requirement 18's second layer is a model pass, a model call
opens a socket, and ``pii_check`` may not make one. So the engine slices the window and decides what
to do with the answer, and the edge makes the call. Two adapters make a seam real (P20) and there are
two: the client ``edge/bootstrap.py`` builds, and the stand-in every test in ``make check`` runs
against -- *no network in `make check`* is § *Testing Strategy*'s rule, not a convenience.

**``JuryPanel`` is the same argument at a larger size, and it draws the line in a different
place.** ``jury`` cannot call N models for the same reason ``pii_check`` cannot call one, so the
panel is the edge's: it holds the composition, the task statement out of ``config/prompts/``, the
retries and the rate limiting. What crosses is the *filled slots* and the record's materialised
answer schema -- never the record, so nothing about provenance, quarantine or a previous scan leaves
with the prompt (Requirement 51: the template is policy's and the values are the profile's).

**Whether a vote is usable is not the panel's to say.** The panel reports what each juror answered
and the engine decides, because ``vote_consensus`` already refuses an answer the profile does not
permit -- and a schema cannot say *at most one call per tool name*, which is the case the two
notions part on. Two notions of *valid* on one record is how ``invalid_votes: 0`` comes to sit
beside ``final_prediction: null``, and nothing in the record would say which one was wrong.

**A port reaches a stage through the ``Engine``**, because every service's signature is
``(engine, records)`` and there is no other channel. ``Engine.personal_data_verifier`` and
``Engine.jury_panel`` are that, and ``QuestionStore`` arrives the same way in T24.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
