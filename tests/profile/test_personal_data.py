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
    group_spans_by_path,
    order_claims_by_class,
    replace_node,
)
from dataforce.profile.tool_decision.utils import build_review_text
from dataforce.services.tool_decision import (
    detect_personal_data,
    list_personal_data_classes,
    number_personal_data_spans,
    redact_personal_data,
)

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


def build_checking_config(
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


class StubbedLlmDetector(PiiLlmDetector):
    """The model detector answered from a dict, so a test about the arithmetic makes no call.

    It keeps the detector's own rule that a value not in the text verbatim is dropped: a stub that
    answered values the text does not hold would let a test claim an offset nothing can carry.
    """

    def __init__(self, detected: Mapping[str, str]) -> None:
        super().__init__(VerifierModelConfig(model=VERIFIER))
        self.detected = dict(detected)

    async def detect(self, prompt: str, text: str) -> dict[str, str]:
        return {
            value: personal_data_class
            for value, personal_data_class in self.detected.items()
            if value in text
        }


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
        super().__init__(build_checking_config(*scans))
        self.confirmed = confirmed
        self.pii_llm_detector = StubbedLlmDetector(detected or {})
        self.asked: list[tuple[str, tuple[PersonalDataSpan, ...], str]] = []

    async def confirm_pii_by_llm(
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


async def read_llm_claims(
    checker: ToolDecisionPersonalChecking, text: str, language: Language = "vi"
) -> dict[str, str]:
    """What the model detector claims about `text`, asked the way the scan asks it."""
    return await checker.pii_llm_detector.detect(
        checker.build_pii_llm_detect_prompt(text, language), text
    )


def build_scan_input(
    sample: Mapping[str, Any], language: Language = "vi"
) -> PersonalDataCheckingInput:
    """What a scan is given: this record, in this language."""
    return PersonalDataCheckingInput(sample=sample, language=language)


def install_model_answers(
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
                for line in read_section(prompt, "## Spans")
            ]
        )
        return json.dumps({"confirmed": list(said)})

    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "complete", answered)


def find_occurrences(text: str, value: str) -> list[int]:
    """Every offset `value` starts at in `text`, read out rather than written down."""
    found, start = [], text.find(value)
    while start >= 0:
        found.append(start)
        start = text.find(value, start + len(value))
    return found


def read_span_value(record: Mapping[str, Any], span: PersonalDataSpan) -> str:
    """What one span's offsets actually read, in the string its `path` names.

    Not `review_text[start:end]`: the text is a rendering and the offsets are the record's.
    """
    node: Any = record
    for step in span.path:
        node = node[step]
    said: str = node
    return said[span.start : span.end]


def read_span_slices(
    found: PersonalDataDetected, record: Mapping[str, Any] = SAMPLE
) -> list[str]:
    """What each span's offsets actually read, in the record the answer says they index."""
    return [read_span_value(record, span) for span in found.spans]


def build_span(
    record: Mapping[str, Any],
    path: tuple[str | int, ...],
    value: str,
    personal_data_class: str,
    placeholder: str,
    id: int,
) -> PersonalDataSpan:
    """One span a reviewer typed, with its offsets found in its own field rather than written."""
    node: Any = record
    for step in path:
        node = node[step]
    said: str = node
    return PersonalDataSpan(
        id=id,
        path=path,
        start=said.index(value),
        end=said.index(value) + len(value),
        personal_data_class=personal_data_class,
        placeholder=placeholder,
    )


def list_placeholders(
    found: PersonalDataDetected, value: str, record: Mapping[str, Any] = SAMPLE
) -> set[str]:
    """Every placeholder the spans over one value carry. Two is one value read as two people."""
    return {
        span.placeholder
        for span in found.spans
        if read_span_value(record, span) == value
    }


def read_section(prompt: str, heading: str) -> list[str]:
    """The lines under one `## heading`, up to the next blank line.

    Read positionally on purpose: a prompt with the language where the text should be contains
    both, so `in prompt` says nothing about which slot each one landed in.
    """
    lines = prompt.splitlines()
    after = lines[lines.index(heading) + 1 :]
    return list(takewhile(lambda line: line.strip(), after))


# ----------------------------------------------------------------- the frame of reference


async def test_review_text_holds_the_turns_the_catalog_and_the_label() -> None:
    """The frame of reference is turns, catalog and label together, which is why the phone number
    is there three times rather than once.

    The turns alone would miss the argument value in the label, which is exactly where a phone
    number sits in a tool-calling sample.
    """
    text = build_review_text(SAMPLE)

    assert text.startswith("user: Chào em")
    assert "assistant: Dạ em mở phiếu" in text
    assert "[OpenTicket]" in text
    assert text.endswith(
        f'label: [{{"name": "OpenTicket", "arguments": {{"ma_khach": "{PHONE}"}}}}]'
    )
    assert len(find_occurrences(text, PHONE)) == 3


# ----------------------------------------------------------------- the two detectors


