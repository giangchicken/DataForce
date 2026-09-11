"""The panel over hand-written answers: the arithmetic, the two prompts, and the failure paths.

No model answers anything here, and which seam is stubbed follows the rule under test.
`StubbedPanel` overrides `predict` and `judge_prediction`, for the tests about what the
*arithmetic* does with the votes it is given -- a strict majority, agreement over the votes that
came back, and the narrowing that lets a judge return only an answer a juror wrote, which is a rule
of the modality that this task does not use. `answering` stubs the library's `complete` instead,
for the tests about `ToolPredictor`'s own contract: that a juror that fails is absent rather than
an empty-label vote, that an unparseable answer is the same thing, and that what reaches a model is
a prompt with no slot left in it.

Every answer is written as tool calls, because that is the shape a juror answers in and the reason
the matching is structural: `[{"name": "A"}]`, `[{"name":"A"}]` and the same two calls in the other
order are one answer. A panel that counted those as two would break a tie it does not have -- and
then pay a model to break it.
"""

import json
from collections.abc import Mapping, Sequence
from itertools import takewhile
from pathlib import Path
from typing import Any

import pytest
from agent_toolkit.llm import LLMConfig

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.ai_review import LLMReviewerVote
from dataforce.modalities.text2text.ai_review.schema import (
    LLMModelConfig,
    SFTModelConfig,
)
from dataforce.profile.tool_decision import ai_review
from dataforce.profile.tool_decision.ai_review import (
    ToolDecisionLLMPrediction,
    ToolDecisionSFTPrediction,
)
from dataforce.profile.tool_decision.utils import openai_tool_format_to_text

OPEN_TICKET = '[{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}]'
# The same call, spelled the way a second model happens to write it: no spaces, keys the other way
# round. One answer, and the whole reason two of them are compared as canonical text.
OPEN_TICKET_TIGHT = '[{"arguments":{"ma_khach":"KH-1"},"name":"OpenTicket"}]'
CLOSE_TICKET = '[{"name": "CloseTicket", "arguments": {"ma_phieu": "SR-1"}}]'
# The two calls a message needs, in the two orders two jurors happen to write them, and once with
# the arguments as the JSON text a provider's wire format writes.
BOTH_CALLS = f"[{OPEN_TICKET[1:-1]}, {CLOSE_TICKET[1:-1]}]"
BOTH_CALLS_REVERSED = f"[{CLOSE_TICKET[1:-1]}, {OPEN_TICKET[1:-1]}]"
ARGUMENTS_AS_TEXT = (
    '[{"name": "OpenTicket", "arguments": "{\\"ma_khach\\": \\"KH-1\\"}"}]'
)
NO_TOOL = "[]"

TURNS = (
    "user: Chào em, mở phiếu cho anh với.",
    "assistant: Dạ anh cho em mã khách hàng ạ.",
    "user: KH-1 nhé.",
)
TOOLS: tuple[Mapping[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "OpenTicket",
            "description": "Mở phiếu hỗ trợ cho khách hàng.",
            "parameters": {
                "type": "object",
                "required": ["ma_khach"],
                "properties": {"ma_khach": {"type": "string"}},
            },
        },
    },
)

JUROR = "a-juror"
SECOND = "another-juror"
RESOLVED = LLMConfig(model=JUROR, base_url="http://a-model.invalid")


