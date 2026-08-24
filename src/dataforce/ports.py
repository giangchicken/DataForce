"""DEFINITION · QuestionStore and PersonalDataVerifier -- what the engine demands of the edge.

Two ports. The abstraction belongs to the layer that consumes it, so each is declared here and
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

**A port reaches a stage through the ``Engine``**, because every service's signature is
``(engine, records)`` and there is no other channel. ``Engine.personal_data_verifier`` is that, and
``QuestionStore`` arrives the same way in T24.
"""

from collections.abc import Mapping
from typing import Protocol


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
