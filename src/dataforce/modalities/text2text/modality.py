"""LOGIC · Text2Text — the object that answers the Modality protocol, and the turn it reads.

**The implementation is here and not in ``__init__.py``**, which is a ``façade ·`` that holds nothing
of its own (Requirement 2). All three of a modality's operations are conversions -- an item into
parts, parts into a vector, a part's text into the hits in it -- so the object lives beside the
conversions it is assembled from: layer one's four scans are picked in ``pii_detector.py``, the
document a vector is taken over is built in ``text_embeddor.py``, and what the manifest declares is
read through ``dataforce/declarations.py``.

**A turn is read here because a turn is content, and it reads only what every module in the family
reads.** ``role``, and a ``content`` that may be a string, a null or a content-block array -- the
whole of Requirement 13's shape minus the one part of it that is a *task's* vocabulary. A turn that
also acts used to be written down here, joined onto the text on a separator ``record.py`` carried for
both axes; what a turn *did* is what one module in this family answers with, and § *The two axes*
says a concept may not hold a convention only one of its modules speaks. So ``_turn_part`` is the
seam: this class writes down what was said, ``ToolDecision`` overrides it to write what was done onto
the part it gets back, and both the key it reads that from and the separator are that profile's own.
It is private because I23 holds an implementation's public surface to exactly the protocol's five
members, and a seam for a subclass is not a member.

The key names are deliberately not spelled here, and that is the rule rather than fastidiousness: a
docstring in the concept that names a profile's key teaches a reader of ``text2text`` a word only
``tool_decision`` speaks, which is the same leak in prose that the code no longer has.

**An item this cannot read raises, and Requirement 43 says nothing may.** ``content_parts`` returns
``list[Part]`` and the signature is § *Modality*'s, so there is no value channel for *this item is
unreadable* -- the options are to raise or to fabricate a turn. Two things raise ``ConfigError``: an
item whose ``messages`` is not a list, and a turn that declares no ``role``. Requirement 43 permits a
``ConfigError`` only *before any record is read* and both of these fire while records are being read,
so the rule is broken here on purpose: ``load_data`` is the only caller and the only thing that can
turn an unreadable item into a counted skip, and it cannot even say *which* item from here --
``content_parts`` is handed the item and no offset. T14 settles it, and
``profiles/tool_decision/profile.py`` carries the same note for the same reason.

``text_parts`` is here rather than in ``text_embeddor.py`` because refusing a media part is this
modality's rule about its own input and not a fact about a vector: both callers are below, and a part
reaching the wrong modality is a mis-composed run rather than a bad record.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text.pii_detector import personal_data_detectors
from dataforce.modalities.text2text.schema import Detector
from dataforce.modalities.text2text.text_embeddor import (
    Encoder,
    embedded_document,
    roles_not_embedded,
)
from dataforce.record import Part, canonical_json

if TYPE_CHECKING:
    from dataforce.modalities import Modality

# The declared source shape's keys, as one item and one turn spell them.
MESSAGES = "messages"
ROLE = "role"
CONTENT = "content"
TEXT = "text"


def spoken_text(content: Any) -> str:
    """What a turn said, whatever shape its `content` arrived in.

    A string is copied verbatim (Requirement 16) and a null turn said nothing. A **list** is the
    content-block form the same OpenAI shape declares -- `[{"type": "text", "text": "…"}]` -- and
    Requirement 13 declares that shape, so an item carrying one is a declared item and becomes a
    record. A text block contributes its text; any other block contributes its canonical JSON,
    which keeps it inside `record_id` instead of dropping it, and puts it where `label_check` and
    triage can see it. No separator is inserted between blocks, because any choice of one would be
    invented here and would change what a `record_id` covers.

    Blocks are joined rather than refused even where one of them is an image: a media block in a
    text2text run is a mis-composed pair, and the place that says so is `text_parts`, on a part
    whose *type* is not text -- refusing here would be a per-record raise on a readable item.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block[TEXT]
            if isinstance(block, Mapping) and isinstance(block.get(TEXT), str)
            else canonical_json(block)
            for block in content
        )
    return canonical_json(content)


def text_parts(parts: Sequence[Part]) -> tuple[Part, ...]:
    """The parts, having refused any that is not text.

    A media part reaching this modality is a mis-composed run rather than a bad record -- the pair
    is chosen once, at composition -- so it is the one thing here that raises (Requirement 43).
    """
    for part in parts:
        if part.type != "text":
            raise ConfigError(
                f"the text2text modality was handed a {part.type!r} part; content that is "
                "not text needs the modality that owns it"
            )
    return tuple(parts)


