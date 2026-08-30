"""T19 · jury: what the panel is asked, what comes back, and which of it the record can use.

**The panel is a stand-in in every test here, and that is the boundary rather than a shortcut.**
`make check` runs no network (§ *Testing Strategy* item 8), and what this stage owns is which
records it pays for, what it hands the port, and what it makes of the answers -- all three are
assertable against a stub that answers from a list. The live panel is `edge/bootstrap.py`'s and the
Smoke rung's, which is where the parity gate sits.

**The case that decides who judges a vote is `test_two_calls_on_one_tool_...`.** That answer passes
the materialised schema -- `uniqueItems` compares whole calls, and two calls on one tool with
different arguments are not equal -- and fails the profile, which is the notion `vote_consensus`
uses. A panel deciding validity for itself would write `valid: true` on a vote no consensus could
be built from, and `invalid_votes: 0` would sit beside a null `final_prediction`.

Every fixture is invented.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

import pytest

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.ai_review.jury import answered, jury
from dataforce.pipeline.data_quality.label_check import label_check
from dataforce.ports import JurorAnswer
from dataforce.record import PanelVerdict, Record, StoredAnswer

from .test_label_check import written_paths
from .test_load_data import an_engine
from .test_tool_decision import LOOKED_UP, SENT, TICKETED, a_profile, a_record

# One call naming a tool a second vote also names, with the arguments a juror got wrong. The
# schema permits the pair -- the two calls are not equal -- and the profile does not.
SENT_AGAIN = {
    "name": "SendStatement",
    "arguments": {"ma_khach": "480216", "ky": "thang_truoc"},
}
# A bare name reads as *the call with no arguments* on a source's label and no producer writes
# one, so a juror that does is answering outside the space.
BARE = "LookupBalance"

PANEL = 2
PROMPT = "jury_vote.v1"


class APanel:
    """The jury port, as a stand-in: it answers from a list instead of from N models."""

    def __init__(
        self,
        *said: JurorAnswer,
        panel_version: int = PANEL,
        prompt_version: str = PROMPT,
    ) -> None:
        self.panel_version = panel_version
        self.prompt_version = prompt_version
        self._said = said
        self.asked: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []

    def votes(
        self, slots: Mapping[str, Any], answer_schema: Mapping[str, Any]
    ) -> Sequence[JurorAnswer]:
        """Every call it was asked to make, so a test can assert what crossed the port."""
        self.asked.append((slots, answer_schema))
        return self._said


class AFailingPanel(APanel):
    """A panel that did not come back. `agent-toolkit` owns the retries; this is after them."""

    def votes(
        self, slots: Mapping[str, Any], answer_schema: Mapping[str, Any]
    ) -> Sequence[JurorAnswer]:
        raise RuntimeError("the endpoint is not answering")


class AMisconfiguredPanel(APanel):
    """An adapter reporting a fault a human has to fix, which is what `ConfigError` means."""

    def votes(
        self, slots: Mapping[str, Any], answer_schema: Mapping[str, Any]
    ) -> Sequence[JurorAnswer]:
        raise ConfigError("config/model/DeepSeek-V4-Flash.json names no endpoint")


class ARaisingProfile:
    """Only the two members `answered` calls, and one of them is broken.

    Not a whole `Profile`: what is under test is which side of the seam a raise came from, and
    fifteen unused members would make the fixture the thing a reader has to understand.
    """

    def jury_slots(self, record: Record) -> Mapping[str, Any]:
        raise KeyError("a profile bug, on the engine's side of the port")

    def answer_schema(self, record: Record) -> Mapping[str, Any]:
        return {}


def a_juror(
    answer: StoredAnswer | None,
    model_name: str = "juror-1",
    label_is_right: bool = True,
) -> JurorAnswer:
    """One juror's answer, in the shape the port hands back: no verdict on its usability."""
    return JurorAnswer(
        model_name=model_name,
        label_is_right=label_is_right,
        answer=answer,
        reasoning="Yêu cầu của khách là gửi sao kê.",
    )


def a_panel_of(*answers: StoredAnswer | None) -> APanel:
    """One juror per answer, named in order, so a test can read the votes back by name."""
    return APanel(
        *(
            a_juror(answer, model_name=f"juror-{seat + 1}")
            for seat, answer in enumerate(answers)
        )
    )


def an_engine_that(panel: APanel | None) -> Engine:
    """The engine a stage is handed: both axes, `params.yaml`, and the panel's port."""
    return replace(an_engine(), jury_panel=panel)


def judged(*records: Record, engine: Engine | None = None) -> tuple[Record, ...]:
    """Records through `label_check` and then `jury`, which is the order the phase runs them."""
    running = engine or an_engine_that(a_panel_of((SENT,)))
    return jury(running, label_check(running, records).records).records


def verdict_of(record: Record) -> PanelVerdict:
    """What this stage wrote on the record."""
    written = record.ai_review.jury

    assert written is not None
    return written


def answers_in(verdict: PanelVerdict) -> Iterable[tuple[StoredAnswer, bool]]:
    """Each vote as the record kept it: what it answered, and whether the record can use it."""
    return [(vote.answer, vote.valid) for vote in verdict.llm_votes]


