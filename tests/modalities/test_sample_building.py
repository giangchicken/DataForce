"""The precondition every text2text task inherits, and the row a finished review becomes.

**The refusals are the reason this file is long.** A corpus derived from personal data is tradeable
only once de-identified, so the two checks here are the only thing standing between a review that
did not finish and a `dataset` table something gets sold out of. Each is written twice -- once for
the document that is refused, once for the one that is not -- because a check that refuses
everything passes the first half on its own.

The builder under test is a stub: what a task answers is two methods, and none of what is asserted
here depends on which task answered them. That is the claim `sample_building.py` makes, so the
stub is how it gets tested.
"""

import json
from collections.abc import Mapping
from typing import Any

import pytest

from dataforce.modalities.text2text.dataset_management import (
    DatasetSampleBuilding,
    ShippedDatasetSample,
    StepNotRun,
)
from dataforce.modalities.text2text.dataset_management.sample_building import (
    PERSONAL_DATA_SCAN,
    REDACTION,
    read_redacted_classes,
    read_scanned_personal_data,
    read_shipped_sample,
)

PHONE = "0912345678"
EMAIL = "minh0912345678@vd.vn"
REVIEW_TEXT = f"user: Chào anh {PHONE}, mail {EMAIL}\nlabel: null"

ASKED = [{"role": "user", "content": "Chào anh <PHONE_1>, mail <EMAIL_1>"}]
CATALOG = [{"type": "function", "function": {"name": "OpenTicket"}}]
CALLED = [{"name": "OpenTicket", "arguments": {"ma_khach": "<PHONE_1>"}}]


def build_span(value: str, personal_data_class: str, numbered: int) -> dict[str, Any]:
    """One confirmed span over a value in `REVIEW_TEXT`, with the offsets read rather than typed."""
    return {
        "id": numbered,
        "start": REVIEW_TEXT.index(value),
        "end": REVIEW_TEXT.index(value) + len(value),
        "personal_data_class": personal_data_class,
        "placeholder": f"<{personal_data_class}_1>",
        "reason": None,
    }


SCANNED: dict[str, Any] = {
    "review_text": REVIEW_TEXT,
    "claims": [["PHONE", PHONE], ["EMAIL", EMAIL]],
    "spans": [build_span(PHONE, "PHONE", 1), build_span(EMAIL, "EMAIL", 2)],
    "redacted_text": "user: Chào anh <PHONE_1>, mail <EMAIL_1>\nlabel: null",
    "outcome": "redacted",
}


def build_document(**overridden: Any) -> dict[str, Any]:
    """A finished review: every step answered, and the redaction took."""
    document: dict[str, Any] = {
        "id": "s4471",
        "messages": [{"role": "user", "content": f"Chào anh {PHONE}, mail {EMAIL}"}],
        "tools": CATALOG,
        "label": [{"name": "OpenTicket", "arguments": {"ma_khach": PHONE}}],
        "new_messages": ASKED,
        "new_tools": None,
        "new_label": CALLED,
        "personal_data": SCANNED,
        "duplicate": None,
        "abnormal": None,
        "llm": None,
        "sft": None,
        "class": {"language": "vi", "ambiguous": False, "domain": "customer_care"},
    }
    return document | overridden


class CountingSampleBuilding(DatasetSampleBuilding):
    """A task that ships the turns and counts them. The two methods, answered as simply as they can be."""

    def build_input(self, shipped: ShippedDatasetSample) -> Mapping[str, Any]:
        return {"messages": list(shipped.messages)}

    def compute_facets(self, shipped: ShippedDatasetSample) -> Mapping[str, Any]:
        return {"number_turns": len(shipped.messages)}


@pytest.fixture
def building() -> CountingSampleBuilding:
    return CountingSampleBuilding()


# ------------------------------------------------------------------ what ships, and what does not


def test_a_new_key_is_what_ships_and_the_original_stays_behind() -> None:
    """The whole of what makes `dataset` exportable: its columns come off the redacted copies."""
    shipped = read_shipped_sample(build_document())

    assert shipped.messages == tuple(ASKED)
    assert shipped.label == tuple(CALLED)


