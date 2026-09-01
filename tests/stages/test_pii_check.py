"""T16 · pii_check: what the two layers find, what gets replaced, and what is held back.

The adversarial fixtures § *Testing Strategy* item 6 asks for, and the three decisions T16 made.
Every fixture is invented; the Vietnamese is the corpus's language and the spoken
forms are the ones an off-the-shelf scrubber does not detect.

**Layer two is a stand-in in every test here, and that is the boundary rather than a shortcut.**
`make check` runs no network (§ *Testing Strategy* item 8), and what this stage owns is the window it
slices, what it does with a subset that came back, and what it does when nothing did. A stub that
answers from a fixed list makes all three assertable; the live model is `edge/bootstrap.py`'s and the
Smoke rung's.

**The hardest case used to be the mixed spelling**, `bon tám khong hai mot nam`, and since T54 it is
not one: the library's own patterns list the toned and the tone-stripped word side by side, so one
pass over the raw text finds all four spellings and the tone-stripped view this stage used to build
word by word is gone. What is left for the stage is the other half of the same problem — a scan
reports a *value* and a span needs offsets, so every reported value is located in the raw text across
any run of whitespace. That is what redacts a name the transcript wrapped over a line, and a hit
nobody can locate is a hit nobody can redact.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

import pytest

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.data_quality.label_check import label_check
from dataforce.pipeline.data_quality.pii_check import pii_check, spans_of
from dataforce.record import Part, Record

from .test_label_check import written_paths
from .test_load_data import an_engine
from .test_tool_decision import SENT, a_record, a_turn_that_calls

# One one-time code, written the four ways a call-centre transcript writes it. A code and not a bare
# customer id since T54: an identifier with no cue word in front of it is not a class layer one has,
# which is § *PII, in two layers*' stated cost and `test_text2text.py` asserts directly.
TYPED = "480215"
SPOKEN = "bốn tám không hai một năm"
SPOKEN_BARE = "bon tam khong hai mot nam"
SPOKEN_MIXED = "bon tám khong hai mot nam"


class ALayerTwo:
    """The verifier port, as a stand-in: it answers from a rule instead of from a model."""

    def __init__(
        self, decide: Callable[[str, Mapping[str, str]], Mapping[str, str]]
    ) -> None:
        self._decide = decide
        self.windows: list[str] = []

    def confirmed_personal_data(
        self, window: str, found: Mapping[str, str]
    ) -> Mapping[str, str]:
        """Every call it was asked to make, so a test can assert what the window was."""
        self.windows.append(window)
        return self._decide(window, found)


def confirming_everything() -> ALayerTwo:
    """The layer two that agrees with layer one, which is the case redaction needs."""
    return ALayerTwo(lambda window, found: found)


def clearing(*values: str) -> ALayerTwo:
    """The layer two that sets precision: these values are not personal data after all."""
    return ALayerTwo(
        lambda window, found: {
            value: named for value, named in found.items() if value not in values
        }
    )


def reclassifying(value: str, named: str) -> ALayerTwo:
    """The layer two that reads the sentence and disagrees about *which* class a hit is."""
    return ALayerTwo(lambda window, found: {**found, value: named})


def failing() -> ALayerTwo:
    """A model call that did not come back. `agent-toolkit` owns the retries; this is after them."""

    def refuse(window: str, found: Mapping[str, str]) -> Mapping[str, str]:
        raise RuntimeError("the endpoint is not answering")

    return ALayerTwo(refuse)


def misconfigured() -> ALayerTwo:
    """An adapter reporting a fault a human has to fix, which is what `ConfigError` means."""

    def refuse(window: str, found: Mapping[str, str]) -> Mapping[str, str]:
        raise ConfigError("config/model/gemma-4-31B-it.json names no endpoint")

    return ALayerTwo(refuse)


def a_turn(text: str, role: str = "user") -> Part:
    """One turn of invented conversation."""
    return Part(type="text", role=role, text=text)


def an_engine_that(
    layer_two: ALayerTwo | None = None, redact: bool = True, **params: Any
) -> Engine:
    """The engine a stage is handed: both axes, `params.yaml`, and layer two's port."""
    return replace(
        an_engine({"enable_redact": redact, **params}),
        personal_data_verifier=layer_two,
    )


def checked(
    *content: Part,
    engine: Engine | None = None,
    label: Any = (SENT,),
) -> tuple[Record, Mapping[str, Any]]:
    """One record through `label_check` and then `pii_check`, and the side output with it."""
    running = engine or an_engine_that(confirming_everything())
    loaded = label_check(running, [a_record(content=content, label=label)]).records
    scanned = pii_check(running, loaded)
    return scanned.records[0], scanned.side_output


