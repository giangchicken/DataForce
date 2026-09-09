"""`scan` over one hand-written sample: two detectors, one confirmation, and the rules over them.

The sample is the one the page draws: a name, a phone number, and an email address whose local part
*is* that phone number. That nesting is why the rules are ordered the way they are -- the email scan
claims the longer value, the phone span falling inside it is dropped, and `redacted_text` replaces
the longest value first so the text cannot come out as `minh<PHONE_1>@vd.vn`, which is neither
redacted nor intact. Each of those three took a wrong answer while the page was being built.

Both model steps are answered here rather than by a model, and which seam is stubbed follows the
rule under test. `StubbedModels` overrides the two methods, for the many tests that are about what a
detection or a confirmation *does*. `answering` stubs the library's `complete` instead, for the ones
about the steps' own contracts: that neither may raise, that a value the model did not copy is
discarded, and that what reaches the model is the config the request named.

No offset is written down. Each is read out of the review text, so a test states the rule instead of
restating the arithmetic the scan just did.
"""

import json
from collections.abc import Mapping, Sequence
from itertools import takewhile
from pathlib import Path
from typing import Any

import pytest
from agent_toolkit.file_utils import read_txt
from agent_toolkit.llm import LLMConfig
from agent_toolkit.string_utils import MAX_SLOT_FILLING_PASSES
from pydantic import ValidationError

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.data_quality import (
    SCANS,
    PersonalDataCheckingConfig,
    PersonalDataCheckingInput,
    PersonalDataDetected,
    PersonalDataSpan,
    PiiLlmConfirmed,
    PiiLlmConfirmer,
    PiiLlmDetected,
    PiiLlmFinding,
    PiiLlmSpanConfirmed,
    PiiRuleDetector,
    personal_data_checking,
)
from dataforce.modalities.text2text.data_quality.schema import (
    Language,
    RuleScan,
    VerifierModelConfig,
)
from dataforce.profile.tool_decision import data_quality
from dataforce.profile.tool_decision.data_quality import (
    PiiLlmDetector,
    ToolDecisionPersonalChecking,
    find_and_number_spans,
    order_claims_by_class,
)
from dataforce.services.tool_decision import personal_data_detect, personal_data_replace

EMAIL = "minh0912345678@vd.vn"
PHONE = "0912345678"
NAME = "Trần Văn Minh"
ADDRESS = "12 Lê Lợi, Quận 1"

SAMPLE: Mapping[str, Any] = {
    "id": "one-ticket",
    "language": "vi",
    "messages": [
        {
            "role": "user",
            "content": f"Chào em, anh {NAME}, số {PHONE}, mail {EMAIL}, ở {ADDRESS}, mở phiếu.",
        },
        {"role": "assistant", "content": "Dạ em mở phiếu hỗ trợ cho mình ngay ạ."},
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "OpenTicket",
                "description": "Mở phiếu hỗ trợ cho khách hàng.",
                "parameters": {
                    "type": "object",
                    "required": ["ma_khach", "noi_dung"],
                    "properties": {
                        "ma_khach": {"type": "string"},
                        "noi_dung": {
                            "type": "object",
                            "properties": {"tieu_de": {"type": "string"}},
                            "required": ["tieu_de"],
                        },
                    },
                },
            },
        }
    ],
    # The phone number a third time, in an argument value -- which is the whole reason the catalog
    # and the label are inside the review text.
    "label": [{"name": "OpenTicket", "arguments": {"ma_khach": PHONE}}],
}

# What a model answers about the address, as the shape it is asked for.
ADDRESS_FOUND: Mapping[str, str] = {"text": ADDRESS, "label": "ADDRESS"}

NOTHING_TO_FIND: Mapping[str, Any] = {
    "id": "quiet",
    "language": "vi",
    "messages": [{"role": "user", "content": "app lỗi từ sáng, em xem giúp anh."}],
}

VERIFIER = "a-verifier"
RESOLVED = LLMConfig(model=VERIFIER, base_url="http://a-model.invalid")


def checking_config(
    *scans: tuple[str, RuleScan], **declared: Any
) -> PersonalDataCheckingConfig:
    """What a checker is configured with: the model a request ticked, and the scans it runs.

    No scans means the four the shape defaults to. A test that brings its own is not injecting a
    seam -- declaring them is the feature, and it is how a deployment runs a scan of its own.
    """
    return PersonalDataCheckingConfig(
        verifier_model=VerifierModelConfig(model=VERIFIER, **declared),
        **({"list_scan_functions": scans} if scans else {}),
    )