def test_a_null_new_key_ships_what_arrived_rather_than_nothing() -> None:
    """`new_tools: null` is *no new version was made*, which the page writes for every clean
    catalog. Read literally it would ship an empty catalog for most of the corpus."""
    shipped = read_shipped_sample(build_document())

    assert shipped.tools == tuple(CATALOG)


def test_a_label_that_ships_as_nothing_is_kept_apart_from_one_that_ships_empty() -> (
    None
):
    """`()` and `None` are both *no answer was needed*, and the store is where § *Open* decides
    which of them a no-call sample writes -- so neither is turned into the other here."""
    assert read_shipped_sample(build_document(new_label=[], label=[])).label == ()
    assert read_shipped_sample(build_document(new_label=None, label=None)).label is None


# ------------------------------------------------------------------ the precondition


def test_a_sample_nobody_scanned_names_the_scan_and_builds_nothing(
    building: CountingSampleBuilding,
) -> None:
    """`personal_data: null` is step 2 never having run, and there is no proof to be had after.

    The message is asserted and not only the step, because *nobody scanned this* and *this scan
    will not read* are different things to be told even though they are one refusal -- and without
    it the null branch is held by nothing: a `null` falls through to the read below and comes back
    named the same way, wearing a validation dump for a message.
    """
    with pytest.raises(StepNotRun) as refused:
        building.build_sample(build_document(personal_data=None))

    assert PERSONAL_DATA_SCAN in str(refused.value)
    assert "personal_data is null" in str(refused.value)


def test_a_scan_that_will_not_read_is_the_same_refusal_as_no_scan_at_all() -> None:
    """Evidence nothing downstream can check proves nothing, so it is not evidence."""
    with pytest.raises(StepNotRun) as refused:
        read_scanned_personal_data(build_document(personal_data={"spans": "nonsense"}))

    assert PERSONAL_DATA_SCAN in str(refused.value)
    assert "will not read as a scan" in str(refused.value)


def test_a_confirmed_value_left_in_what_ships_names_the_redaction(
    building: CountingSampleBuilding,
) -> None:
    """The second refusal, and the one the law is about: a row holding a value the redaction was
    asked to remove is a row that may not be sold, so it may not be stored."""
    with pytest.raises(StepNotRun) as refused:
        building.build_sample(
            build_document(
                new_messages=[{"role": "user", "content": f"Chào anh {PHONE}"}]
            )
        )

    assert REDACTION in str(refused.value)
    # The span and not the value: a refusal naming it would put personal data into an HTTP body
    # and into whatever logs one, which is what this check exists to prevent.
    assert "span 1 (PHONE)" in str(refused.value)
    assert PHONE not in str(refused.value)


def test_a_value_left_in_the_label_is_refused_on_the_same_terms(
    building: CountingSampleBuilding,
) -> None:
    """Three fields ship and the check is over all three: a value redacted in the turns and left
    in an argument is a value in the corpus."""
    with pytest.raises(StepNotRun) as refused:
        building.build_sample(
            build_document(
                new_label=[{"name": "OpenTicket", "arguments": {"x": EMAIL}}]
            )
        )

    assert REDACTION in str(refused.value)


def test_a_value_left_in_a_field_with_no_new_version_is_refused_too(
    building: CountingSampleBuilding,
) -> None:
    """The reason the check reads what **ships** and not the `new_` keys literally. `new_tools` is
    `null` for a catalog nothing rewrote, so the original is what lands in the row -- and a check
    that only read `new_tools` would clear a catalog with a phone number in a tool description."""
    with pytest.raises(StepNotRun) as refused:
        building.build_sample(
            build_document(
                tools=[{"type": "function", "function": {"name": PHONE}}],
                new_tools=None,
            )
        )

    assert REDACTION in str(refused.value)


def test_a_value_json_would_escape_is_still_found_in_what_ships(
    building: CountingSampleBuilding,
) -> None:
    """The reason the check walks the strings rather than the sample serialised. A quote, a
    backslash and a newline are all escaped on the way into JSON, so a substring search over the
    serialised text would clear a record still holding one -- and it would do it silently, for the
    kind of value the check exists for."""
    quoted = 'Trần "Minh" Nguyễn\\An'
    text = f"user: {quoted} gọi"

    with pytest.raises(StepNotRun) as refused:
        building.build_sample(
            build_document(
                personal_data={
                    "review_text": text,
                    "claims": [["NAME", quoted]],
                    "spans": [
                        {
                            "id": 1,
                            "start": text.index(quoted),
                            "end": text.index(quoted) + len(quoted),
                            "personal_data_class": "NAME",
                            "placeholder": "<NAME_1>",
                            "reason": None,
                        }
                    ],
                    "redacted_text": "user: <NAME_1> gọi",
                    "outcome": "redacted",
                },
                new_messages=[{"role": "user", "content": f"{quoted} gọi"}],
            )
        )

    assert REDACTION in str(refused.value)


