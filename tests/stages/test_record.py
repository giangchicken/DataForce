"""The bus, before there is a stage to put on it: identity, immutability, and the refused key.

`tests/stages/` holds what a stage reads and writes, and the record *is* what every stage reads
and writes -- so the tests that fix its shape sit where the stage tests will, rather than in
`tests/properties/`, which spec.md § *Package layout* gives to I8 and I11 over a live corpus.

Three things are proved here. **I9**, that `record_id` is a function of content and of nothing
else: a shuffled re-ingest produces the same set of ids, and a changed character produces a
different one. **I10**, that no answer space can be stored. And the two structural promises the
type makes to every stage -- a part carries what its type declares, and a record handed to a stage
cannot be edited by it.

Every fixture below is invented (AGENTS.md §9). The Vietnamese is there because the corpus this
runs over is Vietnamese and an id over non-ASCII is worth exercising, not for flavour.
"""

import random
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from dataforce.record import (
    Branch,
    Part,
    PersonalDataScan,
    PersonalDataSpan,
    Provenance,
    Record,
    record_id_for,
)

TURNS = (
    "Mã của mình là 0900123456.",
    "Cho mình xem sao kê tháng này.",
    "Bạn muốn gửi sao kê qua email nào?",
    "Mở giúp mình một ticket nhé.",
)


def a_text_part(text: str, role: str = "user") -> Part:
    """One turn of invented conversation."""
    return Part(type="text", role=role, text=text)


def a_media_part(uri: str, sha256: str) -> Part:
    """One turn that is a file: the shape a media modality will write (Requirement 8)."""
    return Part(type="audio", role="user", uri=uri, sha256=sha256)


def a_provenance(offset: int = 0) -> Provenance:
    """What `load_data` stamps. Only `offset` varies here: it is what a shuffle moves."""
    return Provenance(
        source_file_sha256="a1b2c3d4" * 8,
        offset=offset,
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
        modality="text2text@1",
        profile="tool_decision@1",
        run_id="r_2026-01-01T00:00:00Z_0000",
    )


def a_record(*content: Part, **overrides: Any) -> Record:
    """A record with this content, and everything else the way `load_data` would leave it."""
    fields: dict[str, Any] = {
        "record_id": record_id_for(content),
        "source_id": "s1",
        "branch": Branch(modality="text2text", profile="tool_decision"),
        "provenance": a_provenance(),
        "content": content,
        "label": ({"name": "SendStatement", "arguments": {"ky": "thang_nay"}},),
    }
    return Record(**{**fields, **overrides})


def a_corpus(order: Sequence[int]) -> list[Record]:
    """One corpus ingested in the order given: `offset` follows position, and the id must not."""
    return [
        a_record(
            a_text_part(TURNS[turn]),
            source_id=f"s{turn}",
            provenance=a_provenance(offset=position),
        )
        for position, turn in enumerate(order)
    ]


def test_a_record_id_is_sixteen_lowercase_hex() -> None:
    """Requirement 6, on the surface a join reads."""
    record_id = record_id_for((a_text_part(TURNS[0]),))

    assert len(record_id) == 16
    assert set(record_id) <= set("0123456789abcdef")


def test_a_shuffled_re_ingest_produces_the_same_set_of_ids() -> None:
    """I9: position in the source file is not content, so re-reading it shuffled joins the same.

    The offsets and the `source_id`s move with the shuffle, which is what makes this a re-ingest
    rather than a re-sort of one list.
    """
    order = list(range(len(TURNS)))
    shuffled = random.Random(20260824).sample(order, len(order))

    assert shuffled != order, "the fixture shuffle has to actually move something"
    assert {r.record_id for r in a_corpus(shuffled)} == {
        r.record_id for r in a_corpus(order)
    }


def test_one_changed_character_changes_the_id() -> None:
    """I9's other half: an id that survives an edit to the text is not an id of the content."""
    original = record_id_for((a_text_part("Mã của mình là 0900123456."),))
    edited = record_id_for((a_text_part("Mã của mình là 0900123457."),))

    assert original != edited


