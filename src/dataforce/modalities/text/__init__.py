"""The `text` modality: turns, static embeddings, and an escaped display control.

Three of the four members are here. Privacy detectors are the fourth and are
substantial enough to be their own task, so `privacy_detectors` returns an empty
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
from dataforce.shared.record import Part, Record, TextPart, UIControl

__all__ = ["EMBEDDING_MODEL", "TEXT", "TextModality"]

# Static embeddings: a vector is a pure function of its input, with no sampling
# and no ordering effect, so two runs over one corpus dedup identically.
EMBEDDING_MODEL = "minishlab/potion-multilingual-128M"

# What separates one turn from the next when parts are embedded as one document.
_TURN_SEPARATOR = "\n\n"

# The system turn is left out of the vector. Measured on 200 real duplicate pairs
# from the first corpus: retrieving a record's near-duplicate succeeds 200/200 times
# on the conversation alone and 0/200 times with the system turn included, because a
# 4,000-character instruction block swamps a 780-character conversation and every
# record's nearest neighbour becomes whichever other record was given similar
# instructions. Catalog similarity is what `group_key` measures; this measures
# whether two records say the same thing.
_NOT_EMBEDDED = frozenset({"system"})


@lru_cache(maxsize=1)
def _model() -> StaticModel:
    """The embedder, loaded once. Downloads on first use, then reads the cache."""
    return StaticModel.from_pretrained(EMBEDDING_MODEL)


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
    """Conversational text, one part per turn."""

    name = "text"
    version = "1"

    def load(self, raw: Any) -> list[Part]:
        """One source item's turns, in order, each carrying its role.

        The text is copied out byte-for-byte. Normalising here would silently
        change what `rid` is computed over and what an annotator is shown.
        """
        return [
            TextPart(role=turn["role"], text=turn["content"])
            for turn in raw["messages"]
        ]

    def embed(self, parts: list[Part]) -> Sequence[float]:
        """One vector over the conversation, for near-duplicate detection only."""
        document = _TURN_SEPARATOR.join(
            part.text for part in _text_parts(parts) if part.role not in _NOT_EMBEDDED
        )
        vector: list[float] = _model().encode([document])[0].tolist()
        return vector

    def privacy_detectors(self) -> list[Detector]:
        """Empty until the Vietnamese detectors land. `pii_check` refuses this."""
        return []

    def display_control(self, record: Record) -> UIControl:
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


TEXT = TextModality()