# --- the stage's own three promises ---


def test_a_record_gains_exactly_one_key() -> None:
    """I8. `ai_review.jury` and nothing else -- not the content, not the label, not a sibling."""
    engine = an_engine_that(a_panel_of((SENT,)))
    before = label_check(engine, [a_record()]).records[0]
    after = jury(engine, [before]).records[0]

    assert written_paths(before.model_dump(), after.model_dump()) == {"ai_review.jury"}


def test_every_record_comes_back() -> None:
    """I11, including the two this stage does not pay a panel for."""
    given = (a_record(), a_record(tools=[]), a_record(label=(LOOKED_UP,)))

    assert len(judged(*given)) == len(given)


def test_there_is_no_side_output() -> None:
    """A vote is a value on the record; the manifest already says which panel produced it."""
    engine = an_engine_that(a_panel_of((SENT,)))

    assert jury(engine, label_check(engine, [a_record()]).records).side_output == {}


# --- which records are paid for ---


def test_a_quarantined_record_is_not_judged() -> None:
    """§ *Per-service contracts*: no point paying a panel to weigh a record already known broken."""
    panel = a_panel_of((SENT,))
    written = judged(a_record(tools=[]), engine=an_engine_that(panel))[0]

    assert written.ai_review.jury is None
    assert panel.asked == []


def test_a_record_label_check_never_saw_is_not_judged() -> None:
    """The absence, not the verdict -- the rule `pii_check`'s own precondition states."""
    panel = a_panel_of((SENT,))
    written = jury(an_engine_that(panel), [a_record()]).records[0]

    assert written.ai_review.jury is None
    assert panel.asked == []


def test_a_skipped_record_comes_back_untouched() -> None:
    """A skip is a record with one key fewer, never a record with something else changed."""
    before = a_record(tools=[])

    assert (
        judged(before)[0].model_dump()
        == label_check(an_engine_that(a_panel_of()), [before]).records[0].model_dump()
    )


# --- what crosses the port ---


def test_the_panel_is_handed_the_slots_and_the_space_and_not_the_record() -> None:
    """Requirement 51's division: the values are the profile's, the template is policy's."""
    panel = a_panel_of((SENT,))
    record = a_record()
    judged(record, engine=an_engine_that(panel))
    slots, schema = panel.asked[0]

    assert slots == a_profile().jury_slots(record)
    assert schema == a_profile().answer_schema(record)


def test_no_provenance_leaves_with_the_prompt() -> None:
    """What the panel can see is the conversation, the catalog and the label, and that is all."""
    panel = a_panel_of((SENT,))
    record = a_record()
    judged(record, engine=an_engine_that(panel))
    filled = " ".join(str(value) for value in panel.asked[0][0].values())

    assert record.provenance.run_id not in filled
    assert record.source_id not in filled


def test_the_panel_is_asked_once_per_record() -> None:
    """One call per record is what makes the phase's cost legible, and what caching keys on."""
    panel = a_panel_of((SENT,))
    judged(a_record(), a_record(label=(LOOKED_UP,)), engine=an_engine_that(panel))

    assert len(panel.asked) == 2


# --- every vote is kept ---


def test_the_composition_reaches_the_record() -> None:
    """A change to either invalidates every comparison drawn across them (Requirement 24)."""
    verdict = verdict_of(judged(a_record())[0])

    assert (verdict.panel_version, verdict.prompt_version) == (PANEL, PROMPT)


def test_a_vote_outside_the_answer_space_is_kept_and_counted() -> None:
    """Requirement 24: never silently dropped -- a dropped vote makes a noisy panel look small."""
    panel = a_panel_of((SENT,), (BARE,))
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert answers_in(verdict) == [((SENT,), True), ((BARE,), False)]
    assert verdict.invalid_votes == 1


def test_two_calls_on_one_tool_pass_the_schema_and_are_still_invalid() -> None:
    """The case that decides who judges a vote: `uniqueItems` compares whole calls, so the
    materialised schema permits this pair and the profile -- which is what `vote_consensus` uses
    -- does not."""
    record = a_record()
    answer = (SENT, SENT_AGAIN)

    assert a_profile().answer_schema(record)["uniqueItems"] is True
    assert not a_profile().answer_is_permitted(answer, record)

    panel = a_panel_of(answer)
    verdict = verdict_of(judged(record, engine=an_engine_that(panel))[0])

    assert answers_in(verdict) == [(answer, False)]
    assert verdict.invalid_votes == 1


def test_a_juror_that_decoded_nothing_is_present_and_invalid() -> None:
    """`None` is written down as the empty answer, which is a real vote and must not be counted
    as one: *call nothing* is what a majority of empty votes means."""
    panel = a_panel_of(None, ())
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert answers_in(verdict) == [((), False), ((), True)]
    assert verdict.invalid_votes == 1