@pytest.fixture(autouse=True)
def resolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every juror and the judge resolve their model as the panel is built.

    Autouse and not a helper, because it is a precondition of *constructing* the panel rather than
    of any one rule. Patched at the library's own call, and the resolved model is named for the one
    asked, so a vote can say which juror produced it -- `test_model_config.py` owns what a config
    that cannot be resolved does.
    """

    def resolving(**kwargs: Any) -> LLMConfig:
        return LLMConfig(model=kwargs["model"], base_url=RESOLVED.base_url)

    monkeypatch.setattr(ai_review, "resolve_config", resolving)


def panel(*jurors: str) -> ToolDecisionLLMPrediction:
    """A real panel over the models named."""
    return ToolDecisionLLMPrediction([LLMModelConfig(model=name) for name in jurors])


class StubbedPanel(ToolDecisionLLMPrediction):
    """The arithmetic over votes written here: one juror per answer, and the judge answered too.

    `silent` declares jurors that answered nothing, which is what a failed call comes to -- so the
    panel asked and the votes returned differ, which is the whole of what `label_agreement` is
    measured over. `judged` is what a judge would answer, for the modality's narrowing rule that
    this task's own `judge_prediction` never reaches, and `asked` records that call so a test can
    say it was not made.
    """

    def __init__(
        self, *answers: str, silent: int = 0, judged: str | None = None
    ) -> None:
        super().__init__(
            [
                LLMModelConfig(model=f"{JUROR}-{number}")
                for number in range(1, len(answers) + silent + 1)
            ]
        )
        self.answers = answers
        self.judged = judged
        self.asked: list[tuple[str, ...]] = []

    async def predict(
        self, turns: Sequence[str], tools: Sequence[object], language: str
    ) -> Sequence[LLMReviewerVote]:
        return tuple(
            LLMReviewerVote(model_name=f"{JUROR}-{number}", reason="stubbed", label=one)
            for number, one in enumerate(self.answers, start=1)
        )

    async def judge_prediction(self, answers: Sequence[str]) -> str | None:
        self.asked.append(tuple(answers))
        return self.judged


def answering(
    monkeypatch: pytest.MonkeyPatch,
    *,
    voted: Mapping[str, Any],
    prompts: list[str] | None = None,
) -> None:
    """Install a `complete` that answers as the model it was handed.

    `voted` is keyed by the model asked, so a panel where one juror fails and another answers is
    written as that. An entry may be the answer object, the raw text, or an exception to raise.
    """

    async def answered(prompt: str, **kwargs: Any) -> str:
        if prompts is not None:
            prompts.append(prompt)
        resp = voted[kwargs["model"]]
        if isinstance(resp, Exception):
            raise resp
        return resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr(ai_review, "complete", answered)


def voting(label: Any, reason: str = "stubbed") -> Mapping[str, Any]:
    """What `tool_prediction.txt` asks a juror for, as the shape it asks for it in."""
    return {"reason": reason, "label": label}


def section(prompt: str, heading: str) -> list[str]:
    """The lines under one `## heading`, up to the next blank line.

    Read positionally on purpose: a prompt with the language where the turns should be contains
    both, so `in prompt` says nothing about which slot each one landed in.
    """
    lines = prompt.splitlines()
    after = lines[lines.index(heading) + 1 :]
    return list(takewhile(lambda line: line.strip(), after))


def events_on(captured: pytest.CaptureFixture[str]) -> list[Mapping[str, Any]]:
    """The events one call wrote, read back as the objects a deployment reads (`H-6`)."""
    return [json.loads(line) for line in captured.readouterr().out.splitlines()]


# ----------------------------------------------------------------- the strict majority


async def test_two_of_three_matching_is_the_panel_s_answer() -> None:
    """A strict majority, in the one case it and a mode agree about."""
    said = StubbedPanel().exact_match_consensus([OPEN_TICKET, OPEN_TICKET, NO_TOOL])

    assert said == OPEN_TICKET


async def test_two_and_two_is_no_answer() -> None:
    """A strict majority and never a mode: two of four is half, and half is not more than half."""
    said = StubbedPanel().exact_match_consensus(
        [OPEN_TICKET, OPEN_TICKET, NO_TOOL, NO_TOOL]
    )

    assert said is None


async def test_a_mode_that_is_not_a_strict_majority_is_no_answer() -> None:
    """The case the two rules disagree about, and the reason the requirement names one of them.

    Two of five is the most-given answer and is not the panel's: three jurors said something else.
    """
    said = StubbedPanel().exact_match_consensus(
        [OPEN_TICKET, OPEN_TICKET, NO_TOOL, CLOSE_TICKET, "[{}]"]
    )

    assert said is None


async def test_two_answers_that_mean_the_same_count_as_one() -> None:
    """One whitespace and one key ordering, which is what makes this a majority.

    Compared as written, these are three different strings and the panel has no answer. What comes
    back is the answer as the juror wrote it, not the canonical form nothing was written in.
    """
    said = StubbedPanel().exact_match_consensus(
        [OPEN_TICKET, OPEN_TICKET_TIGHT, NO_TOOL]
    )

    assert said == OPEN_TICKET


async def test_a_panel_of_one_is_its_own_majority() -> None:
    """One config is a panel of one, and one answer is more than half of one."""
    assert StubbedPanel().exact_match_consensus([NO_TOOL]) == NO_TOOL


async def test_nothing_answered_is_no_answer() -> None:
    """Every juror failing, seen from the arithmetic: no votes to count a majority over."""
    assert StubbedPanel().exact_match_consensus([]) is None


# ----------------------------------------------------------------- what the panel said


async def test_agreement_is_counted_over_the_votes_that_came_back() -> None:
    """§ *Error Behavior*: a juror that failed is absent, not a disagreement.

    Three jurors asked, one silent, and one of the two answers matches the label. Half the panel
    said what the label says and half of what came back did too -- the number that would drag it
    to a third is the one this forbids.
    """
    panel_of_three = StubbedPanel(OPEN_TICKET, NO_TOOL, silent=1)

    said = await panel_of_three.verdict(TURNS, OPEN_TICKET, TOOLS, "vi")

    assert len(panel_of_three.jurors) == 3
    assert [vote.label for vote in said.votes] == [OPEN_TICKET, NO_TOOL]
    assert said.label_agreement == 0.5


async def test_agreement_reads_the_label_the_way_the_answers_are_read() -> None:
    """The label arrives as JSON and a juror answers in JSON, so one spelling is not a disagreement."""
    said = await StubbedPanel(OPEN_TICKET_TIGHT).verdict(
        TURNS, OPEN_TICKET, TOOLS, "vi"
    )

    assert said.label_agreement == 1.0


async def test_every_juror_failing_is_a_verdict_and_not_an_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """§ *Error Behavior*, the second bullet: no votes, `0.0`, `None`, and one event per juror."""
    answering(
        monkeypatch,
        voted={
            JUROR: RuntimeError("the endpoint hung up"),
            SECOND: RuntimeError("the endpoint hung up"),
        },
    )

    said = await panel(JUROR, SECOND).verdict(TURNS, OPEN_TICKET, TOOLS, "vi")

    assert said.votes == ()
    assert said.label_agreement == 0.0
    assert said.consensus is None
    events = events_on(capsys)
    assert [event["event"] for event in events] == ["tool_prediction_failed"] * 2
    assert {event["model"] for event in events} == {JUROR, SECOND}
    assert all("RuntimeError" in event["error"] for event in events)


# ----------------------------------------------------------------- the judge fallback


async def test_the_judge_is_not_asked_where_the_exact_match_answered() -> None:
    """§ *Design*: only where that is `None` does `verdict` ask the judge."""
    agreeing = StubbedPanel(OPEN_TICKET, OPEN_TICKET, judged=NO_TOOL)

    said = await agreeing.verdict(TURNS, OPEN_TICKET, TOOLS, "vi")

    assert said.consensus == OPEN_TICKET
    assert agreeing.asked == []


async def test_the_judge_breaks_a_tie_with_the_answer_the_juror_wrote() -> None:
    """What comes back is matched to an answer given, and returned as written.

    The judge is handed the two answers and picks the first, spelled its own way. What the verdict
    carries is the juror's spelling, because that is what a juror said.
    """
    tied = StubbedPanel(OPEN_TICKET, CLOSE_TICKET, judged=OPEN_TICKET_TIGHT)

    said = await tied.verdict(TURNS, OPEN_TICKET, TOOLS, "vi")

    assert tied.asked == [(OPEN_TICKET, CLOSE_TICKET)]
    assert said.consensus == OPEN_TICKET


async def test_a_judge_answer_no_juror_wrote_is_refused() -> None:
    """The invariant, and the cheapest way to break it: a judge that answers the sample itself.

    An answer nobody gave is not the panel's answer, so the tie stands rather than resolving to a
    call no juror would defend.
    """
    tied = StubbedPanel(OPEN_TICKET, CLOSE_TICKET, judged='[{"name": "Escalate"}]')

    said = await tied.verdict(TURNS, OPEN_TICKET, TOOLS, "vi")

    assert said.consensus is None


async def test_this_task_asks_no_judge_and_pays_for_no_call_to_say_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tie that survives the matching is two different calls, and it stands.

    Two jurors, two calls made, and nothing else asked. A model picking between `OpenTicket` and
    no tool at all would be the deciding vote, cast by a juror that never read the
    conversation; what the record carries instead is a panel that disagreed.
    """
    prompts: list[str] = []
    answering(
        monkeypatch,
        voted={JUROR: voting([{"name": "OpenTicket"}]), SECOND: voting([])},
        prompts=prompts,
    )
    asked = panel(JUROR, SECOND)

    said = await asked.verdict(TURNS, OPEN_TICKET, TOOLS, "vi")

    assert said.consensus is None
    assert await asked.judge_prediction([OPEN_TICKET, NO_TOOL]) is None
    assert len(prompts) == 2


