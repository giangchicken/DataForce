"""The `text` modality: turns, static embeddings, and an escaped display control.

Three of the four members are here. Privacy detectors are the fourth and are
substantial enough to be their own task, so `personal_data_detectors` returns an empty
list until they land -- which the seam test tolerates and `pii_check` does not.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

from model2vec import StaticModel

from dataforce.core.errors import ConfigError
from dataforce.core.manifest import Manifest
from dataforce.core.record import Part, Record, TextPart, UIControl
from dataforce.modalities.base import Detector

__all__ = ["MANIFEST_NAME", "TextModality"]

# The manifest this modality is: `config/modalities/text.yaml`. It declares the name and
# version stamped into `producer.modality`, the embedding model, and which roles stay
# out of a vector. Reading it is the composition root's job -- importing this module
# opens no file, so it works from any working directory.
MANIFEST_NAME = "text"

# What separates one turn from the next when parts are embedded as one document.
_TURN_SEPARATOR = "\n\n"


@lru_cache(maxsize=1)
def _embedder(name: str) -> StaticModel:
    """The embedder, loaded once per model name. Downloads first use, then caches."""
    return StaticModel.from_pretrained(name)


def _text_parts(parts: Sequence[Part]) -> list[TextPart]:
    """The parts, asserting they are all text.

    A media part reaching this modality is a mis-composed run -- `modality` and
    `profile` are chosen together at the command line -- so it is a config error
    rather than something to skip quietly.
    """
    for part in parts:
        if not isinstance(part, TextPart):
            raise ConfigError(
                f"the text modality was given a {part.type!r} part; "
                "content that is not text needs the modality that owns it"
            )
    return [part for part in parts if isinstance(part, TextPart)]


def _call_arguments(function: Mapping[str, Any]) -> Any:
    """One call's arguments, whichever way the source spelled them.

    Every OpenAI-compatible provider sends `arguments` as a JSON *string* and some
    send the object; both are the same call, so both are parsed to the object and
    requirement 70 re-emits them in one form. Unparseable is a source-layout
    problem, named as one -- guessing here would put a different `rid` on a record
    depending on how its arguments were quoted.
    """
    given = function.get("arguments") or {}
    if not isinstance(given, str):
        return given
    try:
        return json.loads(given)
    except json.JSONDecodeError as broken:
        raise ConfigError(
            f"the arguments of a call to {function.get('name')!r} are not JSON: "
            f"{given!r} ({broken})"
        ) from None


def _canonical_call_text(calls: Sequence[Mapping[str, Any]]) -> str:
    """A turn's calls as one canonical string: sorted keys, no insignificant space.

    Requirement 70. A call keeps its name and its arguments and nothing else: the
    provider's `id` and `type` are wire bookkeeping, and carrying them would put a
    per-request identifier inside `rid`, so two runs over one source would disagree
    about which records they are.
    """
    return json.dumps(
        [
            {
                "name": call["function"]["name"],
                "arguments": _call_arguments(call["function"]),
            }
            for call in calls
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _turn_as_part(turn: Mapping[str, Any]) -> TextPart:
    """One turn as one part, whether it carries a string or a call.

    A string is copied out byte-for-byte and never re-spelled -- only a turn
    carrying structure *instead of* a string is rendered, so nothing about the
    shape this corpus is in changes. A turn with neither is a source-layout
    problem and says so: requirement 70 renders structure, and there is nothing
    here to guess an absent content from.
    """
    content = turn.get("content")
    if isinstance(content, str):
        return TextPart(role=turn["role"], text=content)
    calls = turn.get("tool_calls")
    if calls:
        return TextPart(role=turn["role"], text=_canonical_call_text(calls))
    raise ConfigError(
        f"a {turn.get('role')!r} turn carries neither string content nor "
        "tool_calls; one turn is one part, and there is nothing to build it from"
    )


class TextModality:
    """Conversational text, one part per turn.

    Identity, the embedding model and the roles left out of a vector are all declared,
    because `producer.modality` stamps this version onto every record it reads and the
    role exclusion is a measured choice rather than an implementation detail.
    """

    def __init__(self, declared: Manifest) -> None:
        self.manifest = declared
        self.name = declared.name
        self.version = declared.version
        embedding = declared.require("embedding")
        self.embedding_model: str = embedding["model"]
        # Roles that stay out of the vector. Measured on 200 real duplicate pairs:
        # retrieving a record's near-duplicate succeeds 200/200 on the conversation
        # alone and 0/200 with the system turn included, because a 4,000-character
        # instruction block swamps a 780-character conversation.
        self.not_embedded = frozenset(embedding["exclude_roles"])

    def content_parts(self, raw: Any) -> list[Part]:
        """One source item's turns, in order, each carrying its role.

        A turn carrying a `tool_calls` array rather than a string is still one
        part, rendered canonically so that two sources spelling one call
        differently produce one part, one digest and one `rid`. Rendering, not
        interpreting: what a call *means* is the profile's, and a modality that
        started reading arguments would have acquired an opinion about what an
        answer is.
        """
        return [_turn_as_part(turn) for turn in raw["messages"]]

    def embedding(self, parts: list[Part]) -> Sequence[float]:
        """One vector over the conversation, for near-duplicate detection only."""
        document = _TURN_SEPARATOR.join(
            part.text
            for part in _text_parts(parts)
            if part.role not in self.not_embedded
        )
        vector: list[float] = (
            _embedder(self.embedding_model).encode([document])[0].tolist()
        )
        return vector

    def personal_data_detectors(self) -> list[Detector]:
        """Empty until the Vietnamese detectors land. `pii_check` refuses this."""
        return []

    def display_config(self, record: Record) -> UIControl:
        """The turns as escaped markup.

        Corpus text is call-centre transcript that reached us through ASR and is
        never trusted as markup: every turn is escaped, so a conversation
        containing a tag is shown as that text rather than becoming structure in
        the annotator's page.
        """
        turns = "\n".join(
            f'  <div class="turn turn--{html.escape(part.role, quote=True)}">'
            f'<span class="role">{html.escape(part.role)}</span>'
            f"<pre>{html.escape(part.text)}</pre></div>"
            for part in _text_parts(record.content)
        )
        return UIControl(
            f'<HyperText name="content" clickableLinks="false">\n{turns}\n</HyperText>'
        )