@pytest.fixture(autouse=True)
def resolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every checker resolves its model when it is built, so every test needs that to answer.

    Autouse and not a helper, because it is a precondition of *constructing* the class rather than
    of any one rule. Patched at the library's own call, in both modules that make it, so every
    test here builds the real classes -- what they refuse is `test_model_config.py`'s subject.
    """
    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "resolve_config", lambda **kwargs: RESOLVED)


class StubbedModels(ToolDecisionPersonalChecking):
    """Both model steps answered here: what the model detector finds, and what is confirmed.

    `detected` is what the model reports on top of the rule scans, `{value: class}`. `confirmed` is
    the values the confirmation says are real, or `None` for every span it is shown. `asked`
    records the confirmation's call, so a test can say what it was handed and not only what came
    back.
    """

    def __init__(
        self,
        confirmed: Sequence[str] | None = None,
        detected: Mapping[str, str] | None = None,
        *,
        scans: Sequence[tuple[str, RuleScan]] = (),
    ) -> None:
        super().__init__(checking_config(*scans))
        self.confirmed = confirmed
        self.detected = dict(detected or {})
        self.asked: list[tuple[str, tuple[PersonalDataSpan, ...], str]] = []

    async def pii_llm_detect(self, text: str, language: str) -> dict[str, str]:
        return {
            value: personal_data_class
            for value, personal_data_class in self.detected.items()
            if value in text
        }

    async def pii_llm_confirm(
        self,
        checking_input: PersonalDataCheckingInput,
        text: str,
        spans: Sequence[PersonalDataSpan],
    ) -> tuple[PersonalDataSpan, ...]:
        self.asked.append((text, tuple(spans), checking_input.language))
        real = None if self.confirmed is None else set(self.confirmed)
        return tuple(
            span.model_copy(update={"reason": f"stubbed for {span.placeholder}"})
            for span in spans
            if real is None or text[span.start : span.end] in real
        )


def given(
    sample: Mapping[str, Any], language: Language = "vi"
) -> PersonalDataCheckingInput:
    """What a scan is given: this record, in this language."""
    return PersonalDataCheckingInput(sample=sample, language=language)


def answering(
    monkeypatch: pytest.MonkeyPatch,
    *,
    detected: Sequence[Mapping[str, Any]] = (),
    confirmed: Sequence[Mapping[str, Any]] | None = None,
    prompts: list[str] | None = None,
) -> None:
    """Install a `complete` that answers whichever of the two prompts it is handed.

    Patched in both modules that call it -- the detector makes its own call and so does the
    confirmation -- and one function answers both, telling them apart by the heading only the
    confirmation's prompt carries.

    `confirmed` is answered verbatim, for the tests about what an answer may say. `None` confirms
    every span the prompt shows, read off the prompt itself, so a test about anything else does
    not have to know which id each span got.
    """

    async def answered(prompt: str, **kwargs: Any) -> str:
        if prompts is not None:
            prompts.append(prompt)
        if "## Spans" not in prompt:
            return json.dumps({"detected": list(detected)})
        said = (
            confirmed
            if confirmed is not None
            else [
                {"id": int(line.split("|")[0]), "confirmed": True, "reason": "stubbed"}
                for line in section(prompt, "## Spans")
            ]
        )
        return json.dumps({"confirmed": list(said)})

    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "complete", answered)


def occurrences(text: str, value: str) -> list[int]:
    """Every offset `value` starts at in `text`, read out rather than written down."""
    found, start = [], text.find(value)
    while start >= 0:
        found.append(start)
        start = text.find(value, start + len(value))
    return found


def sliced(found: PersonalDataDetected) -> list[str]:
    """What each span's offsets actually read in the text the answer says they index."""
    return [found.review_text[span.start : span.end] for span in found.spans]


def placeholders_of(found: PersonalDataDetected, value: str) -> set[str]:
    """Every placeholder the spans over one value carry. Two is one value read as two people."""
    return {
        span.placeholder
        for span in found.spans
        if found.review_text[span.start : span.end] == value
    }


def section(prompt: str, heading: str) -> list[str]:
    """The lines under one `## heading`, up to the next blank line.

    Read positionally on purpose: a prompt with the language where the text should be contains
    both, so `in prompt` says nothing about which slot each one landed in.
    """
    lines = prompt.splitlines()
    after = lines[lines.index(heading) + 1 :]
    return list(takewhile(lambda line: line.strip(), after))


# ----------------------------------------------------------------- the frame of reference


async def test_review_text_holds_the_turns_the_catalog_and_the_label() -> None:
    """Requirement 6, and it is why the phone number is there three times rather than once.

    The turns alone would miss the argument value in the label, which is exactly where a phone
    number sits in a tool-calling sample.
    """
    text = StubbedModels().build_review_text(SAMPLE)

    assert text.startswith("user: Chào em")
    assert "assistant: Dạ em mở phiếu" in text
    assert "[OpenTicket]" in text
    assert text.endswith(
        f'label: [{{"name": "OpenTicket", "arguments": {{"ma_khach": "{PHONE}"}}}}]'
    )
    assert len(occurrences(text, PHONE)) == 3


# ----------------------------------------------------------------- the two detectors


def test_the_first_scan_to_claim_a_value_keeps_it() -> None:
    """Requirement 7, which is what the declared order is for.

    The four scans are the library's and none of them returns another's value on this sample, so
    the collision is put in on purpose: the rule under test is the detector's own, not a regex's.
    """
    detector = PiiRuleDetector(
        (
            ("EMAIL", lambda text, language: [PHONE]),
            ("PHONE", lambda text, language: [PHONE]),
        )
    )

    assert detector.detect(f"số {PHONE}", "vi") == {PHONE: "EMAIL"}