def test_an_absent_juror_and_an_undecodable_one_read_differently() -> None:
    """Two failure modes and two readings of them: an exhausted call moves the vote count, an
    undecodable answer moves `invalid_votes`. Collapsing them would make a panel that half
    failed indistinguishable from a panel that half misbehaved."""
    exhausted = verdict_of(
        judged(a_record(), engine=an_engine_that(a_panel_of((SENT,))))[0]
    )
    undecodable = verdict_of(
        judged(a_record(), engine=an_engine_that(a_panel_of((SENT,), None)))[0]
    )

    assert (len(exhausted.llm_votes), exhausted.invalid_votes) == (1, 0)
    assert (len(undecodable.llm_votes), undecodable.invalid_votes) == (2, 1)


def test_the_juror_keeps_its_name_its_verdict_and_its_reasoning() -> None:
    """Requirement 24's four fields; the reasoning is for the human who reads a disagreement."""
    panel = APanel(a_juror((LOOKED_UP,), model_name="juror-b", label_is_right=False))
    vote = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0]).llm_votes[0]

    assert (vote.model_name, vote.label_is_right) == ("juror-b", False)
    assert vote.reasoning


# --- what the panel is taken to have said ---


def test_the_plurality_is_what_most_of_the_usable_votes_gave() -> None:
    """Grouped by the profile's δ rather than by `==`: two votes naming the same two tools in a
    different order are one answer, and a comparison on the stored form would call the single
    dissenting vote the plurality instead."""
    panel = a_panel_of((TICKETED,), (SENT, LOOKED_UP), (LOOKED_UP, SENT))
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert verdict.plurality == (SENT, LOOKED_UP)


def test_a_tie_goes_to_the_juror_that_voted_first() -> None:
    """Two runs over one record write the same plurality, which `max` over a set would not."""
    panel = a_panel_of((LOOKED_UP,), (TICKETED,))
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert verdict.plurality == (LOOKED_UP,)


def test_an_invalid_vote_reaches_neither_the_plurality_nor_the_prediction() -> None:
    """An answer the profile refuses is one no consensus could have been built from anyway."""
    panel = a_panel_of((BARE,), (BARE,), (SENT,))
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert verdict.invalid_votes == 2
    assert verdict.plurality == (SENT,)
    assert verdict.final_prediction == (SENT,)


def test_a_majority_voting_the_empty_answer_agreed_to_call_nothing() -> None:
    """`()` and null stay two values: this is the one that means the panel decided something."""
    panel = a_panel_of((), (), (SENT,))
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert verdict.final_prediction == ()


def test_a_panel_that_agreed_on_nothing_defensible_says_so_with_null() -> None:
    """Three jurors, three different tools, no majority for any name."""
    panel = a_panel_of((SENT,), (LOOKED_UP,), (TICKETED,))
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(panel))[0])

    assert verdict.final_prediction is None


# --- when the panel does not come back ---


def test_a_panel_that_failed_is_read_as_no_votes() -> None:
    """Requirement 43: a call that failed after the retries is not a reason to stop a run."""
    verdict = verdict_of(judged(a_record(), engine=an_engine_that(AFailingPanel()))[0])

    assert verdict.llm_votes == ()
    assert verdict.invalid_votes == 0
    assert verdict.final_prediction is None


def test_a_run_of_many_records_completes_when_one_panel_call_fails() -> None:
    """The record carries the consequence; the other nineteen thousand are unaffected."""
    given = (a_record(), a_record(label=(LOOKED_UP,)))
    written = judged(*given, engine=an_engine_that(AFailingPanel()))

    assert [verdict_of(record).llm_votes for record in written] == [(), ()]


# --- the one thing that stops a run ---


def test_an_engine_with_no_panel_refuses_before_the_first_record() -> None:
    """A fact about the configuration, raised before any record is touched."""
    with pytest.raises(ConfigError, match="panel"):
        jury(an_engine_that(None), [a_record()])


def test_the_refusal_does_not_depend_on_there_being_a_record() -> None:
    """An empty batch is not a reason to accept a configuration that cannot run."""
    with pytest.raises(ConfigError, match="panel"):
        jury(an_engine_that(None), [])


def test_a_config_error_from_the_panel_stops_the_run() -> None:
    """`ConfigError` means a human must change configuration, so it is not one missing vote.

    An adapter that cannot reach its endpoint raises on record 1 and on all twenty thousand.
    Caught, the run completes with every record scoring `0.0` in `cohesion` and landing in
    `contested` -- a corpus-shaped lie, and louder than the failure it hid.
    """
    engine = an_engine_that(AMisconfiguredPanel())

    with pytest.raises(ConfigError, match="endpoint"):
        jury(engine, label_check(engine, [a_record()]).records)


def test_a_raise_on_the_engine_side_of_the_port_is_not_a_panel_failure() -> None:
    """The `try` fences the call across the seam and nothing on this side of it. A profile bug
    read as *the panel did not answer* is a bug that produces a plausible record instead of a
    stack trace."""
    engine = replace(an_engine_that(a_panel_of((SENT,))), profile=ARaisingProfile())  # type: ignore[arg-type]

    with pytest.raises(KeyError):
        answered(engine, a_panel_of((SENT,)), a_record())