def scan_of(record: Record) -> Any:
    """What this stage wrote on the record."""
    written = record.data_quality.pii_check
    assert written is not None
    return written


def found_values(record: Record, scanned: Record) -> set[str]:
    """Every hit, read back out of the text the spans were recorded against (Requirement 19)."""
    return {
        (record.content[span.part].text or "")[span.start : span.end]
        for span in scan_of(scanned).spans
    }


# --- layer one: the spoken forms a scrubber misses ---


@pytest.mark.parametrize(
    "written",
    [TYPED, SPOKEN, SPOKEN_BARE, SPOKEN_MIXED],
    ids=["typed", "spoken", "tone-free", "mixed"],
)
def test_a_code_is_found_however_it_is_spelled(written: str) -> None:
    """Requirement 18, and in one pass: the library's pattern lists both spellings of every word."""
    said = a_turn(f"Mã xác nhận của mình là {written}.")

    scanned, _ = checked(said)

    assert found_values(a_record(content=(said,)), scanned) == {written}


def test_a_span_points_into_the_text_it_was_found_in() -> None:
    """The offsets are `content`'s, not a normalisation's, which is what makes a hit replaceable."""
    said = a_turn(f"Mã xác nhận của mình là {SPOKEN_MIXED} nhé.")

    scanned, _ = checked(said)

    span = scan_of(scanned).spans[0]
    assert (said.text or "")[span.start : span.end] == SPOKEN_MIXED
    assert scan_of(scanned).content_version_scanned == 1


def test_a_reported_value_is_located_across_any_run_of_whitespace() -> None:
    """What replaced the tone-stripped view: a scan reports a value, and this finds where it is.

    A scan normalises the whitespace inside a name it reports, so the value it hands back may not
    occur verbatim in the text it came out of. Matching its words in order with `\\s+` between them
    is what keeps the span a true offset into `content` -- and the matched slice, not the reported
    value, is what gets replaced.
    """
    wrapped = "Chào anh Nguyễn\nVăn Dũng nhé."

    assert list(spans_of("Nguyễn Văn Dũng", wrapped)) == [(9, 24)]
    assert wrapped[9:24] == "Nguyễn\nVăn Dũng"


def test_every_occurrence_of_a_value_is_a_span() -> None:
    """Requirement 17 replaces a value everywhere, so the evidence has to name every place."""
    twice = f"Mã xác nhận {TYPED}. Vâng, {TYPED} nhé?"

    assert len(list(spans_of(TYPED, twice))) == 2


def test_a_value_reported_twice_is_not_two_spans_per_occurrence() -> None:
    """The cross-product `spans_of` introduces, and what `outermost` is doing about it.

    A scan reports what it matched, so a number said twice comes back twice -- and this stage then
    locates *every* occurrence of *each* reported value, which is four hits over two real spans.
    Keeping all four would put a record's phone number in the evidence twice and number the
    placeholders off it, so the containment pass collapses the identical ones. This is the case that
    says the pass is load-bearing rather than a leftover from the overlapping-patterns design.
    """
    number = "0900123456"
    said = a_turn(f"Số của mình là {number}, gọi lại {number} nhé.")

    scanned, _ = checked(said)

    spans = scan_of(scanned).spans
    assert [(span.start, span.end) for span in spans] == [(15, 25), (35, 45)]
    assert {span.placeholder for span in spans} == {"<PHONE_1>"}


def test_a_value_that_is_all_whitespace_matches_nothing() -> None:
    """The one shape a split-and-escape would turn into a pattern that matches the empty string."""
    assert list(spans_of("   ", "Mã xác nhận 480215.")) == []
    assert list(spans_of("", "Mã xác nhận 480215.")) == []


def test_a_name_behind_its_title_is_found_and_redacted() -> None:
    """§ *Testing Strategy* item 6: the one name rule that needs no list of names.

    A title or an introduction, then the capitalised words after it -- so `anh Nguyễn Văn Dũng` is a
    hit and a name nobody announced is not. That second half is the class's stated reach and not a
    gap this repository closes: a rule's reach is `agent-toolkit`'s, in a diff there.
    """
    said = a_turn("Chào anh Nguyễn Văn Dũng nhé.")

    scanned, written = checked(said)

    assert scan_of(scanned).classes == ("NAME",)
    assert "Nguyễn Văn Dũng" not in (scanned.content[0].text or "")
    assert "<NAME_1>" in (scanned.content[0].text or "")


