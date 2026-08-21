"""The record shape, and the two claims about it that later stages rely on."""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from dataforce.core.record import (
    MediaPart,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
    stamp,
)


class _Impl:
    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version


def _conversation(user_text: str) -> list[TextPart]:
    return [
        TextPart(role="system", text="You are a router."),
        TextPart(role="user", text=user_text),
    ]


def test_rid_is_sixteen_lowercase_hex() -> None:
    rid = compute_rid(_conversation("hello"))
    assert len(rid) == 16
    assert set(rid) <= set("0123456789abcdef")


def test_rid_is_stable_across_a_shuffled_reingest() -> None:
    """Invariant 2: order between records is not content, so ids do not move."""
    corpus = [_conversation(f"turn {i}") for i in range(50)]
    first = [compute_rid(parts) for parts in corpus]

    shuffled = list(corpus)
    random.Random(0).shuffle(shuffled)
    again = {compute_rid(parts) for parts in shuffled}

    assert set(first) == again
    assert len(again) == 50


def test_rid_depends_on_order_within_a_record() -> None:
    """Order inside a record is content: who said what is not interchangeable."""
    parts = _conversation("hello")
    assert compute_rid(parts) != compute_rid(list(reversed(parts)))


def test_media_contributes_its_checksum_not_its_bytes() -> None:
    one = MediaPart(type="audio", role="user", uri="media/ab/a.wav", sha256="abc")
    moved = MediaPart(type="audio", role="user", uri="media/zz/b.wav", sha256="abc")
    other = MediaPart(type="audio", role="user", uri="media/ab/a.wav", sha256="def")

    assert compute_rid([one]) == compute_rid([moved])
    assert compute_rid([one]) != compute_rid([other])


def test_a_media_part_cannot_be_built_without_a_reference() -> None:
    with pytest.raises(ValidationError):
        MediaPart(type="audio", role="user", uri="media/ab/a.wav")  # type: ignore[call-arg]


def test_media_parts_carry_modality_metadata_and_text_parts_do_not() -> None:
    part = MediaPart(type="audio", role="user", uri="u", sha256="s", duration_s=12.4)
    assert part.model_dump()["duration_s"] == 12.4

    with pytest.raises(ValidationError):
        TextPart(role="user", text="hi", duration_s=12.4)  # type: ignore[call-arg]


def test_a_record_defaults_every_field_a_later_stage_owns() -> None:
    record = Record(
        rid=compute_rid(_conversation("hi")),
        source=Source(file_sha256="abc", offset=0, ingested_at="2026-08-18T00:00:00Z"),
        producer=Producer(modality="text@1", profile="tool_decision@1"),
        content=list(_conversation("hi")),
    )
    assert record.parse_status == "ok"
    assert record.failed_checks == []
    assert record.jury is None
    assert record.split is None


def test_the_producer_stamp_names_both_axes_with_versions() -> None:
    producer = stamp(_Impl("text", "1"), _Impl("tool_decision", "2"))
    assert producer.modality == "text@1"
    assert producer.profile == "tool_decision@2"