def test_order_within_a_record_is_content() -> None:
    """Requirement 7: the same turns in the other order are a different conversation."""
    turns = (a_text_part(TURNS[1]), a_text_part(TURNS[2], role="assistant"))

    assert record_id_for(turns) != record_id_for(tuple(reversed(turns)))


def test_moving_a_media_file_does_not_change_the_id() -> None:
    """Requirement 8: the digest is the content; the uri is where it happens to sit today."""
    digest = "f" * 64

    assert record_id_for((a_media_part("data/raw/a.wav", digest),)) == record_id_for(
        (a_media_part("archive/2026/a.wav", digest),)
    )


def test_changing_what_is_in_a_media_file_does_change_the_id() -> None:
    """Requirement 8, the half that makes the first half safe."""
    uri = "data/raw/a.wav"

    assert record_id_for((a_media_part(uri, "f" * 64),)) != record_id_for(
        (a_media_part(uri, "e" * 64),)
    )


@pytest.mark.parametrize(
    "part",
    [
        pytest.param({"type": "text", "role": "user"}, id="text-without-text"),
        pytest.param(
            {"type": "audio", "role": "user", "uri": "a.wav"}, id="media-without-digest"
        ),
        pytest.param(
            {"type": "audio", "role": "user", "sha256": "f" * 64},
            id="media-without-uri",
        ),
        pytest.param(
            {"type": "text", "role": "user", "text": "hi", "sha256": "f" * 64},
            id="text-carrying-a-digest",
        ),
    ],
)
def test_a_part_missing_what_its_type_declares_is_refused(part: dict[str, Any]) -> None:
    """A part that hashes as a hole would collide with every other part missing the same field."""
    with pytest.raises(ValidationError):
        Part(**part)


def test_the_record_has_no_answer_space_field() -> None:
    """I10: `answer_schema` materialises the space from the record; nothing stores a second copy."""
    assert "answer_space" not in Record.model_fields


def test_constructing_a_record_with_an_answer_space_raises() -> None:
    """I10's other half -- the field being absent is not the same as the key being refused."""
    with pytest.raises(ValidationError):
        a_record(a_text_part(TURNS[0]), answer_space=[{"name": "SendStatement"}])


def test_a_stage_cannot_edit_the_record_it_was_handed() -> None:
    """Requirement 41 structurally: a stage returns a copy one key richer, or it returns nothing."""
    record = a_record(a_text_part(TURNS[0]))

    with pytest.raises(ValidationError):
        record.content_version = 2


def test_a_copy_carrying_one_more_key_keeps_the_identity_and_the_content() -> None:
    """What a stage actually does: `model_copy(update=…)`, and the join key survives it."""
    record = a_record(a_text_part(TURNS[0]))

    written = record.model_copy(
        update={
            "data_quality": record.data_quality.model_copy(update={"pii_check": None})
        }
    )

    assert (written.record_id, written.content) == (record.record_id, record.content)


def test_a_record_survives_the_trip_through_json() -> None:
    """The bus is written as JSONL and posted as a body, and one of its keys is a keyword here.

    `pii_check`'s span key is `class` on the record and `personal_data_class` in Python, so the
    alias has to hold in both directions. If it holds in only one, the file a run wrote and the
    body a route accepts stop being the same record, which is what I15 is about.
    """
    scan = PersonalDataScan(
        decision="redacted",
        content_version_scanned=1,
        spans=(
            PersonalDataSpan(
                part=0,
                start=16,
                end=26,
                **{"class": "CUSTOMER_ID"},
                verified=True,
                placeholder="<CUSTOMER_ID_1>",
            ),
        ),
        classes=("CUSTOMER_ID",),
        unverified=0,
    )
    record = a_record(a_text_part(TURNS[0]))
    scanned = record.model_copy(
        update={
            "data_quality": record.data_quality.model_copy(update={"pii_check": scan})
        }
    )

    written = scanned.model_dump()

    assert written["data_quality"]["pii_check"]["spans"][0]["class"] == "CUSTOMER_ID"
    assert Record.model_validate_json(scanned.model_dump_json()) == scanned