def test_a_name_the_transcript_wrapped_over_a_line_is_still_redacted() -> None:
    """§ *Testing Strategy* item 6, and the reason `spans_of` matches across whitespace.

    The scan reports `Nguyễn Văn Dũng` with single spaces because that is how it normalises what it
    matched; the text holds a newline in the middle of it. Searching for the reported value verbatim
    would find nothing, mint a placeholder for a value no span points at, and leave the name in the
    corpus -- so what is replaced is the *matched slice of the raw text*, which is the property that
    makes a hit replaceable at all.
    """
    wrapped = a_turn("Chào anh Nguyễn\nVăn Dũng nhé.")

    scanned, written = checked(wrapped)

    span = scan_of(scanned).spans[0]
    assert (wrapped.text or "")[span.start : span.end] == "Nguyễn\nVăn Dũng"
    assert scanned.content[0].text == "Chào anh <NAME_1> nhé."
    assert written == {
        "pii_check": {
            "placeholders": {scanned.record_id: {"<NAME_1>": "Nguyễn\nVăn Dũng"}}
        }
    }


def test_a_spoken_email_is_found_through_a_cong_and_cham() -> None:
    """`@` and `.` as they are said out loud, which is what layer one is for."""
    said = a_turn("Mail của mình là an.nguyen a còng vidu chấm com nha.")

    scanned, _ = checked(said)

    assert scan_of(scanned).classes == ("EMAIL",)


def test_one_value_used_twice_keeps_one_placeholder() -> None:
    """Requirement 17. Two spans, one placeholder, because the map is keyed by value."""
    scanned, _ = checked(
        a_turn(f"Mã xác nhận của mình là {TYPED}."),
        a_turn(f"Vâng, mã xác nhận {TYPED} phải không ạ?"),
    )

    spans = scan_of(scanned).spans
    assert len(spans) == 2
    assert {span.placeholder for span in spans} == {"<OTP_1>"}


def test_a_value_is_replaced_in_a_part_the_scan_flagged_nothing_in() -> None:
    """One placeholder per value is true across parts, and the scan is per part.

    Newly worth asserting since T54: the classes carry cue words now, so the second mention of a
    code often is not flagged where it is repeated -- and Requirement 17 replaces a value
    *everywhere* it appears, through one pass keyed by value. So the rewrite reaches a part with no
    span in it, and the span list stays what Requirement 19 says it is: where a hit was found.
    """
    scanned, _ = checked(
        a_turn(f"Mã xác nhận của mình là {TYPED}."),
        a_turn(f"Vâng, {TYPED} phải không ạ?"),
    )

    assert [span.part for span in scan_of(scanned).spans] == [0]
    assert TYPED not in (scanned.content[1].text or "")
    assert "<OTP_1>" in (scanned.content[1].text or "")


def test_a_hit_inside_a_longer_hit_is_not_a_second_hit() -> None:
    """Layer one's four scans overlap on purpose, and the outer hit is the one that survives.

    A cue word in front of a ten-digit run puts it in reach of both classes: `PHONE` reports all ten
    and `OTP` reports the first eight of them. Keeping both would mint a placeholder for a value that
    is already gone by the time its turn comes, so the containing hit wins and layer two is what may
    still call it something else.
    """
    scanned, _ = checked(a_turn("Mã xác nhận và số là 0900123456."))

    assert scan_of(scanned).classes == ("PHONE",)
    assert len(scan_of(scanned).spans) == 1
    assert scan_of(scanned).spans[0].placeholder == "<PHONE_1>"


# --- layer two: what sets the precision ---


def test_a_long_digit_run_that_is_an_order_reference_is_flagged_and_then_cleared() -> (
    None
):
    """§ *Testing Strategy* item 6, exactly: layer one flags it, layer two clears it.

    An *order reference* and no longer a price, because the two moved apart when layer one became the
    library's: a seven-digit price reaches no class now, and a ten-digit reference is exactly as long
    as a mobile number. That is the noise layer one is allowed to make and layer two exists to price.
    """
    reference = "1250000789"
    engine = an_engine_that(clearing(reference))

    scanned, written = checked(a_turn(f"Đơn hàng {reference} nhé."), engine=engine)

    assert scan_of(scanned).unverified == 1
    assert not scan_of(scanned).spans[0].verified
    assert scan_of(scanned).decision == "withheld"
    assert reference in (scanned.content[0].text or "")
    assert written == {}