# ----------------------------------------------------------------- one juror, one call


async def test_one_vote_per_juror_that_answered_names_the_juror_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`model_name` is the caller's, so a record says who answered.

    The array a juror answers with is held as one string and nothing turns it into a structure --
    the calls in it are the same calls, and the field is text.
    """
    calls = [{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}]
    answering(
        monkeypatch,
        voted={
            JUROR: voting(calls, reason="Khách đã cho mã."),
            SECOND: voting([], reason="Chưa đủ thông tin."),
        },
    )

    votes = await panel(JUROR, SECOND).predict(TURNS, TOOLS, "vi")

    assert [vote.model_name for vote in votes] == [JUROR, SECOND]
    assert [vote.reason for vote in votes] == ["Khách đã cho mã.", "Chưa đủ thông tin."]
    assert [json.loads(vote.label) for vote in votes] == [calls, []]
    assert all(isinstance(vote.label, str) for vote in votes)


@pytest.mark.parametrize(
    "resp",
    [
        "I would call OpenTicket here.",
        {"label": [{"name": "OpenTicket"}]},
        {"reason": "no calls key"},
        {"reason": "not the shape", "label": {"name": "OpenTicket"}},
    ],
    ids=["prose", "no-reason", "no-label", "label-not-an-array"],
)
async def test_a_juror_that_did_not_answer_the_shape_is_absent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], resp: Any
) -> None:
    """Never a vote, and never an empty label.

    An empty-label vote is the cheapest wrong implementation: it agrees with nothing, so it drags
    `label_agreement` down and reads as a juror that disagreed rather than one that failed.
    """
    answering(monkeypatch, voted={JUROR: resp, SECOND: voting([])})

    votes = await panel(JUROR, SECOND).predict(TURNS, TOOLS, "vi")

    assert [vote.model_name for vote in votes] == [SECOND]
    events = events_on(capsys)
    assert [event["event"] for event in events] == ["tool_prediction_failed"]
    assert events[0]["model"] == JUROR


async def test_the_settings_a_request_declared_reach_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A juror is asked with what its config carried, forwarded untouched beside the three."""
    asked: dict[str, Any] = {}

    async def answered(prompt: str, **kwargs: Any) -> str:
        asked.update(kwargs)
        return json.dumps(voting([]))

    monkeypatch.setattr(ai_review, "complete", answered)
    declared = LLMModelConfig(model=JUROR, settings={"temperature": 0.0})

    await ToolDecisionLLMPrediction(declared).predict(TURNS, TOOLS, "vi")

    assert asked["model"] == JUROR
    assert asked["temperature"] == 0.0


