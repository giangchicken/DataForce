"""LOGIC · Text2Text -- the object that answers the Modality protocol.

**The implementation is here and not in ``__init__.py``**, which is a ``façade ·`` that holds nothing
of its own (Requirement 2). All four of a modality's operations are conversions -- an item into
parts, parts into a vector, a record into a display fragment -- so the object lives beside the
conversions it is assembled from: a turn becomes a part in ``turns.py``, layer one's patterns are
built in ``detectors.py``, and what the manifest declares is read through
``dataforce/declarations.py``.

**An item this cannot read raises, and Requirement 43 says nothing may.** ``content_parts`` returns
``list[Part]`` and the signature is § *Modality*'s, so there is no value channel for *this item is
unreadable* -- the options are to raise or to fabricate a turn. Two things raise ``ConfigError``: an
item whose ``messages`` is not a list, here, and a turn that declares no ``role``, in ``turns.py``.
Requirement 43 permits a ``ConfigError`` only *before any record is read* and both of these fire
while records are being read, so the rule is broken here on purpose: ``load_data`` is the only
caller and the only thing that can turn an unreadable item into a counted skip, and it cannot even
say *which* item from here -- ``content_parts`` is handed the item and no offset. T14 settles it,
and ``profiles/tool_decision/profile.py`` carries the same note for the same reason.

``text_parts`` is here rather than in ``turns.py`` because refusing a media part is this modality's
rule about its own input and not a fact about a turn: both callers are below, and a part reaching
the wrong modality is a mis-composed run rather than a bad record.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from dataforce.declarations import declared_name, declared_roles
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text.detectors import personal_data_detectors
from dataforce.modalities.text2text.schema import Detector, DisplayConfig
from dataforce.modalities.text2text.turns import CONTENT, ROLE, a_turn
from dataforce.record import Part, Record

if TYPE_CHECKING:
    from dataforce.modalities import Modality

# What turns one document into one vector. The model behind it is an endpoint `edge/bootstrap.py`
# resolves and hands over, because the engine opens no file and reaches no service (I1) -- the same
# shape Requirement 16 gives a media modality's URI resolver, "declared when it is built".
type Encoder = Callable[[str], Sequence[float]]


# What this modality's own manifest declares, and the one key a source item carries.
EMBEDDING = "embedding"
MODEL = "model"
EXCLUDE_ROLES = "exclude_roles"
MESSAGES = "messages"

# The key `<Paragraphs>` reads its turns from, and the one key this half of the config owns.
CONVERSATION = "conversation"

# What separates one turn from the next in the document a vector is taken over.
TURN_SEPARATOR = "\n\n"

# Requirement 52: `<Chat>` renders this exactly the way this modality wants and is Enterprise-only,
# so the community path is `<Paragraphs layout="dialogue">`. `$question` is the profile's string and
# `$conversation` is this half's data -- the tag that shows one is still the display half's.
DISPLAY_TAGS = (
    '<Paragraphs name="conversation" value="$conversation"\n'
    '            layout="dialogue" nameKey="role" textKey="content"/>\n'
    '<Header value="$question"/>'
)


def embedding_model(manifest: Manifest) -> str:
    """Which model this modality's vectors come from, by the name its deployment serves it under.

    Read here rather than at the edge because the implementation that needs a key is the one that
    knows what it means (`manifest.py`), and resolved there rather than here because resolving it
    opens `config/model/<model>.json` (I1). `edge/bootstrap.py` calls this, builds the `Encoder`,
    and hands it over.
    """
    return declared_name(manifest, EMBEDDING, MODEL)


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
    """Conversational text: read verbatim, embedded, shown to a person as dialogue.

    **Not `@final`, and that is the whole of what T52 needed from this class.** A profile is one
    module inside a concept and now says so by subclassing it (Decision 24), so `ToolDecision` is a
    `Text2Text` and every later module in this family -- `summarize`, `classification` -- shares
    these four members rather than redeclaring them. What a subclass may not do is answer for a
    profile member: the two protocols stay separate and the identity is prefixed on both, which is
    why `modality_name` is not `name`.

    **Built with what only the edge can produce.** Identity and both embedding choices come from
    `config/modalities/text2text.yaml`, whose filename is the identity (Requirement 40), and the
    model that turns a document into a vector is resolved at the edge and handed over, because no
    engine module opens a file or reaches a service (I1). `exclude_roles` is a measured choice and the
    manifest records what re-measures it; nothing about either is assigned in this class body (I5).

    **Layer one's language is a declaration too**, for the same reason and found later: the shapes
    it scans for are this module's and the words they are filled with are the corpus's, so
    `personal_data_detectors` is built once here rather than being a module constant.
    """

    def __init__(self, manifest: Manifest, encode: Encoder) -> None:
        self.modality_name = manifest.name
        self.modality_version = manifest.version
        self._encode = encode
        self._not_embedded = declared_roles(manifest, EMBEDDING, EXCLUDE_ROLES)
        self._detectors = personal_data_detectors(manifest)

    def content_parts(self, item: Mapping[str, Any]) -> list[Part]:
        """One source item's turns, as ordered parts. Text verbatim, media by reference.

        Byte-identical to the source (Requirement 16): normalising here would change what
        `record_id` is computed over and what an annotator is shown.

        **This is the second reader of the item.** `build_record`'s own docstring calls itself the
        only place a source shape is read, and this reads `messages` and, inside a turn, `role`,
        `content`, `tool_calls` and a call's `function` and `arguments`. It has to: turns are content.
        What it does *not* do is validate which shape the item is in -- the profile's `shape:`
        declaration is the only check, and this side assumes a chat item unconditionally. § *Profile*
        carries the correction; neither axis may hold the other's vocabulary, so there is nowhere to
        move the check to.
        """
        turns = item.get(MESSAGES)
        if not isinstance(turns, list):
            raise ConfigError(
                f"a text2text item carries its turns under {MESSAGES!r} as a list; "
                f"this one holds {sorted(item)}"
            )
        return [a_turn(turn) for turn in turns]

    def embedding(self, parts: Sequence[Part]) -> list[float]:
        """A vector for near-duplicate grouping, from the model the manifest names.

        The document is the conversation less the excluded roles, in order, which is the half of
        this that is a pure function of the parts and the whole of what this module can promise:
        the vector itself is only as reproducible as the endpoint the edge resolved, which is the
        limit Requirement 23 now states.
        """
        document = TURN_SEPARATOR.join(
            part.text or ""
            for part in text_parts(parts)
            if part.role not in self._not_embedded
        )
        return [float(value) for value in self._encode(document)]

    def personal_data_detectors(self) -> list[Detector]:
        """The high-recall pattern layer, in this modality's terms."""
        return list(self._detectors)

    def display_config(self, record: Record) -> DisplayConfig:
        """The *display* half of the annotation config. Never the capture half.

        The turns go into task *data* rather than into markup, so nothing is escaped: `<Paragraphs>`
        reads a JSON array, and a transcript containing a tag stays that text instead of becoming
        structure in the annotator's page.
        """
        return DisplayConfig(
            tags=DISPLAY_TAGS,
            data={
                CONVERSATION: [
                    {ROLE: part.role, CONTENT: part.text or ""}
                    for part in text_parts(record.content)
                ]
            },
        )


if TYPE_CHECKING:

    def _answers_its_protocol(manifest: Manifest, encode: Encoder) -> "Modality":
        """`mypy --strict` checks this return, so a member that stops matching fails the build.

        There is nowhere else for that check to happen yet: a registry is handed a `Modality` by
        `edge/bootstrap.py`, which lands in T27, and `make check` runs mypy over `src/` alone -- an
        annotation in a test proves nothing. The cost is one function that never runs.
        """
        return Text2Text(manifest, encode)