def test_the_window_layer_two_reads_is_one_part_that_had_a_candidate() -> None:
    """A bounded window, and only where there is something to ask about.

    Two properties in one assertion. The window is the turn a hit is in, so setting the precision of
    one hit never sends a whole conversation anywhere -- and a part layer one flagged nothing in is
    not sent at all, which at twenty thousand records times five turns is most of the calls that
    would otherwise be made to be told nothing.
    """
    engine = an_engine_that(confirming_everything())

    checked(
        a_turn("Xin chào."), a_turn(f"Mã xác nhận của mình là {TYPED}."), engine=engine
    )

    verifier = engine.personal_data_verifier
    assert isinstance(verifier, ALayerTwo)
    assert verifier.windows == [f"Mã xác nhận của mình là {TYPED}."]


def test_layer_two_decides_which_class_a_hit_was() -> None:
    """A digit run behind a cue word is an `OTP` *and* a `PHONE` until something reads the sentence.

    § *PII, in two layers*: layer two returns each value under the class it confirms it as, which is
    a subset of the values and never of the classes -- so the class on the span is the one the layer
    that can
    read the sentence chose, not the first scan that reached it.
    """
    number = "0900123456"
    engine = an_engine_that(reclassifying(number, "OTP"))

    scanned, _ = checked(a_turn(f"Số của mình là {number}."), engine=engine)

    assert scan_of(scanned).spans[0].placeholder == "<OTP_1>"


@pytest.mark.parametrize(
    "engine",
    [
        pytest.param(an_engine_that(None), id="no-layer-two"),
        pytest.param(an_engine_that(failing()), id="layer-two-that-failed"),
    ],
)
def test_no_second_layer_is_no_confirmation_and_not_confirmation_by_default(
    engine: Engine,
) -> None:
    """Requirement 43: the call that failed is one missing answer, and the record says so."""
    scanned, written = checked(
        a_turn(f"Mã xác nhận của mình là {TYPED}."), engine=engine
    )

    assert scan_of(scanned).unverified == 1
    assert scan_of(scanned).decision == "withheld"
    assert scanned.content_version == 1
    assert written == {}


# --- what gets rewritten, and what the decision says ---


def test_content_and_label_are_rewritten_together_under_one_placeholder() -> None:
    """Requirement 17, and the defect it exists to prevent, in one assertion each."""
    restating = a_turn_that_calls(
        "SendStatement", {"ma_khach": TYPED, "ky": "thang_nay"}
    )

    scanned, written = checked(a_turn(f"Mã xác nhận của mình là {TYPED}."), restating)

    assert TYPED not in (scanned.content[0].text or "")
    assert scanned.label == (
        {
            "name": "SendStatement",
            "arguments": {"ma_khach": "<OTP_1>", "ky": "thang_nay"},
        },
    )
    assert written == {
        "pii_check": {"placeholders": {scanned.record_id: {"<OTP_1>": TYPED}}}
    }


def test_the_restated_answer_still_matches_the_label_after_redaction() -> None:
    """The downstream half of Requirement 17: redacting one side manufactures a mismatch.

    `label_assistant_mismatch` compares the label against the turn that restates it. Both were
    rewritten here, so it still reads 0 -- and the assertion is run through `label_check` a second
    time, which is the only way to see the defect a one-sided redaction would have caused.
    """
    engine = an_engine_that(confirming_everything())
    restating = a_turn_that_calls(
        "SendStatement", {"ma_khach": TYPED, "ky": "thang_nay"}
    )

    scanned, _ = checked(
        a_turn(f"Mã xác nhận của mình là {TYPED}."), restating, engine=engine
    )
    again = label_check(engine, [scanned]).records[0].data_quality.label_check

    assert again is not None
    assert "label_assistant_mismatch" not in again.failed_checks


def test_redaction_off_reports_and_leaves_the_content_alone() -> None:
    """Requirement 21, and the default: the run completes and `export`'s precondition then fails."""
    engine = an_engine_that(confirming_everything(), redact=False)

    scanned, written = checked(
        a_turn(f"Mã xác nhận của mình là {TYPED}."), engine=engine
    )

    assert scan_of(scanned).decision == "reported"
    assert scan_of(scanned).spans[0].verified
    assert TYPED in (scanned.content[0].text or "")
    assert scanned.content_version == 1
    assert written == {}


def test_a_record_with_nothing_to_redact_is_redacted() -> None:
    """`export`'s precondition is `decision == "redacted"`, so a clean record has to reach it."""
    scanned, _ = checked(a_turn("Cho mình xem sao kê tháng này."), label=())

    assert scan_of(scanned).decision == "redacted"
    assert scan_of(scanned).spans == ()
    assert scanned.content_version == 1


