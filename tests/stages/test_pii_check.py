"""T16 · pii_check: what the two layers find, what gets replaced, and what is held back.

The adversarial fixtures § *Testing Strategy* item 6 asks for, and the three decisions T16 made.
Every fixture is invented (AGENTS.md §9); the Vietnamese is the corpus's language and the spoken
forms are the ones an off-the-shelf scrubber does not detect.

**Layer two is a stand-in in every test here, and that is the boundary rather than a shortcut.**
`make check` runs no network (§ *Testing Strategy* item 8), and what this stage owns is the window it
slices, what it does with a subset that came back, and what it does when nothing did. A stub that
answers from a fixed list makes all three assertable; the live model is `edge/bootstrap.py`'s and the
Smoke rung's.

**The hardest case is the mixed spelling**, `bon tám khong hai mot nam`: the raw text does not match a
pattern written in correct Vietnamese and the tone-stripped pattern does not match the raw text
either, so only the per-word view finds it — and the span it produces has to point into the raw text,
because a hit nobody can locate is a hit nobody can redact.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

import pytest

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.data_quality.label_check import label_check
from dataforce.pipeline.data_quality.pii_check import pii_check, tone_stripped_view
from dataforce.record import Part, Record

from .test_label_check import written_paths
from .test_load_data import an_engine
from .test_tool_decision import SENT, a_record, a_turn_that_calls

# One customer id, written the four ways a call-centre transcript writes it.
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
def test_a_customer_id_is_found_however_it_is_spelled(written: str) -> None:
    """Requirement 18: the pattern is written once in correct Vietnamese and matches all four."""
    said = a_turn(f"Mã của mình là {written}.")

    scanned, _ = checked(said)

    assert found_values(a_record(content=(said,)), scanned) == {written}


def test_a_span_points_into_the_text_it_was_found_in() -> None:
    """The offsets are `content`'s, not a normalisation's, which is what makes a hit replaceable."""
    said = a_turn(f"Mã của mình là {SPOKEN_MIXED} nhé.")

    scanned, _ = checked(said)

    span = scan_of(scanned).spans[0]
    assert (said.text or "")[span.start : span.end] == SPOKEN_MIXED
    assert scan_of(scanned).content_version_scanned == 1


def test_the_tone_stripped_view_keeps_every_character_at_its_own_index() -> None:
    """The rule the view exists for: same length, so an offset in it is an offset in the text."""
    said = "Mã của mình là bốn tám không hai một năm."

    view = tone_stripped_view(said)

    assert len(view) == len(said)
    assert view == "Ma cua minh la bon tam khong hai mot nam."


def test_a_spoken_email_is_found_through_a_cong_and_cham() -> None:
    """`@` and `.` as they are said out loud, which is what layer one is for."""
    said = a_turn("Mail của mình là an.nguyen a còng vidu chấm com nha.")

    scanned, _ = checked(said)

    assert scan_of(scanned).classes == ("EMAIL",)


def test_one_value_used_twice_keeps_one_placeholder() -> None:
    """Requirement 17. Two spans, one placeholder, because the map is keyed by value."""
    scanned, _ = checked(
        a_turn(f"Mã của mình là {TYPED}."), a_turn(f"Vâng, {TYPED} phải không ạ?")
    )

    spans = scan_of(scanned).spans
    assert len(spans) == 2
    assert {span.placeholder for span in spans} == {"<CUSTOMER_ID_1>"}


def test_a_hit_inside_a_longer_hit_is_not_a_second_hit() -> None:
    """A digit run inside an email address: layer one's patterns overlap on purpose."""
    scanned, _ = checked(a_turn("Gửi vào mail 4802156@vidu.com giúp mình."))

    assert scan_of(scanned).classes == ("EMAIL",)


# --- layer two: what sets the precision ---


def test_a_digit_run_that_is_a_price_is_flagged_and_then_cleared() -> None:
    """§ *Testing Strategy* item 6, exactly: layer one flags it, layer two clears it."""
    price = "1250000"
    engine = an_engine_that(clearing(price))

    scanned, written = checked(a_turn(f"Tổng cộng {price} đồng nhé."), engine=engine)

    assert scan_of(scanned).unverified == 1
    assert not scan_of(scanned).spans[0].verified
    assert scan_of(scanned).decision == "withheld"
    assert price in (scanned.content[0].text or "")
    assert written == {}