def test_a_value_standing_where_a_key_would_be_is_not_a_value_left_behind(
    building: CountingSampleBuilding,
) -> None:
    """The replacement copies a mapping key for key and rewrites the values, so a key is not
    somewhere a value could have been left -- and a check with a wider reach than the rewrite would
    refuse records nothing could ever make pass."""
    built = building.build_sample(
        build_document(new_messages=[{PHONE: "a key, not a value"}])
    )

    assert built.facets["personal_data"] == ["EMAIL", "PHONE"]


def test_a_span_reading_nothing_is_not_a_value_anything_could_have_left_behind(
    building: CountingSampleBuilding,
) -> None:
    """A reviewer's own row, with offsets that select no text. The replacement skips it for the
    same reason, and a precondition stricter than the rewrite would refuse finished records."""
    empty = build_span(PHONE, "PHONE", 1) | {"end": REVIEW_TEXT.index(PHONE)}

    built = building.build_sample(
        build_document(personal_data=SCANNED | {"spans": [empty]})
    )

    assert built.facets["personal_data"] == ["PHONE"]


def test_a_finished_review_is_refused_by_neither(
    building: CountingSampleBuilding,
) -> None:
    """The half that says the two checks above are checks and not a wall."""
    built = building.build_sample(build_document())

    assert built.input == {"messages": ASKED}
    assert built.label == tuple(CALLED)


# ------------------------------------------------------------------ the facets


def test_the_classes_redacted_are_read_off_the_confirmed_spans_and_sorted() -> None:
    """What kind of personal data used to be in a corpus a buyer is told is clean -- the one thing
    about it they cannot read off the rows. Sorted and named once, so two spans of one class are
    one entry and two orderings of the same scan are one value."""
    scanned = read_scanned_personal_data(build_document())

    assert read_redacted_classes(scanned) == ("EMAIL", "PHONE")


def test_a_sample_that_held_none_says_so_rather_than_saying_nothing(
    building: CountingSampleBuilding,
) -> None:
    """`[]` is a claim -- this sample had no personal data in it -- and is not the same reading as
    a column nobody filled."""
    clean = building.build_sample(
        build_document(personal_data=SCANNED | {"spans": [], "outcome": "reported"})
    )

    assert clean.facets["personal_data"] == []


def test_what_a_person_ticked_arrives_without_the_modality_naming_any_of_it(
    building: CountingSampleBuilding,
) -> None:
    """A declared facet is a claim nothing can check, so it is carried rather than read: the names
    under `class` are the task's and the page's, and this layer knows none of them."""
    built = building.build_sample(
        build_document(**{"class": {"domain": "telesale", "direction": "outbound"}})
    )

    assert built.facets["domain"] == "telesale"
    assert built.facets["direction"] == "outbound"


def test_a_tick_cannot_fill_in_a_facet_that_is_computed(
    building: CountingSampleBuilding,
) -> None:
    """*No derived facet was ever typed by a person.* Otherwise the rule is held by nothing but
    the two lists living in different files, and a page that grew the wrong tick would quietly
    describe a corpus that is not there."""
    built = building.build_sample(
        build_document(
            **{"class": {"personal_data": ["NONE"], "number_turns": 99, "domain": "x"}}
        )
    )

    assert built.facets["personal_data"] == ["EMAIL", "PHONE"]
    assert built.facets["number_turns"] == 1


def test_the_document_is_not_altered_by_being_read(
    building: CountingSampleBuilding,
) -> None:
    """It is stored whole in `record.document`, so a read that edited it would put the edit in the
    table that exists to be the evidence."""
    document = build_document()
    before = json.dumps(document, sort_keys=True, ensure_ascii=False)

    building.build_sample(document)

    assert json.dumps(document, sort_keys=True, ensure_ascii=False) == before