def test_the_first_scan_to_claim_a_value_keeps_it() -> None:
    """Two scans claiming one value: the first keeps it, which is what the declared order is for.

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

    scanned = build_scan_input(
        {"id": "own", "messages": [{"role": "user", "content": said}]}
    )
    detected = await checker.detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert list_placeholders(detected, ticket, scanned.sample) == {"<TICKET_1>"}
    assert list_placeholders(detected, NAME, scanned.sample) == {"<NAME_1>"}
    assert (
        redacted.review_text
        == "user: anh <NAME_1> bao loi phieu <TICKET_1>\nlabel: null"
    )
    assert redacted.outcome == "redacted"


async def test_the_model_detects_what_no_rule_scan_can() -> None:
    """Why there is a second detector at all: an address is nobody's regex.

    It is detected, confirmed, spanned and replaced like any other value, and the class the model
    named is what its placeholder reads.
    """
    scanned = build_scan_input(SAMPLE)
    detected = await StubbedModels(detected={ADDRESS: "ADDRESS"}).detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert list_placeholders(detected, ADDRESS) == {"<ADDRESS_1>"}
    assert redacted.review_text is not None
    assert ADDRESS not in redacted.review_text
    assert redacted.outcome == "redacted"


async def test_a_class_only_the_model_named_is_numbered_after_the_declared_four() -> (
    None
):
    """The order `<CLASS_N>` numbers in: the rule detector's classes first, then the model's.

    A declared class keeps its number wherever the model's answer put it, so adding a detector
    cannot renumber what a reviewer was already reading.

    Read off `claims` and not off the spans: `Quận 1` sits inside the address it was claimed
    beside, so its span is dropped as nested and the ordering the claims carry
    would be invisible on the answer.
    """
    checker = StubbedModels(detected={ADDRESS: "ADDRESS", "Quận 1": "DISTRICT"})

    detected = await checker.detect(build_scan_input(SAMPLE))

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

    detected = await checker.detect(build_scan_input(SAMPLE))

    assert list_placeholders(detected, PHONE) == {"<PHONE_1>"}


async def test_a_value_the_model_did_not_copy_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model is asked to copy, because the offsets are found by searching for what it wrote.

    A normalised number and a value with its sentence around it are the two ways that goes wrong,
    and neither can carry an offset -- so both are dropped before anything is asked to confirm.
    """
    install_model_answers(
        monkeypatch,
        detected=[
            {"text": "+84912345678", "label": "PHONE"},
            {"text": f"anh {NAME} nói", "label": "NAME"},
            {"text": ADDRESS, "label": "ADDRESS"},
        ],
    )
    checker = ToolDecisionPersonalChecking(build_checking_config())
    text = build_review_text(SAMPLE)

    assert await read_llm_claims(checker, text) == {ADDRESS: "ADDRESS"}


async def test_an_entry_missing_a_half_names_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`{text, label}` is the contract, and an entry missing either half names nothing.

    The scan still answers: the rule scans are local and go on detecting, so a model having a bad
    day narrows the record's precision rather than failing it.
    """
    install_model_answers(
        monkeypatch,
        detected=[
            {"text": ADDRESS},
            {"label": "ADDRESS"},
            {"text": "", "label": "ADDRESS"},
            {"text": ADDRESS, "label": ""},
        ],
    )
    checker = ToolDecisionPersonalChecking(build_checking_config())
    text = build_review_text(SAMPLE)

    assert await read_llm_claims(checker, text) == {}
    assert set(read_span_slices(await checker.detect(build_scan_input(SAMPLE)))) == {
        EMAIL,
        PHONE,
        NAME,
    }


async def test_a_readable_finding_survives_an_unreadable_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both fields default to `""` rather than being required, and this is what that buys.

    A model that reports four values and forgets one label has still found three. Required fields
    would fail the whole answer over one entry, because a list of shapes validates every item.
    """
    install_model_answers(
        monkeypatch,
        detected=[
            {"label": "ADDRESS"},
            {"text": ADDRESS},
            {"text": NAME, "label": "NAME"},
        ],
    )
    checker = ToolDecisionPersonalChecking(build_checking_config())

    assert await read_llm_claims(checker, build_review_text(SAMPLE)) == {NAME: "NAME"}


