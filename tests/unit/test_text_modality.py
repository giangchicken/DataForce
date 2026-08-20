"""The `text` modality: turns in, parts out, and nothing rendered as markup.

The escaping test is not defensive coding. This corpus is ASR output from
call-centre audio, so a customer saying something a browser reads as a tag is
ordinary input, and the annotator has to see the text that was said.
"""

from __future__ import annotations

import pytest

from dataforce.modalities import registry
from dataforce.modalities.base import Modality
from dataforce.modalities.text import TEXT
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import (
    MediaPart,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
)

MARKERS = (
    "{trigger}",
    "{hold_other}",
    "{hold_missing}",
    "{constraint}",
    "{turn_trigger}",
)

RAW = {
    "idx": 7,
    "messages": [
        {
            "role": "system",
            "content": "TOOLS:\n[SendMail_1a]\nKhi nào gọi: {trigger} khách",
        },
        {"role": "user", "content": "cho tôi gửi mail nhé"},
        {"role": "assistant", "content": '["SendMail_1a"]'},
    ],
    "meta": {"label": ["SendMail_1a"]},
}


def record_from(parts: list[TextPart]) -> Record:
    return Record(
        rid=compute_rid(parts),
        source=Source(
            file_sha256="0" * 64, offset=0, ingested_at="2026-08-19T00:00:00Z"
        ),
        producer=Producer(modality="text@1", profile="fake@1"),
        content=list(parts),
    )


def test_three_turns_become_three_text_parts_with_roles_preserved() -> None:
    parts = TEXT.content_parts(RAW)

    assert [part.type for part in parts] == ["text", "text", "text"]
    assert [part.role for part in parts] == ["system", "user", "assistant"]


def test_loaded_text_is_byte_identical_to_the_source() -> None:
    """Normalising here would change what `rid` covers and what an annotator reads."""
    parts = TEXT.content_parts(RAW)

    for part, turn in zip(parts, RAW["messages"], strict=True):
        assert isinstance(part, TextPart)
        assert part.text == turn["content"]


def test_the_modality_is_registrable_through_the_real_gate() -> None:
    assert isinstance(TEXT, Modality)
    registry.register(TEXT)
    assert registry.get("text") is TEXT


def test_privacy_detectors_are_empty_until_they_land() -> None:
    """Declared, so the stage that refuses an undetected corpus has something to read."""
    assert TEXT.personal_data_detectors() == []


def test_a_tag_in_the_corpus_is_shown_as_text_not_rendered() -> None:
    hostile = "<script>alert('x')</script> và <img src=x onerror=1>"
    control = TEXT.display_config(record_from([TextPart(role="user", text=hostile)]))

    assert "<script>" not in control
    assert "<img" not in control
    assert "&lt;script&gt;" in control


def test_marker_tokens_survive_the_display_control_byte_identically() -> None:
    """Invariant 1: the DSL is the annotator's only evidence, on every surface."""
    system = " ".join(MARKERS)
    control = TEXT.display_config(record_from([TextPart(role="system", text=system)]))

    for marker in MARKERS:
        assert marker in control


def test_a_role_cannot_smuggle_an_attribute_into_the_control() -> None:
    """Roles come from the source too, so they are escaped on the same terms."""
    control = TEXT.display_config(
        record_from([TextPart(role='user" onclick="steal()', text="ok")])
    )

    assert 'onclick="steal()"' not in control


def test_a_media_part_is_a_configuration_error_not_a_silent_skip() -> None:
    media = MediaPart(
        type="audio", role="user", uri="s3://bucket/a.wav", sha256="0" * 64
    )

    with pytest.raises(ConfigError, match="audio"):
        TEXT.embedding([media])


@pytest.mark.integration
def test_embeddings_are_deterministic_across_two_runs() -> None:
    """Static embeddings, so dedup gives the same clusters on a re-run."""
    parts = TEXT.content_parts(RAW)

    first = TEXT.embedding(parts)
    second = TEXT.embedding(parts)

    assert list(first) == list(second)
    assert len(first) == 256  # potion-multilingual-128M
    assert all(isinstance(value, float) for value in first)