def test_a_claimed_value_that_is_not_in_the_text_is_not_detected() -> None:
    """A normalised value carries no offset, so this frame of reference cannot speak about it.

    Kept, it would earn a placeholder, no span, and a `redacted` decision over a value nothing
    ever replaced -- `+84912345678` for a text that says `0912345678`.
    """
    detector = PiiRuleDetector(
        (("PHONE", lambda text, language: ["+84912345678", PHONE]),)
    )

    assert detector.detect(f"số {PHONE}", "vi") == {PHONE: "PHONE"}


async def test_a_deployment_s_own_scan_runs_beside_the_four() -> None:
    """Which scans run is the config's, so a corpus with a shape of its own does not need a fork.

    A ticket code is nobody's library regex, and a deployment that has one hands it over as a scan
    like any other: it detects, it is confirmed, it earns `<CLASS_N>` under the class it was given,
    and it is replaced. The four defaults come with it, in front of it, because the order they are
    declared in is the order a value two of them claim is settled by.
    """
    ticket = "SR-8891"
    said = f"anh {NAME} bao loi phieu {ticket}"
    checker = StubbedModels(scans=(*SCANS, ("TICKET", lambda text, language: [ticket])))

    detected = await checker.detect(
        given({"id": "own", "messages": [{"role": "user", "content": said}]})
    )
    replaced = personal_data_replace(detected)

    assert placeholders_of(detected, ticket) == {"<TICKET_1>"}
    assert placeholders_of(detected, NAME) == {"<NAME_1>"}
    assert (
        replaced.redacted_text
        == "user: anh <NAME_1> bao loi phieu <TICKET_1>\nlabel: null"
    )
    assert replaced.outcome == "redacted"


async def test_the_model_detects_what_no_rule_scan_can() -> None:
    """Why there is a second detector at all: an address is nobody's regex.

    It is detected, confirmed, spanned and replaced like any other value, and the class the model
    named is what its placeholder reads.
    """
    detected = await StubbedModels(detected={ADDRESS: "ADDRESS"}).detect(given(SAMPLE))
    replaced = personal_data_replace(detected)

    assert placeholders_of(detected, ADDRESS) == {"<ADDRESS_1>"}
    assert replaced.redacted_text is not None
    assert ADDRESS not in replaced.redacted_text
    assert replaced.outcome == "redacted"


async def test_a_class_only_the_model_named_is_numbered_after_the_declared_four() -> (
    None
):
    """The order `<CLASS_N>` numbers in: the rule detector's classes first, then the model's.

    A declared class keeps its number wherever the model's answer put it, so adding a detector
    cannot renumber what a reviewer was already reading.

    Read off `claims` and not off the spans: `Quận 1` sits inside the address it was claimed
    beside, so its span is dropped as nested (Requirement 11) and the ordering the claims carry
    would be invisible on the answer.
    """
    checker = StubbedModels(detected={ADDRESS: "ADDRESS", "Quận 1": "DISTRICT"})

    detected = await checker.detect(given(SAMPLE))

    assert list(
        dict.fromkeys(personal_data_class for personal_data_class, _ in detected.claims)
    ) == [
        "EMAIL",
        "PHONE",
        "NAME",
        "ADDRESS",
        "DISTRICT",
    ]
    assert "DISTRICT" not in {span.personal_data_class for span in detected.spans}


async def test_a_rule_claim_wins_a_disagreement_about_a_value_s_class() -> None:
    """Both detectors may claim one value, and only one class can pick its placeholder.

    The rule scan's wins: it comes from a regex a reader can check, where the model's class is a
    judgement. The value is detected either way -- what is settled here is what it is *called*.
    """
    checker = StubbedModels(detected={PHONE: "OTP"})

    detected = await checker.detect(given(SAMPLE))

    assert placeholders_of(detected, PHONE) == {"<PHONE_1>"}


async def test_a_value_the_model_did_not_copy_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model is asked to copy, because the offsets are found by searching for what it wrote.

    A normalised number and a value with its sentence around it are the two ways that goes wrong,
    and neither can carry an offset -- so both are dropped before anything is asked to confirm.
    """
    answering(
        monkeypatch,
        detected=[
            {"text": "+84912345678", "label": "PHONE"},
            {"text": f"anh {NAME} nói", "label": "NAME"},
            {"text": ADDRESS, "label": "ADDRESS"},
        ],
    )
    checker = ToolDecisionPersonalChecking(checking_config())
    text = checker.build_review_text(SAMPLE)

    assert await checker.pii_llm_detect(text, "vi") == {ADDRESS: "ADDRESS"}


async def test_an_entry_missing_a_half_names_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`{text, label}` is the contract, and an entry missing either half names nothing.

    The scan still answers: the rule scans are local and go on detecting, so a model having a bad
    day narrows the record's precision rather than failing it.
    """
    answering(
        monkeypatch,
        detected=[
            {"text": ADDRESS},
            {"label": "ADDRESS"},
            {"text": "", "label": "ADDRESS"},
            {"text": ADDRESS, "label": ""},
        ],
    )
    checker = ToolDecisionPersonalChecking(checking_config())
    text = checker.build_review_text(SAMPLE)

    assert await checker.pii_llm_detect(text, "vi") == {}
    assert set(sliced(await checker.detect(given(SAMPLE)))) == {EMAIL, PHONE, NAME}