# ----------------------------------------------------------------- the two prompts


async def test_the_prediction_prompt_carries_the_catalog_the_turns_and_the_language() -> (
    None
):
    """Four slots, and the sample's label in none of them.

    Each value is under its own heading, because two slots filled with each other's value is a
    prompt that reads as nonsense and passes a containment check. The last turn is the question
    and the ones before it are the history, so a juror is not asked about the turn it cannot see.
    """
    prompt = panel(JUROR).build_tool_prediction_prompt(TURNS, TOOLS, "vi")

    assert "{{" not in prompt
    assert section(prompt, "## Conversation History") == list(TURNS[:-1])
    assert section(prompt, "## Customer's Latest Message") == [TURNS[-1]]
    assert section(prompt, "## Conversation Language") == ["vi"]
    assert openai_tool_format_to_text(TOOLS) in prompt
    assert "OpenTicket" in prompt
    assert "ma_khach" in prompt


async def test_the_prediction_prompt_is_the_sample_s_and_holds_no_label() -> None:
    """A juror is not shown the label, stated as the one thing the prompt must not contain.

    A model shown the label answers about the label, and the signal this service runs on is a
    model answering the sample's own question -- so the label reaches no slot, by any spelling.
    """
    prompt = panel(JUROR).build_tool_prediction_prompt(TURNS, TOOLS, "vi")

    assert OPEN_TICKET not in prompt
    assert "KH-1" in prompt  # the customer said it; that is the turn, not the label
    assert "ma_phieu" not in prompt