def test_the_window_layer_two_reads_is_one_part_that_had_a_candidate() -> None:
    """A bounded window, and only where there is something to ask about.

    Two properties in one assertion. The window is the turn a hit is in, so setting the precision of
    one hit never sends a whole conversation anywhere -- and a part layer one flagged nothing in is
    not sent at all, which at twenty thousand records times five turns is most of the calls that
    would otherwise be made to be told nothing.
    """
    engine = an_engine_that(confirming_everything())

    checked(a_turn("Xin chào."), a_turn(f"Mã của mình là {TYPED}."), engine=engine)

    verifier = engine.personal_data_verifier
    assert isinstance(verifier, ALayerTwo)
    assert verifier.windows == [f"Mã của mình là {TYPED}."]


def test_layer_two_decides_which_class_a_hit_was() -> None:
    """A ten-digit run is a phone number *and* a customer id until something reads the sentence."""
    number = "0900123456"
    engine = an_engine_that(reclassifying(number, "CUSTOMER_ID"))

    scanned, _ = checked(a_turn(f"Số của mình là {number}."), engine=engine)

    assert scan_of(scanned).spans[0].placeholder == "<CUSTOMER_ID_1>"


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
    scanned, written = checked(a_turn(f"Mã của mình là {TYPED}."), engine=engine)

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

    scanned, written = checked(a_turn(f"Mã của mình là {TYPED}."), restating)

    assert TYPED not in (scanned.content[0].text or "")
    assert scanned.label == (
        {
            "name": "SendStatement",
            "arguments": {"ma_khach": "<CUSTOMER_ID_1>", "ky": "thang_nay"},
        },
    )
    assert written == {
        "pii_check": {"placeholders": {scanned.record_id: {"<CUSTOMER_ID_1>": TYPED}}}
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

    scanned, _ = checked(a_turn(f"Mã của mình là {TYPED}."), restating, engine=engine)
    again = label_check(engine, [scanned]).records[0].data_quality.label_check

    assert again is not None
    assert "label_assistant_mismatch" not in again.failed_checks


def test_redaction_off_reports_and_leaves_the_content_alone() -> None:
    """Requirement 21, and the default: the run completes and `export`'s precondition then fails."""
    engine = an_engine_that(confirming_everything(), redact=False)

    scanned, written = checked(a_turn(f"Mã của mình là {TYPED}."), engine=engine)

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
    scanned, _ = checked(a_turn(f"Mã của mình là {TYPED}."))

    assert scanned.content_version == 2
    assert scan_of(scanned).content_version_scanned == 1
    assert scan_of(scanned).decision == "redacted"


def test_two_runs_over_one_record_mint_the_same_placeholders() -> None:
    """Numbered per class in first-hit order, so a re-run is comparable to the run before it."""
    once, _ = checked(a_turn(f"Mã {TYPED} và số 0900123456."))
    twice, _ = checked(a_turn(f"Mã {TYPED} và số 0900123456."))

    assert [span.placeholder for span in scan_of(once).spans] == [
        span.placeholder for span in scan_of(twice).spans
    ]


# --- the stage's own promises ---


def test_a_record_that_is_only_reported_gains_exactly_one_key() -> None:
    """I8, in the case Requirement 5 has no exception for."""
    engine = an_engine_that(confirming_everything(), redact=False)
    record = a_record(content=(a_turn(f"Mã của mình là {TYPED}."),))
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
    record = a_record(content=(a_turn(f"Mã của mình là {TYPED}."),))
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
    record = a_record(content=(a_turn(f"Mã của mình là {TYPED}."),))

    scanned = pii_check(an_engine_that(confirming_everything()), [record]).records

    assert scanned == (record,)
    assert scanned[0].data_quality.pii_check is None


def test_a_quarantined_record_is_still_scanned() -> None:
    """The other half of that resolution: no *verdict* is a reason to skip.

    Personal data in a record that failed a label check is still personal data, and a corpus where
    the broken records are the unscrubbed ones is the worst possible arrangement.
    """
    scanned, _ = checked(a_turn(f"Mã của mình là {TYPED}."), label=("KhongCoTool",))

    assert scanned.data_quality.label_check is not None
    assert scanned.data_quality.label_check.quarantined
    assert scan_of(scanned).decision == "redacted"


def test_every_record_comes_back() -> None:
    """I11, over a batch where one is skipped, one is redacted and one has nothing to find."""
    engine = an_engine_that(confirming_everything())
    records = [
        a_record(content=(a_turn(f"Mã của mình là {TYPED}."),)),
        a_record(content=(a_turn("Xin chào."),)),
    ]
    loaded = [*label_check(engine, records).records, records[0]]

    assert len(pii_check(engine, loaded).records) == len(loaded)


def test_a_mistyped_switch_is_refused_before_any_record_is_read() -> None:
    """`bool("no")` is `True`, so a coerced switch turns redaction on for a value meaning off."""
    with pytest.raises(ConfigError, match="enable_redact"):
        checked(a_turn("Xin chào."), engine=an_engine_that(redact="no"))