async def test_a_readable_finding_survives_an_unreadable_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both fields default to `""` rather than being required, and this is what that buys.

    A model that reports four values and forgets one label has still found three. Required fields
    would fail the whole answer over one entry, because a list of shapes validates every item.
    """
    answering(
        monkeypatch,
        detected=[
            {"label": "ADDRESS"},
            {"text": ADDRESS},
            {"text": NAME, "label": "NAME"},
        ],
    )
    checker = ToolDecisionPersonalChecking(checking_config())

    assert await checker.pii_llm_detect(checker.build_review_text(SAMPLE), "vi") == {
        NAME: "NAME"
    }


async def test_the_class_the_model_wrote_is_read_in_upper_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A class picks `<CLASS_N>`, and `<address_1>` beside `<ADDRESS_1>` reads as two things."""
    answering(monkeypatch, detected=[{"text": ADDRESS, "label": "home address"}])
    checker = ToolDecisionPersonalChecking(checking_config())
    text = checker.build_review_text(SAMPLE)

    assert await checker.pii_llm_detect(text, "vi") == {ADDRESS: "HOME_ADDRESS"}


# ----------------------------------------------------------------- the confirmation


async def test_the_confirmation_is_handed_the_spans_the_text_and_the_language() -> None:
    """It is asked about spans, never to find its own, and each one carries the id it answers with.

    Spans and not values, because the same characters are personal data in one line and an order
    number in another -- so the question is about where a hit sits, and the ids are what an answer
    names. The language is the input's (Decision 17) and reaches every step, so one declaration
    serves all of them.
    """
    checker = StubbedModels(detected={ADDRESS: "ADDRESS"})

    await checker.detect(given(SAMPLE))

    text, spans, language = checker.asked[0]
    assert language == "vi"
    assert text == checker.build_review_text(SAMPLE)
    assert [span.id for span in spans] == [1, 2, 3, 4, 5]
    assert [
        (span.personal_data_class, text[span.start : span.end]) for span in spans
    ] == [
        ("EMAIL", EMAIL),
        ("PHONE", PHONE),
        ("PHONE", PHONE),
        ("NAME", NAME),
        ("ADDRESS", ADDRESS),
    ]


async def test_only_a_confirmed_value_is_replaced() -> None:
    """The confirmation is what sets the precision: what it leaves out earns no span at all."""
    detected = await StubbedModels(confirmed=[EMAIL, NAME]).detect(given(SAMPLE))
    replaced = personal_data_replace(detected)

    assert placeholders_of(detected, PHONE) == set()
    assert replaced.redacted_text is not None
    assert PHONE in replaced.redacted_text
    assert replaced.outcome == "withheld"


async def test_an_answer_about_a_span_that_was_not_shown_is_discarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The modality's rule: the confirmation only ever narrows what the detectors found.

    An id no span carries is discarded -- a model that invents a number would otherwise keep
    something nobody detected, and there is no span to keep. A span answered twice keeps the first
    answer, so one answer cannot both confirm and reject. Asked of `pii_llm_confirm` directly as
    well as through the scan, because reading it off the returned spans would not show what was
    discarded on the way.
    """
    answering(
        monkeypatch,
        confirmed=[
            {"id": 99, "confirmed": True, "reason": "a span nobody has"},
            {"id": 3, "confirmed": True, "reason": "the phone in the label"},
            {"id": 3, "confirmed": False, "reason": "and now it is not"},
        ],
    )
    checker = ToolDecisionPersonalChecking(checking_config())
    text = checker.build_review_text(SAMPLE)
    claimed = checker.pii_rule_detector.detect(text, "vi")
    candidates = find_and_number_spans(
        text, order_claims_by_class(text, claimed, checker.pii_rule_detector.classes)
    )

    confirmed = await checker.pii_llm_confirm(given(SAMPLE), text, candidates)
    detected = await checker.detect(given(SAMPLE))
    replaced = personal_data_replace(detected)

    assert [(span.id, span.reason) for span in confirmed] == [
        (3, "the phone in the label")
    ]
    assert [span.id for span in detected.spans] == [3]
    assert sliced(detected) == [PHONE]
    assert replaced.outcome == "withheld"


async def test_a_confirmed_span_carries_the_reason_it_was_confirmed_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The confirmation answers `{id, confirmed, reason}` per span, and the reason is a reviewer's.

    It is the one thing on a span that no rule here computes: why those characters are personal
    data in this text. A span nothing confirmed is not returned at all, so every reason on the
    answer belongs to a span that ships redacted.
    """
    answering(
        monkeypatch,
        confirmed=[
            {"id": 1, "confirmed": True, "reason": "địa chỉ email của khách"},
            {"id": 2, "confirmed": False, "reason": "trùng trong địa chỉ email"},
        ],
    )
    checker = ToolDecisionPersonalChecking(checking_config())

    detected = await checker.detect(given(SAMPLE))

    assert [(span.id, span.reason) for span in detected.spans] == [
        (1, "địa chỉ email của khách")
    ]
    assert sliced(detected) == [EMAIL]