async def test_a_missing_prompt_is_not_a_failed_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A juror may not raise on a *call*, which is not licence to swallow a declaration error.

    The prompt is built outside the `try` for exactly this: a deployment with no prompt file would
    otherwise ask every juror nothing and report itself as a provider having a bad day.
    """
    answering(monkeypatch, voted={JUROR: voting([])})
    monkeypatch.setattr(ai_review, "TOOL_PREDICTION_PROMPT", Path("nowhere.txt"))

    with pytest.raises(ConfigError, match="nowhere.txt"):
        await panel(JUROR).verdict(TURNS, OPEN_TICKET, TOOLS, "vi")


# ----------------------------------------------------------------- the calls, matched


@pytest.mark.parametrize(
    ("one", "other", "same"),
    [
        (OPEN_TICKET, OPEN_TICKET_TIGHT, True),
        (BOTH_CALLS, BOTH_CALLS_REVERSED, True),
        (OPEN_TICKET, ARGUMENTS_AS_TEXT, True),
        (OPEN_TICKET, f"Đây là kết luận của tôi: {OPEN_TICKET}", True),
        (
            OPEN_TICKET,
            '[{"type": "function", "id": "call_1", "name": "OpenTicket",'
            ' "arguments": {"ma_khach": "KH-1"}}]',
            True,
        ),
        (OPEN_TICKET, CLOSE_TICKET, False),
        (OPEN_TICKET, BOTH_CALLS, False),
        (
            OPEN_TICKET,
            '[{"name": "OpenTicket", "arguments": {"ma_khach": "KH-2"}}]',
            False,
        ),
        (NO_TOOL, NO_TOOL, True),
        (NO_TOOL, f"Không cần gọi tool nào: {NO_TOOL}", True),
        (NO_TOOL, OPEN_TICKET, False),
        (NO_TOOL, "không cần gọi tool nào", False),
    ],
    ids=[
        "one-spelling",
        "the-other-order",
        "arguments-as-text",
        "prose-around-it",
        "the-wire-format-s-extra-keys",
        "another-tool",
        "one-call-of-two",
        "another-argument-value",
        "no-tool-twice",
        "no-tool-with-prose-around-it",
        "no-tool-against-a-call",
        "no-tool-against-prose",
    ],
)
def test_two_answers_are_one_when_the_calls_in_them_are_the_same_calls(
    one: str, other: str, same: bool
) -> None:
    """What this task means by two answers agreeing, and the reason it needs no judge.

    An answer is a tool call, so the calls are read out and matched: the order they were written
    in, the spacing, prose around them, arguments as text rather than as an object, and the keys a
    provider's wire format hangs on a call are all spellings of one answer. A different tool, a
    different argument value, or one call where another answer made two are different answers --
    and no model is asked to tell them apart.

    Read off the panel, which is the class that holds the rule.
    """
    matching = panel(JUROR)

    assert (
        matching.normalize_prediction(one) == matching.normalize_prediction(other)
    ) is same


async def test_the_same_calls_in_two_orders_are_a_majority_and_ask_no_judge() -> None:
    """The whole point, at the level the panel works: this is a majority, not a tie.

    Compared as strings these are three different answers and the panel has none, which is where
    a judge used to be paid to look at them. Matched as calls, two jurors said the same thing.
    """
    panel_of_three = StubbedPanel(
        BOTH_CALLS, BOTH_CALLS_REVERSED, CLOSE_TICKET, judged=CLOSE_TICKET
    )

    said = await panel_of_three.verdict(TURNS, BOTH_CALLS, TOOLS, "vi")

    assert said.consensus == BOTH_CALLS
    assert said.label_agreement == pytest.approx(2 / 3)
    assert panel_of_three.asked == []


# ----------------------------------------------------------------- the finetuned reviewer


async def test_a_finetuned_reviewer_is_refused_rather_than_answered_with_a_number() -> (
    None
):
    """§ *Open*: `SFTReviewerVerdict` carries a confidence and nothing says where it comes from.

    So the answer is a refusal and not an invented number -- a `ConfigError`, which is what this
    codebase calls a declaration it cannot act on, so the route answers 422 by the name that was
    ticked. `NotImplementedError` was the other option and is a 500: the caller's declaration is
    well formed, and telling them it failed inside a call would be a lie about which side is
    missing something.
    """
    reviewer = ToolDecisionSFTPrediction(SFTModelConfig(model=JUROR))

    with pytest.raises(ConfigError, match="confidence"):
        await reviewer.predict(TURNS, TOOLS, "vi")
