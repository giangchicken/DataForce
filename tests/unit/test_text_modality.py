"""The `text` modality: turns in, parts out, and nothing rendered as markup.

The escaping test is not defensive coding. This corpus is ASR output from
call-centre audio, so a customer saying something a browser reads as a tag is
ordinary input, and the annotator has to see the text that was said.
"""

from __future__ import annotations

import pytest
from conftest import TEXT

from dataforce.api.registry import Registry
from dataforce.core.errors import ConfigError
from dataforce.core.record import (
    MediaPart,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
)
from dataforce.modalities.base import Modality

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


# One call, spelled three ways a real provider spells it: arguments as a JSON string,
# the same string with the keys in the other order and whitespace added, and the object
# form. Requirement 70 says all three are one call.
CALL_AS_STRING = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "c2",
            "type": "function",
            "function": {
                "name": "SendStatement",
                "arguments": '{"ma_khach": "480215", "ky": "thang_nay"}',
            },
        }
    ],
}
CALL_REORDERED = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "c9",
            "type": "function",
            "function": {
                "arguments": '{ "ky" : "thang_nay" ,\n  "ma_khach" : "480215" }',
                "name": "SendStatement",
            },
        }
    ],
}
CALL_AS_OBJECT = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "type": "function",
            "function": {
                "name": "SendStatement",
                "arguments": {"ky": "thang_nay", "ma_khach": "480215"},
            },
        }
    ],
}

CANONICAL = (
    '[{"arguments":{"ky":"thang_nay","ma_khach":"480215"},"name":"SendStatement"}]'
)


def test_one_call_spelled_three_ways_is_one_part_and_one_rid() -> None:
    """Requirement 70, and invariant 2: identity cannot depend on quoting.

    A provider that quotes its arguments differently, or orders their keys
    differently, is describing the same call -- so the canonical rendering is what
    stops two ingests of one conversation becoming two records.
    """
    spellings = [CALL_AS_STRING, CALL_REORDERED, CALL_AS_OBJECT]

    parts = [TEXT.content_parts({"messages": [turn]}) for turn in spellings]

    for built in parts:
        assert len(built) == 1
        assert isinstance(built[0], TextPart)
        assert built[0].role == "assistant"
        assert built[0].text == CANONICAL
    assert len({compute_rid(built) for built in parts}) == 1


def test_a_call_carries_its_name_and_arguments_and_no_wire_bookkeeping() -> None:
    """`id` is per-request. In `rid` it would make one conversation two records."""
    (part,) = TEXT.content_parts({"messages": [CALL_AS_STRING]})

    assert isinstance(part, TextPart)
    assert "c2" not in part.text
    assert "function" not in part.text


def test_vietnamese_argument_values_are_not_escaped_away() -> None:
    """The canonical form is still the text a person reads on the annotator's page."""
    turn = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "type": "function",
                "function": {
                    "name": "OpenTicket",
                    "arguments": {"ly_do": "khách chưa nhận được sao kê"},
                },
            }
        ],
    }

    (part,) = TEXT.content_parts({"messages": [turn]})

    assert isinstance(part, TextPart)
    assert "khách chưa nhận được sao kê" in part.text


def test_a_conversation_mixing_strings_and_calls_builds_in_turn_order() -> None:
    """A `tool` role needs no declaration to be carried -- only to be read by meaning."""
    raw = {
        "messages": [
            {"role": "user", "content": "Mã của mình là 480215."},
            CALL_AS_STRING,
            {"role": "tool", "tool_call_id": "c2", "content": '{"so_du": 1250000}'},
            {"role": "assistant", "content": "Đã gửi sao kê cho bạn."},
        ]
    }

    parts = TEXT.content_parts(raw)

    assert [part.role for part in parts] == ["user", "assistant", "tool", "assistant"]
    assert isinstance(parts[2], TextPart)
    # a string turn is copied, never re-spelled: the space after the colon survives
    assert parts[2].text == '{"so_du": 1250000}'
    assert TEXT.display_config(record_from(list(parts)))


def test_a_string_turn_wins_over_calls_beside_it() -> None:
    """Requirement 70 renders structure carried *instead of* a string, not as well as.

    Rendering a turn that already has text would change what `rid` covers on every
    corpus where a provider sends both.
    """
    turn = {**CALL_AS_STRING, "content": "Để mình gửi sao kê nhé."}

    (part,) = TEXT.content_parts({"messages": [turn]})

    assert isinstance(part, TextPart)
    assert part.text == "Để mình gửi sao kê nhé."


def test_a_turn_with_neither_content_nor_calls_is_named_not_guessed() -> None:
    with pytest.raises(ConfigError, match="neither string content nor"):
        TEXT.content_parts({"messages": [{"role": "assistant", "content": None}]})


def test_arguments_that_are_not_json_name_the_tool_rather_than_crashing_blindly() -> (
    None
):
    turn = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"type": "function", "function": {"name": "SendMail", "arguments": "{oops"}}
        ],
    }

    with pytest.raises(ConfigError, match="SendMail"):
        TEXT.content_parts({"messages": [turn]})


def test_the_modality_is_registrable_through_the_real_gate() -> None:
    assert isinstance(TEXT, Modality)
    registry = Registry()
    registry.register_modality(TEXT)
    assert registry.modality("text") is TEXT


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
def test_a_record_carrying_a_call_embeds_like_any_other() -> None:
    """The vector is over the conversation, and a rendered call is part of it."""
    parts = TEXT.content_parts(
        {
            "messages": [
                {"role": "user", "content": "Gửi sao kê giúp mình."},
                CALL_AS_STRING,
                {"role": "tool", "tool_call_id": "c2", "content": "{}"},
            ]
        }
    )

    vector = TEXT.embedding(parts)

    assert len(vector) == 256
    assert all(isinstance(value, float) for value in vector)


@pytest.mark.integration
def test_embeddings_are_deterministic_across_two_runs() -> None:
    """Static embeddings, so dedup gives the same clusters on a re-run."""
    parts = TEXT.content_parts(RAW)

    first = TEXT.embedding(parts)
    second = TEXT.embedding(parts)

    assert list(first) == list(second)
    assert len(first) == 256  # potion-multilingual-128M
    assert all(isinstance(value, float) for value in first)