async def test_nothing_detected_is_nobody_asked_to_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The confirmation is about a list, so an empty one has nothing to ask about.

    A model asked to confirm nothing is one call and one bill per clean record, and its answer
    could only hold a value no detector claimed.
    """
    prompts: list[str] = []
    answering(monkeypatch, prompts=prompts)

    detected = await ToolDecisionPersonalChecking(checking_config()).detect(
        given(NOTHING_TO_FIND)
    )
    replaced = personal_data_replace(detected)

    assert replaced.outcome == "reported"
    assert len(prompts) == 1
    assert "## Detected" not in prompts[0]


# ----------------------------------------------------------------- the spans and the copy


async def test_every_returned_offset_slices_back_to_its_value() -> None:
    """§ *Invariants*, first line: a span's offsets index the review text and nothing else.

    The detectors answer with values, so the offsets are this code's own arithmetic -- and an
    off-by-one in it is invisible until something slices with it. Pinned exactly, spans and
    offsets both, because "one of the three values" would pass on a span a character short.
    """
    detected = await StubbedModels().detect(given(SAMPLE))
    text = detected.review_text

    assert sliced(detected) == [EMAIL, PHONE, PHONE, NAME]
    assert [span.personal_data_class for span in detected.spans] == [
        "EMAIL",
        "PHONE",
        "PHONE",
        "NAME",
    ]
    assert [span.start for span in detected.spans] == [
        text.index(EMAIL),
        occurrences(text, PHONE)[0],
        occurrences(text, PHONE)[2],
        text.index(NAME),
    ]


async def test_a_value_said_twice_keeps_one_placeholder() -> None:
    """Requirement 10. The phone number is in a turn, inside the email, and in the label.

    Two placeholders over one value is two people as far as anything reading the row can tell,
    which is what co-referent means here.
    """
    detected = await StubbedModels().detect(given(SAMPLE))

    assert len(occurrences(detected.review_text, PHONE)) == 3
    assert placeholders_of(detected, PHONE) == {"<PHONE_1>"}
    assert (
        len([span for span in detected.spans if span.placeholder == "<PHONE_1>"]) == 2
    )
    assert placeholders_of(detected, EMAIL) == {"<EMAIL_1>"}
    assert placeholders_of(detected, NAME) == {"<NAME_1>"}


async def test_the_digit_run_inside_the_email_earns_no_span() -> None:
    """Requirement 11's case as the page draws it, whichever of the two rules drops it.

    The email scan claims the longer value; the phone-shaped digit run inside it is a *different*
    value, so nothing about the values says one sits in the other -- the offsets do, and so does
    the `h` the run butts against.
    """
    detected = await StubbedModels().detect(given(SAMPLE))
    text = detected.review_text
    inside = occurrences(text, PHONE)[1]
    starts = [span.start for span in detected.spans]

    assert text.index(EMAIL) < inside < text.index(EMAIL) + len(EMAIL)
    assert inside not in starts
    assert occurrences(text, PHONE)[0] in starts
    assert occurrences(text, PHONE)[2] in starts


async def test_a_span_inside_a_longer_span_is_dropped() -> None:
    """Requirement 11 on its own, over a shorter value the word boundary cannot reject.

    `Văn` sits inside `Trần Văn Minh` with a space on each side, so it is a legitimate occurrence
    of its own value and only the offsets say it is inside another span. Both rules drop something
    and neither covers the other: the boundary reads the characters around an occurrence, the
    outermost rule reads the spans around it.
    """
    checker = StubbedModels(scans=(("NAME", lambda text, language: [NAME, "Văn"]),))

    detected = await checker.detect(
        given(
            {
                "id": "nested",
                "messages": [{"role": "user", "content": f"anh {NAME} noi"}],
            }
        )
    )
    replaced = personal_data_replace(detected)

    assert [span.placeholder for span in detected.spans] == ["<NAME_1>"]
    assert replaced.redacted_text == "user: anh <NAME_1> noi\nlabel: null"
    # And the dropped span is not a value left over: `Văn` went with the name it sat inside, so
    # every detected value resolved and the scan says `redacted` rather than holding the record.
    assert replaced.outcome == "redacted"


async def test_an_occurrence_butting_against_a_word_character_is_not_one() -> None:
    """The offsets are found by searching for a value, and a search knows no word boundary.

    The phone scan asserts one in its own regex, so a 10-digit run inside a 14-digit order number
    is not a phone number it claimed -- and a span there reports a stranger's order as the
    customer's number.

    What the copy does with that order number is *not* fixed by the boundary and is pinned here as
    it behaves: replacement is by value, so the run inside it goes too and the row reads
    `<PHONE_1>9012`. Requirement 12 asks for replacement by value and § *The store* calls this cut
    undecided; the boundary keeps the scan from *reporting* the order number, which is the half
    this code owns.
    """
    said = "so 0912345678 va don hang 09123456789012"

    detected = await StubbedModels().detect(
        given({"id": "order", "messages": [{"role": "user", "content": said}]})
    )
    replaced = personal_data_replace(detected)

    assert [(span.start, span.end) for span in detected.spans] == [
        (
            detected.review_text.index(PHONE),
            detected.review_text.index(PHONE) + len(PHONE),
        )
    ]
    assert replaced.redacted_text is not None
    assert "<PHONE_1>9012" in replaced.redacted_text
    assert replaced.outcome == "redacted"


async def test_the_longest_value_is_replaced_first() -> None:
    """Requirement 12, and the string this keeps out of the row: `minh<PHONE_1>@vd.vn`.

    Replacement is by value over the whole text, so a shorter value inside a longer one cuts it in
    half unless the longer one goes first.
    """
    detected = await StubbedModels().detect(given(SAMPLE))
    replaced = personal_data_replace(detected)

    assert replaced.redacted_text is not None
    assert "minh<PHONE_1>@vd.vn" not in replaced.redacted_text
    assert "<EMAIL_1>" in replaced.redacted_text
    assert replaced.redacted_text.count("<PHONE_1>") == 2
    for value in (EMAIL, PHONE, NAME):
        assert value not in replaced.redacted_text


async def test_two_addresses_each_get_their_own_placeholder() -> None:
    """Per-class numbering over the real detector, so `_2` is a rendering something has read."""
    detected = await StubbedModels().detect(
        given(
            {
                "id": "two",
                "messages": [
                    {"role": "user", "content": "mail anh@vd.vn, cc chi@vd.vn nhe"},
                ],
            }
        )
    )
    replaced = personal_data_replace(detected)

    assert placeholders_of(detected, "anh@vd.vn") == {"<EMAIL_1>"}
    assert placeholders_of(detected, "chi@vd.vn") == {"<EMAIL_2>"}
    assert (
        replaced.redacted_text == "user: mail <EMAIL_1>, cc <EMAIL_2> nhe\nlabel: null"
    )
    assert replaced.outcome == "redacted"


async def test_a_class_with_two_values_numbers_them_in_first_appearance_order() -> None:
    """Requirement 10's other half: `N` follows the text, not the order a detector answered in.

    The scan is made to answer out of order on purpose. A detector that returns its matches in
    some other order -- or a fifth one that does -- would otherwise hand a reviewer `<EMAIL_2>`
    for the address the text says first, and nothing would say so.
    """
    # `b` first in the text and `a` first alphabetically, so a sort that is not by appearance
    # cannot land on the same answer by luck.
    first, second = "b@vd.vn", "a@vd.vn"
    checker = StubbedModels(scans=(("EMAIL", lambda text, language: [second, first]),))
    said = f"mail {first} va {second}"
    reading = given({"id": "two", "messages": [{"role": "user", "content": said}]})

    detected = await checker.detect(reading)

    assert placeholders_of(detected, first) == {"<EMAIL_1>"}
    assert placeholders_of(detected, second) == {"<EMAIL_2>"}


# ----------------------------------------------------------------- the copy and the outcome


async def test_the_outcome_is_reported_where_nothing_was_detected() -> None:
    """Requirement 13's first case: nothing was rewritten, so there is nothing to hold back."""
    detected = await StubbedModels().detect(given(NOTHING_TO_FIND))
    replaced = personal_data_replace(detected)

    assert detected.spans == ()
    assert replaced.redacted_text is None
    assert replaced.outcome == "reported"