class Text2Text:
    """Conversational text: read verbatim, embedded, scanned for what a person must not see.

    **Not `@final`, and that is the whole of what T52 needed from this class.** A profile is one
    module inside a concept and now says so by subclassing it (Decision 24), so `ToolDecision` is a
    `Text2Text` and every later module in this family -- `summarize`, `classification` -- shares
    these three members rather than redeclaring them. What a subclass may not do is answer for a
    profile member: the two protocols stay separate and the identity is prefixed on both, which is
    why `modality_name` is not `name`.

    **What a subclass may override is one seam, and it is a turn.** `_turn_part` is where a module in
    this family writes its own vocabulary onto a part -- what a turn *did*, for `tool_decision` --
    and it is the only thing here a profile is expected to extend. The three members are the
    framework, and a framework a subclass has to reimplement is not one.

    **Built with what only the edge can produce.** Identity and both embedding choices come from
    `config/modalities/text2text.yaml`, whose filename is the identity (Requirement 40), and the
    model that turns a document into a vector is resolved at the edge and handed over, because no
    engine module opens a file or reaches a service (I1). `exclude_roles` is a measured choice and the
    manifest records what re-measures it; nothing about either is assigned in this class body (I5).

    **Layer one's language is a declaration too**, for the same reason and found later: which classes
    a hit is recorded under is this axis's and every word the scans read is the library's, so
    `personal_data_detectors` is built once here rather than being a module constant.
    """

    def __init__(self, manifest: Manifest, encode: Encoder) -> None:
        self.modality_name = manifest.name
        self.modality_version = manifest.version
        self._encode = encode
        self._not_embedded = roles_not_embedded(manifest)
        self._detectors = personal_data_detectors(manifest)

    def _turn_part(self, turn: Mapping[str, Any]) -> Part:
        """One message as one part: what was said, in the shape it was said in.

        The seam a module in this family overrides. What is read here is what every task in the
        family reads -- a role and a `content` -- and what a subclass adds is its own vocabulary,
        onto the part this returns.

        **A turn declaring no `role` raises, and Requirement 43 says nothing may.** This module's
        docstring carries the argument for both of this axis's raises. The short of it is that this
        returns a `Part` and has no value channel for *this turn is unreadable*, `load_data` is the
        only caller that knows the offset, and T14 settled it there by catching the raise and
        counting it against the item. A non-string `content` is **not** in that category and does not
        raise: the content-block form is the same standard Requirement 13 declares, so an item
        carrying one is a declared item and becomes a record.
        """
        if ROLE not in turn:
            raise ConfigError(
                f"a text2text turn declares no {ROLE!r}; this one holds {sorted(turn)}"
            )
        return Part(
            type="text", role=str(turn[ROLE]), text=spoken_text(turn.get(CONTENT))
        )

    def content_parts(self, item: Mapping[str, Any]) -> list[Part]:
        """One source item's turns, as ordered parts. Text verbatim, media by reference.

        Byte-identical to the source (Requirement 16): normalising here would change what
        `record_id` is computed over and what an annotator is shown.

        **This is the second reader of the item.** `build_record`'s own docstring calls itself the
        only place a source shape is read, and this reads `messages` and, inside a turn, `role` and
        `content`. It has to: turns are content. What it does *not* do is validate which shape the
        item is in -- the profile's `shape:` declaration is the only check, and this side assumes a
        chat item unconditionally. § *Profile* carries the correction; neither axis may hold the
        other's vocabulary, so there is nowhere to move the check to.
        """
        turns = item.get(MESSAGES)
        if not isinstance(turns, list):
            raise ConfigError(
                f"a text2text item carries its turns under {MESSAGES!r} as a list; "
                f"this one holds {sorted(item)}"
            )
        return [self._turn_part(turn) for turn in turns]

    def embedding(self, parts: Sequence[Part]) -> list[float]:
        """A vector for near-duplicate grouping, from the model the manifest names.

        The document is the conversation less the excluded roles, in order, which is the half of
        this that is a pure function of the parts and the whole of what this module can promise:
        the vector itself is only as reproducible as the endpoint the edge resolved, which is the
        limit Requirement 23 now states.
        """
        document = embedded_document(text_parts(parts), self._not_embedded)
        return [float(value) for value in self._encode(document)]

    def personal_data_detectors(self) -> list[Detector]:
        """The high-recall first layer: one scan per class of personal data."""
        return list(self._detectors)


if TYPE_CHECKING:

    def _answers_its_protocol(manifest: Manifest, encode: Encoder) -> "Modality":
        """`mypy --strict` checks this return, so a member that stops matching fails the build.

        There is nowhere else for that check to happen yet: a registry is handed a `Modality` by
        `edge/bootstrap.py`, which lands in T27, and `make check` runs mypy over `src/` alone -- an
        annotation in a test proves nothing. The cost is one function that never runs.
        """
        return Text2Text(manifest, encode)
