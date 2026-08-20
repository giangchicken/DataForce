"""The `text` modality: turns, static embeddings, and an escaped display control.

Three of the four members are here. Privacy detectors are the fourth and are
substantial enough to be their own task, so `personal_data_detectors` returns an empty
list until they land -- which the seam test tolerates and `pii_check` does not.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from model2vec import StaticModel

from dataforce.modalities.base import Detector
from dataforce.shared.errors import ConfigError
from dataforce.shared.manifest import Manifest
from dataforce.shared.record import Part, Record, TextPart, UIControl

__all__ = ["MANIFEST_NAME", "TextModality"]

# The manifest this modality is: `config/modalities/text.yaml`. It declares the name and
# version stamped into `producer.modality`, the embedding model, and which roles stay
# out of a vector. Reading it is the composition root's job -- importing this module
# opens no file, so it works from any working directory.
MANIFEST_NAME = "text"

# What separates one turn from the next when parts are embedded as one document.
_TURN_SEPARATOR = "\n\n"


@lru_cache(maxsize=1)
def _model(name: str) -> StaticModel:
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

        The text is copied out byte-for-byte. Normalising here would silently
        change what `rid` is computed over and what an annotator is shown.
        """
        return [
            TextPart(role=turn["role"], text=turn["content"])
            for turn in raw["messages"]
        ]

    def embedding(self, parts: list[Part]) -> Sequence[float]:
        """One vector over the conversation, for near-duplicate detection only."""
        document = _TURN_SEPARATOR.join(
            part.text
            for part in _text_parts(parts)
            if part.role not in self.not_embedded
        )
        vector: list[float] = (
            _model(self.embedding_model).encode([document])[0].tolist()
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