async def test_the_outcome_is_redacted_where_every_detected_value_resolved() -> None:
    """Requirement 13's second case: the copy was made and the confirmation confirmed all of it."""
    detected = await StubbedModels().detect(given(SAMPLE))
    replaced = personal_data_replace(detected)

    assert replaced.outcome == "redacted"


async def test_a_value_cut_in_half_is_withheld_rather_than_redacted() -> None:
    """Requirement 13, and the case Requirement 11 does not answer: spans that overlap in part.

    Two names sharing a word -- `anh` is a title cue *and* a common given name, so the real
    detector claims `Trần Văn Anh Minh` and `Minh Hoàng Long` off one sentence. Neither contains
    the other, so both keep a span; replacement is by value, so the second finds a string the
    first already cut and its placeholder never lands. Which span should win is undecided. What is
    decided is that a copy holding half of a value is not that value redacted.
    """
    detected = await StubbedModels().detect(
        given(
            {
                "id": "overlap",
                "messages": [
                    {
                        "role": "user",
                        "content": "Chào em, anh Trần Văn Anh Minh Hoàng Long.",
                    }
                ],
            }
        )
    )
    replaced = personal_data_replace(detected)

    assert [span.placeholder for span in detected.spans] == ["<NAME_1>", "<NAME_2>"]
    assert replaced.redacted_text is not None
    assert "<NAME_1>" in replaced.redacted_text
    assert "<NAME_2>" not in replaced.redacted_text
    assert replaced.outcome == "withheld"


# ----------------------------------------------------------------- what may not raise


@pytest.mark.parametrize(
    "declared",
    [None, "", "   ", 0, ["vi"], "Tiếng việt", "fr"],
    ids=["null", "blank", "spaces", "a-list", "spelled-out", "unsupported", "another"],
)
async def test_a_language_the_scans_cannot_read_is_refused(declared: Any) -> None:
    """Decision 17, and it is the shape that holds it: the input takes `vi` or `en`, nothing else.

    Every rule scan and both model steps take that one value, and `agent_toolkit` keys its `vi`
    and `en` tables by it -- a third value reaches the library as a dictionary lookup and raises a
    `KeyError` from inside it, which is nobody's answer. `Tiếng việt` is in the list because that
    is what a reader would write for Vietnamese, and it is exactly the value the library cannot
    take. `null` too: a caller declaring nothing takes the default the shape states, and is not
    one declaring a language of nothing.

    Refused twice over, because a shape's `ValidationError` is a 500 wherever nobody turns it into
    this codebase's one exception: `personal_data_detect` is that boundary, so the endpoint
    answers 422 and names the record it could not read.
    """
    with pytest.raises(ValidationError):
        PersonalDataCheckingInput(sample=SAMPLE, language=declared)

    with pytest.raises(ConfigError, match="language"):
        await personal_data_detect(checking_config(), SAMPLE, declared)