async def test_the_class_the_model_wrote_is_read_in_upper_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A class picks `<CLASS_N>`, and `<address_1>` beside `<ADDRESS_1>` reads as two things."""
    install_model_answers(
        monkeypatch, detected=[{"text": ADDRESS, "label": "home address"}]
    )
    checker = ToolDecisionPersonalChecking(build_checking_config())
    text = build_review_text(SAMPLE)

    assert await read_llm_claims(checker, text) == {ADDRESS: "HOME_ADDRESS"}


# ----------------------------------------------------------------- the confirmation


async def test_the_confirmation_is_handed_the_spans_the_text_and_the_language() -> None:
    """It is asked about spans, never to find its own, and each one carries the id it answers with.

    Spans and not values, because the same characters are personal data in one line and an order
    number in another -- so the question is about where a hit sits, and the ids are what an answer
    names. The language is the input's and reaches every step, so one declaration
    serves all of them.
    """
    checker = StubbedModels(detected={ADDRESS: "ADDRESS"})

    await checker.detect(build_scan_input(SAMPLE))

    text, spans, language = checker.asked[0]
    assert language == "vi"
    assert text == build_review_text(SAMPLE)
    assert [span.id for span in spans] == [1, 2, 3, 4, 5]
    # Read through the span's own `path`: the offsets index the field it is in, and the text
    # above is what the model is shown rather than what they index.
    assert [
        (span.personal_data_class, read_span_value(SAMPLE, span)) for span in spans
    ] == [
        ("EMAIL", EMAIL),
        ("PHONE", PHONE),
        ("PHONE", PHONE),
        ("NAME", NAME),
        ("ADDRESS", ADDRESS),
    ]


async def test_a_stand_in_the_reviewer_retyped_is_what_the_outcome_is_measured_against() -> (
    None
):
    """The reviewer retypes a placeholder, and the record is still clean.

    Two spellings of one province standing in for one `<PROVINCE_ADDRESS_1>` is a corpus saying
    they are one place, and the page offers that. A rule measuring the copy against the numbering
    *this file* would have given answers `withheld` for a record nothing is wrong with -- the
    value is gone, which is the only question the law asks of it.
    """
    scanned = build_scan_input(SAMPLE)
    detected = await StubbedModels().detect(scanned)
    retyped = detected.model_copy(
        update={
            "spans": tuple(
                span.model_copy(update={"placeholder": "<KEPT_9>"})
                for span in detected.spans
            )
        }
    )

    redacted = redact_personal_data(retyped, scanned.sample)

    assert redacted.review_text is not None
    assert "<KEPT_9>" in redacted.review_text
    for value in (PHONE, EMAIL, NAME):
        assert value not in redacted.review_text
    assert redacted.outcome == "redacted"


async def test_only_a_confirmed_value_is_replaced() -> None:
    """The confirmation is what sets the precision: what it leaves out earns no span at all."""
    scanned = build_scan_input(SAMPLE)
    detected = await StubbedModels(confirmed=[EMAIL, NAME]).detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert list_placeholders(detected, PHONE) == set()
    assert redacted.review_text is not None
    assert PHONE in redacted.review_text
    assert redacted.outcome == "withheld"


async def test_an_answer_about_a_span_that_was_not_shown_is_discarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The modality's rule: the confirmation only ever narrows what the detectors found.

    An id no span carries is discarded -- a model that invents a number would otherwise keep
    something nobody detected, and there is no span to keep. A span answered twice keeps the first
    answer, so one answer cannot both confirm and reject. Asked of `confirm_pii_by_llm` directly as
    well as through the scan, because reading it off the returned spans would not show what was
    discarded on the way.
    """
    install_model_answers(
        monkeypatch,
        confirmed=[
            {"id": 99, "confirmed": True, "reason": "a span nobody has"},
            {"id": 3, "confirmed": True, "reason": "the phone in the label"},
            {"id": 3, "confirmed": False, "reason": "and now it is not"},
        ],
    )
    checker = ToolDecisionPersonalChecking(build_checking_config())
    text = build_review_text(SAMPLE)
    claimed = checker.pii_rule_detector.detect(text, "vi")
    candidates = find_and_number_spans(
        text, order_claims_by_class(text, claimed, checker.pii_rule_detector.classes)
    )

    confirmed = await checker.confirm_pii_by_llm(
        build_scan_input(SAMPLE), text, candidates
    )
    scanned = build_scan_input(SAMPLE)
    detected = await checker.detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert [(span.id, span.reason) for span in confirmed] == [
        (3, "the phone in the label")
    ]
    assert [span.id for span in detected.spans] == [3]
    assert read_span_slices(detected) == [PHONE]
    assert redacted.outcome == "withheld"


async def test_a_confirmed_span_carries_the_reason_it_was_confirmed_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The confirmation answers `{id, confirmed, reason}` per span, and the reason is a reviewer's.

    It is the one thing on a span that no rule here computes: why those characters are personal
    data in this text. A span nothing confirmed is not returned at all, so every reason on the
    answer belongs to a span that ships redacted.
    """
    install_model_answers(
        monkeypatch,
        confirmed=[
            {"id": 1, "confirmed": True, "reason": "địa chỉ email của khách"},
            {"id": 2, "confirmed": False, "reason": "trùng trong địa chỉ email"},
        ],
    )
    checker = ToolDecisionPersonalChecking(build_checking_config())

    detected = await checker.detect(build_scan_input(SAMPLE))

    assert [(span.id, span.reason) for span in detected.spans] == [
        (1, "địa chỉ email của khách")
    ]
    assert read_span_slices(detected) == [EMAIL]


async def test_nothing_detected_is_nobody_asked_to_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The confirmation is about a list, so an empty one has nothing to ask about.

    A model asked to confirm nothing is one call and one bill per clean record, and its answer
    could only hold a value no detector claimed.
    """
    prompts: list[str] = []
    install_model_answers(monkeypatch, prompts=prompts)

    scanned = build_scan_input(NOTHING_TO_FIND)
    detected = await ToolDecisionPersonalChecking(build_checking_config()).detect(
        scanned
    )
    redacted = redact_personal_data(detected, scanned.sample)

    assert redacted.outcome == "reported"
    assert len(prompts) == 1
    assert "## Detected" not in prompts[0]


# ----------------------------------------------------------------- the spans and the copy