def test_content_version_is_bumped_only_where_the_text_changed() -> None:
    """The version says which text a span offset points into, so a bump with no rewrite is a lie."""
    scanned, _ = checked(a_turn(f"Mã xác nhận của mình là {TYPED}."))

    assert scanned.content_version == 2
    assert scan_of(scanned).content_version_scanned == 1
    assert scan_of(scanned).decision == "redacted"


def test_two_runs_over_one_record_mint_the_same_placeholders() -> None:
    """Numbered per class in first-hit order, so a re-run is comparable to the run before it."""
    once, _ = checked(a_turn(f"Mã xác nhận {TYPED} và số 0900123456."))
    twice, _ = checked(a_turn(f"Mã xác nhận {TYPED} và số 0900123456."))

    assert [span.placeholder for span in scan_of(once).spans] == [
        span.placeholder for span in scan_of(twice).spans
    ]


# --- the stage's own promises ---


def test_a_record_that_is_only_reported_gains_exactly_one_key() -> None:
    """I8, in the case Requirement 5 has no exception for."""
    engine = an_engine_that(confirming_everything(), redact=False)
    record = a_record(content=(a_turn(f"Mã xác nhận của mình là {TYPED}."),))
    loaded = label_check(engine, [record]).records[0]

    scanned = pii_check(engine, [loaded]).records[0]

    assert written_paths(loaded.model_dump(), scanned.model_dump()) == {
        "data_quality.pii_check"
    }


def test_a_redacted_record_touches_the_three_paths_requirement_5_names_and_no_others() -> (
    None
):
    """Its own key, `content`, the `label` and `content_version` -- and nothing else moves."""
    engine = an_engine_that(confirming_everything())
    record = a_record(content=(a_turn(f"Mã xác nhận của mình là {TYPED}."),))
    loaded = label_check(engine, [record]).records[0]

    scanned = pii_check(engine, [loaded]).records[0]

    assert written_paths(loaded.model_dump(), scanned.model_dump()) == {
        "data_quality.pii_check",
        "content",
        "content_version",
        "label",
    }


def test_a_record_that_never_went_through_label_check_is_skipped_untouched() -> None:
    """Requirement 42's precondition: skipped, marked by the absence, never dropped."""
    record = a_record(content=(a_turn(f"Mã xác nhận của mình là {TYPED}."),))

    scanned = pii_check(an_engine_that(confirming_everything()), [record]).records

    assert scanned == (record,)
    assert scanned[0].data_quality.pii_check is None


def test_a_quarantined_record_is_still_scanned() -> None:
    """The other half of that resolution: no *verdict* is a reason to skip.

    Personal data in a record that failed a label check is still personal data, and a corpus where
    the broken records are the unscrubbed ones is the worst possible arrangement.
    """
    scanned, _ = checked(
        a_turn(f"Mã xác nhận của mình là {TYPED}."), label=("KhongCoTool",)
    )

    assert scanned.data_quality.label_check is not None
    assert scanned.data_quality.label_check.quarantined
    assert scan_of(scanned).decision == "redacted"


def test_every_record_comes_back() -> None:
    """I11, over a batch where one is skipped, one is redacted and one has nothing to find."""
    engine = an_engine_that(confirming_everything())
    records = [
        a_record(content=(a_turn(f"Mã xác nhận của mình là {TYPED}."),)),
        a_record(content=(a_turn("Xin chào."),)),
    ]
    loaded = [*label_check(engine, records).records, records[0]]

    assert len(pii_check(engine, loaded).records) == len(loaded)


def test_a_mistyped_switch_is_refused_before_any_record_is_read() -> None:
    """`bool("no")` is `True`, so a coerced switch turns redaction on for a value meaning off."""
    with pytest.raises(ConfigError, match="enable_redact"):
        checked(a_turn("Xin chào."), engine=an_engine_that(redact="no"))


def test_a_config_error_from_layer_two_stops_the_run() -> None:
    """`ConfigError` means a human must change configuration, not *this hit is unconfirmed*.

    Swallowed, an adapter that cannot reach its endpoint leaves every hit `unverified` and every
    record `withheld` -- which fails safe, and is the expensive kind of quiet: nothing ships and no
    line says why. `jury` has the same one-line fix for the opposite reason, where it fails silent.
    """
    with pytest.raises(ConfigError, match="endpoint"):
        checked(
            a_turn(f"Mã xác nhận của mình là {TYPED}."),
            engine=an_engine_that(misconfigured()),
        )