async def test_a_record_that_says_nothing_about_its_language_is_scanned_in_vietnamese(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The input's default, and it is Vietnamese because that is the corpus this serves.

    Not a guess at what the turns are in: a declaration a caller did not make takes the value the
    shape states, which a reader sees without running anything. A corpus in another language
    declares `en` per record, and one in a language `agent_toolkit` has no tables for cannot be
    scanned by these rules at all.
    """
    prompts: list[str] = []
    answering(monkeypatch, prompts=prompts)
    quiet = {key: value for key, value in NOTHING_TO_FIND.items() if key != "language"}
    checking_input = PersonalDataCheckingInput(sample=quiet)

    assert checking_input.language == "vi"

    detected = await ToolDecisionPersonalChecking(checking_config()).detect(
        checking_input
    )

    assert personal_data_replace(detected).outcome == "reported"
    assert section(prompts[0], "## Conversation Language") == ["vi"]


async def test_a_failed_call_answers_nothing_and_says_so_on_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Requirement 8 and § *Error Behavior*: neither step may raise, and a failure is an event.

    Both steps fail here. The model detector answers nothing, which leaves the rule scans' values
    detected; the confirmation then confirms none of them, so nothing is replaced and the decision
    is `withheld` rather than `reported` -- a rewrite was asked for and did not happen. One JSON
    object per failure on stdout, each naming the step, and never a log file (`H-6`).
    """

    async def refused(prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("the endpoint hung up")

    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "complete", refused)

    detected = await ToolDecisionPersonalChecking(checking_config()).detect(
        given(SAMPLE)
    )
    replaced = personal_data_replace(detected)

    assert detected.spans == ()
    assert replaced.redacted_text is None
    assert replaced.outcome == "withheld"
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["event"] for event in events] == [
        "pii_llm_detect_failed",
        "pii_llm_confirm_failed",
    ]
    assert {event["model"] for event in events} == {VERIFIER}
    assert all("RuntimeError" in event["error"] for event in events)