async def test_every_returned_offset_slices_back_to_its_value() -> None:
    """§ *Invariants*, first line: a span's offsets index the review text and nothing else.

    The detectors answer with values, so the offsets are this code's own arithmetic -- and an
    off-by-one in it is invisible until something slices with it. Pinned exactly, spans and
    offsets both, because "one of the three values" would pass on a span a character short.
    """
    detected = await StubbedModels().detect(build_scan_input(SAMPLE))

    assert read_span_slices(detected) == [EMAIL, PHONE, PHONE, NAME]
    assert [span.personal_data_class for span in detected.spans] == [
        "EMAIL",
        "PHONE",
        "PHONE",
        "NAME",
    ]
    # In the field each one is in, not in the text above: the phone's second span is in the
    # label's argument, where it is the whole string, and the review text is where it is read.
    turn: str = SAMPLE["messages"][0]["content"]
    assert [(tuple(span.path), span.start) for span in detected.spans] == [
        (("messages", 0, "content"), turn.index(EMAIL)),
        (("messages", 0, "content"), find_occurrences(turn, PHONE)[0]),
        (("label", 0, "arguments", "ma_khach"), 0),
        (("messages", 0, "content"), turn.index(NAME)),
    ]


async def test_a_value_said_twice_keeps_one_placeholder() -> None:
    """The phone number is in a turn, inside the email, and in the label.

    Two placeholders over one value is two people as far as anything reading the row can tell,
    which is what co-referent means here.
    """
    detected = await StubbedModels().detect(build_scan_input(SAMPLE))

    assert len(find_occurrences(detected.review_text, PHONE)) == 3
    assert list_placeholders(detected, PHONE) == {"<PHONE_1>"}
    assert (
        len([span for span in detected.spans if span.placeholder == "<PHONE_1>"]) == 2
    )
    assert list_placeholders(detected, EMAIL) == {"<EMAIL_1>"}
    assert list_placeholders(detected, NAME) == {"<NAME_1>"}


async def test_the_digit_run_inside_the_email_earns_no_span() -> None:
    """The containment case as the page draws it, whichever of the two rules drops it.

    The email scan claims the longer value; the phone-shaped digit run inside it is a *different*
    value, so nothing about the values says one sits in the other -- the offsets do, and so does
    the `h` the run butts against.
    """
    detected = await StubbedModels().detect(build_scan_input(SAMPLE))
    turn: str = SAMPLE["messages"][0]["content"]
    inside = find_occurrences(turn, PHONE)[1]
    in_turn = [
        span.start
        for span in detected.spans
        if tuple(span.path) == ("messages", 0, "content")
    ]

    assert turn.index(EMAIL) < inside < turn.index(EMAIL) + len(EMAIL)
    assert inside not in in_turn
    assert find_occurrences(turn, PHONE)[0] in in_turn


async def test_a_span_inside_a_longer_span_is_dropped() -> None:
    """Containment on its own, over a shorter value the word boundary cannot reject.

    `Văn` sits inside `Trần Văn Minh` with a space on each side, so it is a legitimate occurrence
    of its own value and only the offsets say it is inside another span. Both rules drop something
    and neither covers the other: the boundary reads the characters around an occurrence, the
    outermost rule reads the spans around it.
    """
    checker = StubbedModels(scans=(("NAME", lambda text, language: [NAME, "Văn"]),))

    scanned = build_scan_input(
        {
            "id": "nested",
            "messages": [{"role": "user", "content": f"anh {NAME} noi"}],
        }
    )
    detected = await checker.detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert [span.placeholder for span in detected.spans] == ["<NAME_1>"]
    assert redacted.review_text == "user: anh <NAME_1> noi\nlabel: null"
    # And the dropped span is not a value left over: `Văn` went with the name it sat inside, so
    # every detected value resolved and the scan says `redacted` rather than holding the record.
    assert redacted.outcome == "redacted"


async def test_an_occurrence_butting_against_a_word_character_is_not_one() -> None:
    """The offsets are found by searching for a value, and a search knows no word boundary.

    The phone scan asserts one in its own regex, so a 10-digit run inside a 14-digit order number
    is not a phone number it claimed -- and a span there reports a stranger's order as the
    customer's number.

    What the copy does with that order number is *not* fixed by the boundary and is pinned here as
    it behaves: replacement is by value, so the run inside it goes too and the row reads
    `<PHONE_1>9012`. Replacement is by value and § *Out of Scope* calls this cut
    undecided; the boundary keeps the scan from *reporting* the order number, which is the half
    this code owns.
    """
    said = "so 0912345678 va don hang 09123456789012"

    scanned = build_scan_input(
        {"id": "order", "messages": [{"role": "user", "content": said}]}
    )
    detected = await StubbedModels().detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert [(tuple(span.path), span.start, span.end) for span in detected.spans] == [
        (("messages", 0, "content"), said.index(PHONE), said.index(PHONE) + len(PHONE))
    ]
    assert redacted.review_text is not None
    # **And the order number comes through whole.** Replacing by value used to cut it --
    # `<PHONE_1>9012` -- because the phone is a substring of it and nothing said where to stop.
    # Replacing per span cannot: the run earned no span, so nothing points at it.
    assert "09123456789012" in redacted.review_text
    assert "<PHONE_1>9012" not in redacted.review_text
    assert redacted.outcome == "redacted"


async def test_the_longest_value_is_replaced_first() -> None:
    """Replacement by value, and the string this keeps out of the row: `minh<PHONE_1>@vd.vn`.

    Replacement is by value over the whole text, so a shorter value inside a longer one cuts it in
    half unless the longer one goes first.
    """
    scanned = build_scan_input(SAMPLE)
    detected = await StubbedModels().detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert redacted.review_text is not None
    assert "minh<PHONE_1>@vd.vn" not in redacted.review_text
    assert "<EMAIL_1>" in redacted.review_text
    assert redacted.review_text.count("<PHONE_1>") == 2
    for value in (EMAIL, PHONE, NAME):
        assert value not in redacted.review_text