async def test_an_answer_of_the_wrong_shape_is_not_an_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A model answering prose answers nothing, and says so where a failed call would.

    The shape is what makes that readable: validating against `PiiLlmDetected` and
    `PiiLlmConfirmed` is one check with one message, where a walk through `isinstance` would
    return an empty answer and leave nobody any wiser.
    """

    async def prose(prompt: str, **kwargs: Any) -> str:
        return "I found several things, let me explain."

    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "complete", prose)

    detected = await ToolDecisionPersonalChecking(checking_config()).detect(
        given(SAMPLE)
    )
    replaced = personal_data_replace(detected)

    assert detected.spans == ()
    assert replaced.outcome == "withheld"
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["event"] for event in events] == [
        "pii_llm_detect_failed",
        "pii_llm_confirm_failed",
    ]
    assert all("ValidationError" in event["error"] for event in events)


@pytest.mark.parametrize(
    "missing",
    ["PII_LLM_DETECT_PROMPT", "PII_LLM_CONFIRM_PROMPT"],
    ids=["detect", "confirm"],
)
async def test_a_missing_prompt_is_not_a_failed_call(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """Neither step may raise on a *call*, which is not licence to swallow a declaration error.

    Each prompt is built outside the `try` for exactly this: a deployment with no prompt file
    would otherwise scan every record, answer nothing, and report itself as a provider having a
    bad day.
    """
    answering(monkeypatch)
    holder = (
        data_quality if missing == "PII_LLM_DETECT_PROMPT" else personal_data_checking
    )
    monkeypatch.setattr(holder, missing, Path("nowhere.txt"))

    with pytest.raises(ConfigError, match="nowhere.txt"):
        await ToolDecisionPersonalChecking(checking_config()).detect(given(SAMPLE))


# ----------------------------------------------------------------- the two prompts


async def test_the_detect_prompt_carries_the_language_and_the_text() -> None:
    """`pii_llm_detect.txt`, filled: `{{language}}` and `{{review_text}}`, and no slot left.

    The detected values are not among them -- this is the prompt that finds them -- and each value
    is under its own heading, because two slots filled with each other's value is a prompt that
    reads as nonsense and passes a containment check.
    """
    checker = StubbedModels()
    text = checker.build_review_text(SAMPLE)

    prompt = checker.build_pii_llm_detect_prompt(text, "vi")

    assert "{{" not in prompt
    assert section(prompt, "## Conversation Language") == ["vi"]
    assert section(prompt, "## Text Under Review") == text.splitlines()
    for field in (*PiiLlmDetected.model_fields, *PiiLlmFinding.model_fields):
        assert f'"{field}"' in prompt, field


async def test_the_confirm_prompt_carries_the_language_the_text_and_the_spans() -> None:
    """`pii_llm_confirm.txt`, filled: the three slots, one `id | CLASS | value` per span.

    The modality's file, because the question is about personal data and not about the kind of
    sample it was found in -- the same reason `pii_llm_confirm` has a body there. The id is in the
    line because it is what the answer names.
    """
    checker = StubbedModels()
    text = checker.build_review_text(SAMPLE)
    spans = find_and_number_spans(text, (("EMAIL", EMAIL), ("NAME", NAME)))

    prompt = checker.build_pii_llm_confirm_prompt(given(SAMPLE), text, spans)

    assert "{{" not in prompt
    assert section(prompt, "## Conversation Language") == ["vi"]
    assert section(prompt, "## Text Under Review") == text.splitlines()
    assert section(prompt, "## Spans") == [
        f"1 | EMAIL | {EMAIL}",
        f"2 | NAME | {NAME}",
    ]
    for field in (*PiiLlmConfirmed.model_fields, *PiiLlmSpanConfirmed.model_fields):
        assert f'"{field}"' in prompt, field


async def test_a_sample_quoting_a_slot_name_is_refilled_until_the_toolkit_stops() -> (
    None
):
    """What `agent_toolkit.slot_filling` does with a record that quotes a slot name, pinned as is.

    It re-scans what it has filled until nothing changes, so a conversation quoting
    `{{review_text}}` gets its own text substituted into itself, pass after pass, until
    `MAX_SLOT_FILLING_PASSES` stops it -- the prompt grows by the record's length each pass and
    one slot is still unfilled at the end. Bounded and wasteful rather than wrong, and it is the
    library's fill (`I6`) rather than one written here.

    Held by a test because it is what a reviewer would otherwise discover on a bill: a record can
    quote a slot name by accident, and nothing about the answer would look wrong.
    """
    checker = StubbedModels()
    quoted = {
        "id": "quoting",
        "messages": [
            {"role": "user", "content": "anh noi {{review_text}} va {{language}}"}
        ],
    }
    text = checker.build_review_text(quoted)

    prompt = checker.build_pii_llm_detect_prompt(text, "vi")
    template = read_txt(data_quality.PII_LLM_DETECT_PROMPT)

    assert "{{language}}" not in prompt
    assert prompt.count("{{review_text}}") == 1
    assert (
        len(template)
        < len(prompt)
        < len(template) + MAX_SLOT_FILLING_PASSES * len(text)
    )


# ----------------------------------------------------------------- which model is asked


async def test_both_steps_ask_the_model_the_request_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 10, and one resolution per step rather than one per record.

    What the part carries is what the library is handed; the merge is its own. Both steps resolve
    the one name the request ticked, and the `settings` it declared reach the call untouched --
    without this a scan could ask some other deployment's endpoint and every other test would
    still pass.
    """
    resolved: list[Mapping[str, Any]] = []
    asked: list[Mapping[str, Any]] = []

    def resolving(**kwargs: Any) -> LLMConfig:
        resolved.append(kwargs)
        return RESOLVED

    async def answered(prompt: str, **kwargs: Any) -> str:
        asked.append(kwargs)
        return json.dumps({"detected": [ADDRESS_FOUND], "confirmed": [ADDRESS]})

    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "resolve_config", resolving)
        monkeypatch.setattr(module, "complete", answered)
    checker = ToolDecisionPersonalChecking(
        checking_config(
            base_url="http://asked-for.invalid/v1",
            api_key="the-key",
            settings={"temperature": 0.0},
        )
    )
    await checker.detect(given(SAMPLE))

    declared = {
        "model": VERIFIER,
        "base_url": "http://asked-for.invalid/v1",
        "api_key": "the-key",
    }
    # Twice, and not once: each step resolves its own. Once per step and never once per record.
    assert resolved == [declared, declared]
    assert checker.pii_llm_confirmer.model is RESOLVED
    assert checker.pii_llm_detector.model is RESOLVED
    # Both calls, and not the last one: each step makes its own, so a step that dropped what the
    # request declared would otherwise pass on the other's call.
    assert len(asked) == 2
    for call in asked:
        assert call["model"] == RESOLVED.model
        assert call["base_url"] == RESOLVED.base_url
        assert call["api_key"] == RESOLVED.api_key
        assert call["temperature"] == 0.0


def test_each_step_is_its_own_object_over_one_model() -> None:
    """Two steps, two objects, one model: a detector detects and a confirmer confirms.

    They ask the same model, because a deployment ticked one name -- and they are separate classes
    because what they *do* with an answer is not the same rule, each holding the whole of its own
    asking. Which step each one names on stdout is not read off an attribute here: the two failure
    tests read the events themselves, which is the thing a reader of the row actually sees.

    Three objects and all three built with the checker, because what each one needs -- the scans
    and the model -- is the config's and there before any record is.
    """
    checker = ToolDecisionPersonalChecking(checking_config())

    assert isinstance(checker.pii_rule_detector, PiiRuleDetector)
    assert isinstance(checker.pii_llm_detector, PiiLlmDetector)
    assert isinstance(checker.pii_llm_confirmer, PiiLlmConfirmer)
    assert checker.pii_llm_detector.model is checker.pii_llm_confirmer.model
    assert checker.pii_rule_detector.classes == (
        "EMAIL",
        "PHONE",
        "OTP",
        "NAME",
    )