async def test_two_addresses_each_get_their_own_placeholder() -> None:
    """Per-class numbering over the real detector, so `_2` is a rendering something has read."""
    scanned = build_scan_input(
        {
            "id": "two",
            "messages": [
                {"role": "user", "content": "mail anh@vd.vn, cc chi@vd.vn nhe"},
            ],
        }
    )
    detected = await StubbedModels().detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert list_placeholders(detected, "anh@vd.vn", scanned.sample) == {"<EMAIL_1>"}
    assert list_placeholders(detected, "chi@vd.vn", scanned.sample) == {"<EMAIL_2>"}
    assert redacted.review_text == "user: mail <EMAIL_1>, cc <EMAIL_2> nhe\nlabel: null"
    assert redacted.outcome == "redacted"


async def test_a_class_with_two_values_numbers_them_in_first_appearance_order() -> None:
    """The numbering's other half: `N` follows the text, not the order a detector answered in.

    The scan is made to answer out of order on purpose. A detector that returns its matches in
    some other order -- or a fifth one that does -- would otherwise hand a reviewer `<EMAIL_2>`
    for the address the text says first, and nothing would say so.
    """
    # `b` first in the text and `a` first alphabetically, so a sort that is not by appearance
    # cannot land on the same answer by luck.
    first, second = "b@vd.vn", "a@vd.vn"
    checker = StubbedModels(scans=(("EMAIL", lambda text, language: [second, first]),))
    said = f"mail {first} va {second}"
    reading = build_scan_input(
        {"id": "two", "messages": [{"role": "user", "content": said}]}
    )

    detected = await checker.detect(reading)

    assert list_placeholders(detected, first, reading.sample) == {"<EMAIL_1>"}
    assert list_placeholders(detected, second, reading.sample) == {"<EMAIL_2>"}


# -------------------------------------------------- the values a reviewer left, numbered


async def test_the_values_a_reviewer_left_are_numbered_exactly_as_the_scan_numbered_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The point of the whole route: one rule, not a second one for values people add.

    The scan's own claims handed straight back, so what comes out has to be what went in --
    the same spans, the same ids, the same placeholders. A second implementation would agree on
    the easy sample and disagree here, where a value sits inside another one.
    """
    scanned = await StubbedModels().detect(build_scan_input(SAMPLE))

    numbered = number_personal_data_spans(SAMPLE, dict(map(reversed, scanned.claims)))

    assert numbered.review_text == scanned.review_text
    assert numbered.claims == scanned.claims
    assert [span.model_dump(exclude={"reason"}) for span in numbered.spans] == [
        span.model_dump(exclude={"reason"}) for span in scanned.spans
    ]
    assert read_span_slices(numbered) == [EMAIL, PHONE, PHONE, NAME]


def test_a_value_typed_once_is_found_at_every_occurrence_under_one_placeholder() -> (
    None
):
    """Requirement 29: the reviewer types the value, and the service answers the arithmetic.

    The phone number stands three times in this sample -- in a turn, inside the email address and
    in the label's argument. Two of the three are occurrences: the one inside the email has a word
    character against it, which is the rule that keeps `09123456789012` from holding a phone
    number. Nothing was typed but the value itself, and both occurrences carry the one placeholder.
    """
    text = build_review_text(SAMPLE)

    numbered = number_personal_data_spans(SAMPLE, {PHONE: "PHONE"})

    assert len(find_occurrences(text, PHONE)) == 3
    assert read_span_slices(numbered) == [PHONE, PHONE]
    assert list_placeholders(numbered, PHONE) == {"<PHONE_1>"}
    assert [span.id for span in numbered.spans] == [1, 2]


def test_a_value_inside_a_longer_one_is_dropped_with_nothing_on_the_page_asking() -> (
    None
):
    """The containment rule, applied unconditionally -- which is why the `auto` box could go.

    The street inside the address: claimed on its own it earns a span, because it is inside
    nothing. Claimed beside the address it does not. Neither answer is the caller's to choose, so
    there is nothing left for a tick box to turn off.

    **And it is why a caller sends what it kept rather than everything it was told.** A reviewer
    who unticks the address and keeps the street is asking for the street to come out; sending
    both puts the street back inside a longer span nobody is replacing, and it ships in the clear.
    The box the labelling page lost carried that scoping, and this is where it went.
    """
    street = "Lê Lợi"

    alone = number_personal_data_spans(SAMPLE, {street: "NAME"})
    inside_one = number_personal_data_spans(
        SAMPLE, {ADDRESS: "ADDRESS", street: "NAME"}
    )

    assert street in ADDRESS
    assert read_span_slices(alone) == [street]
    assert read_span_slices(inside_one) == [ADDRESS]


def test_saying_a_value_is_a_different_kind_renumbers_it() -> None:
    """`<CLASS_N>` counts per class, so what a value is decides what stands in for it.

    Within a class the number is first appearance in the text, which is why calling the email a
    phone number makes it the *second* one: the turn says the number before it says the address.
    """
    text = build_review_text(SAMPLE)

    both_phones = number_personal_data_spans(SAMPLE, {PHONE: "PHONE", EMAIL: "PHONE"})
    reclassed = number_personal_data_spans(SAMPLE, {PHONE: "PHONE", EMAIL: "EMAIL"})

    assert text.index(PHONE) < text.index(EMAIL)
    assert list_placeholders(both_phones, PHONE) == {"<PHONE_1>"}
    assert list_placeholders(both_phones, EMAIL) == {"<PHONE_2>"}
    assert list_placeholders(reclassed, EMAIL) == {"<EMAIL_1>"}
    assert list_placeholders(reclassed, PHONE) == {"<PHONE_1>"}


def test_a_value_the_text_does_not_hold_is_left_out_rather_than_refused() -> None:
    """A reviewer halfway through typing a value is not an error, and gets no offset either.

    Left out of `claims` as well as of `spans`, because a claim is what the outcome is measured
    against: one nothing could ever replace would hold every record back for good.
    """
    numbered = number_personal_data_spans(
        SAMPLE, {PHONE: "PHONE", "": "EMAIL", "khong-o-trong-van-ban": "NAME"}
    )

    assert [value for _, value in numbered.claims] == [PHONE]
    assert read_span_slices(numbered) == [PHONE, PHONE]


def test_nothing_claimed_is_no_span_and_the_text_still_comes_back() -> None:
    """A reviewer who unticked everything asked for nothing to be replaced, not for an error.

    The text still comes back, because it is the frame of reference every offset indexes and the
    thing on the screen.
    """
    numbered = number_personal_data_spans(SAMPLE, {})

    assert numbered.claims == ()
    assert numbered.spans == ()
    assert numbered.review_text == build_review_text(SAMPLE)


def test_the_classes_offered_are_the_scans_own_in_the_order_that_numbers_them() -> None:
    """What a reviewer picks from. A list written anywhere else is a second declaration of it.

    `SCANS` and not a parameter: a scan is a Python callable, so there is no request that could
    carry one, and a parameter no caller can reach is a seam that only looks like a choice.
    """
    assert list_personal_data_classes() == tuple(name for name, _ in SCANS)
    assert list_personal_data_classes() == PiiRuleDetector(SCANS).classes


# ----------------------------------------------------------------- the copy and the outcome


async def test_the_outcome_is_reported_where_nothing_was_detected() -> None:
    """`reported`: nothing was rewritten, so there is nothing to hold back."""
    scanned = build_scan_input(NOTHING_TO_FIND)
    detected = await StubbedModels().detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert detected.spans == ()
    # Nothing was claimed, so the copy is the record as it arrived -- rendered, not absent.
    assert redacted.review_text == build_review_text(NOTHING_TO_FIND)
    assert redacted.outcome == "reported"


async def test_the_outcome_is_redacted_where_every_detected_value_resolved() -> None:
    """`redacted`: the copy was made and the confirmation confirmed all of it."""
    scanned = build_scan_input(SAMPLE)
    detected = await StubbedModels().detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert redacted.outcome == "redacted"


async def test_a_value_cut_in_half_is_withheld_rather_than_redacted() -> None:
    """`withheld`, in the case containment does not answer: spans that overlap in part.

    Two names sharing a word -- `anh` is a title cue *and* a common given name, so the real
    detector claims `Trần Văn Anh Minh` and `Minh Hoàng Long` off one sentence. Neither contains
    the other, so containment drops neither and both keep a span.

    Replacing works from the highest offset down, so the later span lands and the earlier one is
    left alone rather than spliced over text that has already moved. Which span should win is
    undecided. What is decided is that a copy holding half of a value is not that value redacted,
    and that it may not hold a fragment of both: `Trần Văn Anh ` is still readable, so the claim
    it belongs to never resolves.
    """
    scanned = build_scan_input(
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
    detected = await StubbedModels().detect(scanned)
    redacted = redact_personal_data(detected, scanned.sample)

    assert [span.placeholder for span in detected.spans] == ["<NAME_1>", "<NAME_2>"]
    assert redacted.review_text is not None
    assert "<NAME_2>" in redacted.review_text
    assert "<NAME_1>" not in redacted.review_text
    # Neither placeholder is inside the other, and neither name survives whole. The half that is
    # left is ordinary text, not a spliced placeholder -- which is what a reader has to be able
    # to tell apart from a redaction that worked.
    assert "<NAME_" not in redacted.review_text.replace("<NAME_2>", "")
    assert redacted.outcome == "withheld"


def test_two_spans_a_reviewer_typed_one_placeholder_on_both_are_both_replaced() -> None:
    """One placeholder per value, from the other end: the map is keyed by value, never by placeholder.

    `placeholder` is a column a reviewer edits, so two rows can carry the same one. Keyed by
    placeholder they would be one entry, and the value that lost would stay in a copy that reports
    itself `redacted` -- which is the one thing an outcome may not do.
    """
    said = f"{NAME} và {PHONE}"
    sample = {"messages": [{"role": "user", "content": said}]}
    detected = PersonalDataDetected(
        review_text=said,
        claims=(("NAME", NAME), ("PHONE", PHONE)),
        spans=(
            build_span(sample, ("messages", 0, "content"), NAME, "NAME", "<X_1>", 1),
            build_span(sample, ("messages", 0, "content"), PHONE, "PHONE", "<X_1>", 2),
        ),
    )

    redacted = redact_personal_data(detected, sample)

    assert redacted.review_text == "user: <X_1> và <X_1>\nlabel: null"
    assert redacted.outcome == "redacted"


def test_a_span_with_no_placeholder_replaces_nothing_and_holds_the_record_back() -> (
    None
):
    """A value replaced by the empty string is deleted rather than redacted, and silently.

    So a span carrying no placeholder is skipped on the same terms as one whose offsets read
    nothing, and the claim it named stays unresolved. `withheld`, not a copy that quietly lost a
    stretch of its text and called itself clean.
    """
    said = f"số {PHONE}"
    sample = {"messages": [{"role": "user", "content": said}]}
    detected = PersonalDataDetected(
        review_text=said,
        claims=(("PHONE", PHONE),),
        spans=(build_span(sample, ("messages", 0, "content"), PHONE, "PHONE", "", 1),),
    )

    redacted = redact_personal_data(detected, sample)

    # Nothing was put in its place, so the number is still there to read -- which is the whole
    # difference between a copy held back and one that quietly lost a stretch of its text.
    assert PHONE in redacted.review_text
    assert redacted.outcome == "withheld"


# ----------------------------------------------------------------- the copy over the record


async def test_a_value_confirmed_once_is_replaced_wherever_it_occurs() -> None:
    """Replacement by value over the record, which is the reach the offsets do not have.

    A span indexes `review_text`; `messages` and `label` are other strings, so the rule that
    reaches them is replacement by value -- and the phone number confirmed in the turn is replaced
    in the argument value too. What the reviewer did *not* hand over stays: the address nothing
    claimed is still in the copy, so this replaces confirmed values rather than scrubbing text.
    """
    detected = await StubbedModels().detect(build_scan_input(SAMPLE))

    redacted = redact_personal_data(detected, SAMPLE)

    said = json.dumps(redacted.sample, ensure_ascii=False)
    assert redacted.sample["label"] == [
        {"name": "OpenTicket", "arguments": {"ma_khach": "<PHONE_1>"}}
    ]
    for value in (EMAIL, PHONE, NAME):
        assert value not in said
    # Longest value first, here too: the phone inside the email must not cut it in half.
    assert "minh<PHONE_1>@vd.vn" not in said
    assert ADDRESS in said
    # Nothing structural moved with the values: the catalog holds no personal data, so it comes
    # back as it arrived, keys, nesting and all.
    assert redacted.sample["tools"] == SAMPLE["tools"]
    assert redacted.sample["id"] == SAMPLE["id"]


async def test_no_span_handed_back_leaves_the_record_as_it_arrived() -> None:
    """A reviewer who handed back nothing asked for nothing to be replaced.

    Not a refusal and not an empty record: the same rule with no pair to apply, which is what the
    last rectangle sends before the scan has been run at all.
    """
    detected = await StubbedModels().detect(build_scan_input(SAMPLE))

    redacted = redact_personal_data(detected.model_copy(update={"spans": ()}), SAMPLE)

    assert redacted.sample == dict(SAMPLE)


async def test_a_value_the_reviewer_dropped_stays_in_the_record() -> None:
    """§ *Design*'s first unresolved case, pinned as the behaviour that exists.

    Unticking a span leaves its value in the record, which is then redacted as far as the reviewer
    allowed and no further. Nothing here decides that for them -- what they handed back is what is
    replaced -- and the value they let through is readable in the copy, which is what makes the
    consequence of their tick visible rather than silent.
    """
    detected = await StubbedModels().detect(build_scan_input(SAMPLE))
    kept = tuple(span for span in detected.spans if span.personal_data_class != "PHONE")

    redacted = redact_personal_data(detected.model_copy(update={"spans": kept}), SAMPLE)

    said = json.dumps(redacted.sample, ensure_ascii=False)
    assert PHONE in said
    assert "<EMAIL_1>" in said
    assert "<NAME_1>" in said


def test_a_number_a_boolean_and_a_null_carry_no_value_to_trade_back() -> None:
    """`replace_node` walks a record and rewrites its strings. Everything else is copied.

    The walk is the point: a value sits in an argument three levels down as readily as in a turn,
    and a node nothing can hold a value in is answered as it arrived rather than stringified. It
    is also what the paths are read against -- a span names the string it is in by the same keys
    and indices this walks, so a walk that skipped a list would leave a span pointing at nothing.
    """
    node = {"n": 42, "yes": True, "nothing": None, "said": [PHONE, {"deep": PHONE}]}
    spans = group_spans_by_path(
        (
            build_span(node, ("said", 0), PHONE, "PHONE", "<PHONE_1>", 1),
            build_span(node, ("said", 1, "deep"), PHONE, "PHONE", "<PHONE_1>", 2),
        )
    )

    assert replace_node(node, spans) == {
        "n": 42,
        "yes": True,
        "nothing": None,
        "said": ["<PHONE_1>", {"deep": "<PHONE_1>"}],
    }


# ----------------------------------------------------------------- what may not raise


@pytest.mark.parametrize(
    "declared",
    [None, "", "   ", 0, ["vi"], "Tiếng việt", "fr"],
    ids=["null", "blank", "spaces", "a-list", "spelled-out", "unsupported", "another"],
)
async def test_a_language_the_scans_cannot_read_is_refused(declared: Any) -> None:
    """The language is declared and one of two, and the shape holds it: `vi` or `en`, nothing else.

    Every rule scan and both model steps take that one value, and `agent_toolkit` keys its `vi`
    and `en` tables by it -- a third value reaches the library as a dictionary lookup and raises a
    `KeyError` from inside it, which is nobody's answer. `Tiếng việt` is in the list because that
    is what a reader would write for Vietnamese, and it is exactly the value the library cannot
    take. `null` too: a caller declaring nothing takes the default the shape states, and is not
    one declaring a language of nothing.

    Refused twice over, because a shape's `ValidationError` is a 500 wherever nobody turns it into
    this codebase's one exception: `detect_personal_data` is that boundary, so the endpoint
    answers 422 and names the record it could not read.
    """
    with pytest.raises(ValidationError):
        PersonalDataCheckingInput(sample=SAMPLE, language=declared)

    with pytest.raises(ConfigError, match="language"):
        await detect_personal_data(build_checking_config(), SAMPLE, declared)


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
    install_model_answers(monkeypatch, prompts=prompts)
    quiet = {key: value for key, value in NOTHING_TO_FIND.items() if key != "language"}
    checking_input = PersonalDataCheckingInput(sample=quiet)

    assert checking_input.language == "vi"

    detected = await ToolDecisionPersonalChecking(build_checking_config()).detect(
        checking_input
    )

    assert redact_personal_data(detected, quiet).outcome == "reported"
    assert read_section(prompts[0], "## Conversation Language") == ["vi"]


async def test_a_failed_call_answers_nothing_and_says_so_on_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """§ *Error Behavior*: Neither step may raise, and a failure is an event.

    Both steps fail here. The model detector answers nothing, which leaves the rule scans' values
    detected; the confirmation then confirms none of them, so nothing is replaced and the decision
    is `withheld` rather than `reported` -- a rewrite was asked for and did not happen. One JSON
    object per failure on stdout, each naming the step, and never a log file (`H-6`).
    """

    async def refused(prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("the endpoint hung up")

    for module in (personal_data_checking, data_quality):
        monkeypatch.setattr(module, "complete", refused)

    scanned = build_scan_input(SAMPLE)
    detected = await ToolDecisionPersonalChecking(build_checking_config()).detect(
        scanned
    )
    redacted = redact_personal_data(detected, scanned.sample)

    assert detected.spans == ()
    # Nothing confirmed is nothing replaced, so the copy still holds every value the rules found.
    assert PHONE in redacted.review_text
    assert redacted.outcome == "withheld"
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

    scanned = build_scan_input(SAMPLE)
    detected = await ToolDecisionPersonalChecking(build_checking_config()).detect(
        scanned
    )
    redacted = redact_personal_data(detected, scanned.sample)

    assert detected.spans == ()
    assert redacted.outcome == "withheld"
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
    install_model_answers(monkeypatch)
    holder = (
        data_quality if missing == "PII_LLM_DETECT_PROMPT" else personal_data_checking
    )
    monkeypatch.setattr(holder, missing, Path("nowhere.txt"))

    with pytest.raises(ConfigError, match="nowhere.txt"):
        await ToolDecisionPersonalChecking(build_checking_config()).detect(
            build_scan_input(SAMPLE)
        )


# ----------------------------------------------------------------- the two prompts


async def test_the_detect_prompt_carries_the_language_and_the_text() -> None:
    """`pii_llm_detect.txt`, filled: `{{language}}` and `{{review_text}}`, and no slot left.

    The detected values are not among them -- this is the prompt that finds them -- and each value
    is under its own heading, because two slots filled with each other's value is a prompt that
    reads as nonsense and passes a containment check.
    """
    checker = StubbedModels()
    text = build_review_text(SAMPLE)

    prompt = checker.build_pii_llm_detect_prompt(text, "vi")

    assert "{{" not in prompt
    assert read_section(prompt, "## Conversation Language") == ["vi"]
    assert read_section(prompt, "## Text Under Review") == text.splitlines()
    for field in (*PiiLlmDetected.model_fields, *PiiLlmFinding.model_fields):
        assert f'"{field}"' in prompt, field


async def test_the_confirm_prompt_carries_the_language_the_text_and_the_spans() -> None:
    """`pii_llm_confirm.txt`, filled: the three slots, one `id | CLASS | value` per span.

    The modality's file, because the question is about personal data and not about the kind of
    sample it was found in -- the same reason `confirm_pii_by_llm` has a body there. The id is in the
    line because it is what the answer names.
    """
    checker = StubbedModels()
    text = build_review_text(SAMPLE)
    spans = find_and_number_spans(text, (("EMAIL", EMAIL), ("NAME", NAME)))

    prompt = checker.build_pii_llm_confirm_prompt(build_scan_input(SAMPLE), text, spans)

    assert "{{" not in prompt
    assert read_section(prompt, "## Conversation Language") == ["vi"]
    assert read_section(prompt, "## Text Under Review") == text.splitlines()
    assert read_section(prompt, "## Spans") == [
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
    library's own fill rather than one written here.

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
    text = build_review_text(quoted)

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
    """Both config sources, and one resolution per step rather than one per record.

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
        build_checking_config(
            base_url="http://asked-for.invalid/v1",
            api_key="the-key",
            settings={"temperature": 0.0},
        )
    )
    await checker.detect(build_scan_input(SAMPLE))

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
    checker = ToolDecisionPersonalChecking(build_checking_config())

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
