"""LOGIC · the conversions over the shapes in schema.py beside it.

``utils`` is the one module name AGENTS.md section 6 exempts, and only under this condition. A
shape and a conversion over it change for different reasons, so ``schema.py`` does not import
this module (I4).

**The implementation is here and not in ``__init__.py``.** All four of a modality's operations are
conversions -- an item into parts, parts into a vector, a record into a display fragment -- and
``__init__.py`` is a ``façade ·`` that holds nothing of its own (Requirement 2). So the object lives
beside the conversions it is made of and the façade re-exports it.

**An item this cannot read raises, and Requirement 43 says nothing may.** ``content_parts``
returns ``list[Part]`` and the signature is § *Modality*'s, so there is no value channel for *this
item is unreadable* -- the options are to raise or to fabricate a turn. Two things raise
``ConfigError``: an item whose ``messages`` is not a list, and a turn that declares no ``role``.
Requirement 43 permits a ``ConfigError`` only *before any record is read* and both of these fire
while records are being read, so the rule is broken here on purpose (§8): ``load_data`` is the only
caller and the only thing that can turn an unreadable item into a counted skip, and it cannot even
say *which* item from here -- ``content_parts`` is handed the item and no offset. T14 settles it,
and ``profiles/tool_decision/utils.py`` carries the same note for the same reason.

A non-string ``content`` is **not** in that category and does not raise: the content-block form is
the same standard Requirement 13 declares, so such an item is a declared item and has to become a
record.

**A turn that both speaks and calls joins the two on ``record.SPOKEN_AND_STATED``**, which is the
record's constant and not this module's, because ``tool_decision`` reads the calls back off it and a
convention spelled here and assumed there is connascence of meaning across a boundary neither side
may import. ``record.py``'s docstring says why it lives there, and one test in
``tests/stages/test_tool_decision.py`` builds a turn through this module and reads it through that
one, so neither end can move alone.

**A tool-call turn is rendered here, and that is content rather than an answer.** ``messages`` holds
the conversation and *nothing in it is an answer* (Requirement 13); an assistant turn that already
called a tool is context like any other. Requirement 15 asks that one call spelled three ways --
arguments as a JSON string, the same string reordered and re-spaced, and the object form -- be one
part and one ``record_id``, so the rendering is canonical JSON over the parsed arguments. What a
call *means* is still the profile's (Requirement 47): this module writes a turn down, it does not
decide what an answer is.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, final

from agent_toolkit.string_utils import normalize_text

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text.schema import Detector, DisplayConfig
from dataforce.record import SPOKEN_AND_STATED, Part, Record

if TYPE_CHECKING:
    from dataforce.modalities import Modality

# What turns one document into one vector. The static model behind it is loaded by
# `edge/bootstrap.py` and handed over, because the engine opens no file (I1) -- the same shape
# Requirement 16 gives a media modality's URI resolver, "declared when it is built".
type Encoder = Callable[[str], Sequence[float]]

# The keys this modality reads: its own manifest's, and the declared source shape's.
EMBEDDING = "embedding"
MODEL = "model"
EXCLUDE_ROLES = "exclude_roles"
MESSAGES = "messages"
ROLE = "role"
CONTENT = "content"
TOOL_CALLS = "tool_calls"
FUNCTION = "function"
ARGUMENTS = "arguments"
NAME = "name"
TEXT = "text"

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

# Vietnamese digits as they are spoken, which is the form no off-the-shelf scrubber detects.
# `mốt`, `tư` and `lăm` are the spoken variants of one, four and five and are why this is a list
# rather than a range.
SPOKEN_DIGITS = "không|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín"

# Six digits is the shortest identifier this corpus's sample carries (`480215`), and a run of ten
# starting with a zero is a Vietnamese mobile number. The two overlap on purpose: a phone number
# matches both, layer one is tuned for recall, and layer two is what decides which it was.
DIGIT_RUN = r"\d(?:[\s.-]?\d){5,}"
PHONE_DIGITS = r"\b0\d(?:[\s.-]?\d){8,9}\b"
SPOKEN_RUN = rf"(?:{SPOKEN_DIGITS})(?:[\s.,]+(?:{SPOKEN_DIGITS})){{5,}}"
SPOKEN_PHONE = rf"không(?:[\s.,]+(?:{SPOKEN_DIGITS})){{8,9}}"
EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
SPOKEN_EMAIL = r"[\w.+-]+\s+a\s+còng\s+[\w.\s-]+?\s+chấm\s+\w+"


def a_detector(name: str, personal_data_class: str, pattern: str) -> Detector:
    """One pattern in both the spellings layer one scans (Requirement 18).

    The tone-stripped twin is derived rather than written, so the pattern above is the only place
    the Vietnamese is spelled and the two cannot drift. `normalize_text` leaves a regular
    expression's metacharacters alone -- `\\s` is a backslash and an `s`, not whitespace -- so what
    changes is the literal text and nothing else.
    """
    return Detector(
        name=name,
        personal_data_class=personal_data_class,
        pattern=pattern,
        tone_stripped_pattern=normalize_text(pattern, remove_tone_marks=True),
    )


# The pattern layer, in code rather than in the manifest: a regular expression is tested, and these
# are tested against adversarial fixtures (spec.md § *Testing Strategy* item 6). What a corpus
# decides is which *classes* it turns out to carry, and that is what a first run over a declared
# source adds to this list.
DETECTORS = (
    a_detector("phone_digits", "PHONE", PHONE_DIGITS),
    a_detector("phone_spoken", "PHONE", SPOKEN_PHONE),
    a_detector("customer_id_digits", "CUSTOMER_ID", DIGIT_RUN),
    a_detector("customer_id_spoken", "CUSTOMER_ID", SPOKEN_RUN),
    a_detector("email_written", "EMAIL", EMAIL),
    a_detector("email_spoken", "EMAIL", SPOKEN_EMAIL),
)


def declared(manifest: Manifest, *path: str) -> Any:
    """One value the manifest declares, or a `ConfigError` naming the path and what is there."""
    reached: Any = manifest.declarations
    for key in path:
        if not isinstance(reached, Mapping) or key not in reached:
            held = sorted(reached) if isinstance(reached, Mapping) else reached
            raise ConfigError(
                f"config/modalities/{manifest.name}.yaml declares no "
                f"{'.'.join(path)}: {key!r} is missing from {held!r}"
            )
        reached = reached[key]
    return reached


def embedding_model(manifest: Manifest) -> str:
    """Which static model this modality's vectors come from.

    Read here rather than at the edge because the implementation that needs a key is the one that
    knows what it means (`manifest.py`), and loaded there rather than here because loading it opens
    a file (I1). `edge/bootstrap.py` calls this, builds the `Encoder`, and hands it over.
    """
    return str(declared(manifest, EMBEDDING, MODEL))


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


def canonical_json(value: Any) -> str:
    """One JSON value as the one string that means it: keys sorted, no incidental whitespace.

    Duplicated from `tool_decision/utils.py` on the same terms as `declaration` below -- the two
    axes share `name`, `version`, `Part` and one separator, and nothing else. A third shared helper
    would be a fourth, and the first key one axis needed and the other did not would put a
    profile's vocabulary in a module the modality imports.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
        return "".join(one_block(block) for block in content)
    return canonical_json(content)


def one_block(block: Any) -> str:
    """One content block's text, or the block itself where it holds none."""
    spoken = block.get(TEXT) if isinstance(block, Mapping) else None
    return spoken if isinstance(spoken, str) else canonical_json(block)


def stated_calls(calls: Sequence[Mapping[str, Any]]) -> str:
    """The calls a turn made, canonically, so Requirement 15's three spellings are one string.

    A call whose shape the declared input does not match is written down as it arrived rather than
    refused: a malformed turn is evidence for `label_check` to find, and a run always completes
    (Requirement 43).
    """
    return canonical_json(
        [
            {NAME: named.get(NAME, ""), ARGUMENTS: call_arguments(named.get(ARGUMENTS))}
            for call in calls
            for named in [call.get(FUNCTION) or {}]
        ]
    )


def call_arguments(stated: Any) -> Any:
    """One call's arguments as the object they mean, whichever of the two forms they arrived in."""
    if not isinstance(stated, str):
        return stated
    try:
        return json.loads(stated)
    except json.JSONDecodeError:
        return stated


def a_turn(turn: Mapping[str, Any]) -> Part:
    """One message as one part: what was said, and what was called, in the order it happened."""
    if ROLE not in turn:
        raise ConfigError(
            f"a text2text turn declares no {ROLE!r}; this one holds {sorted(turn)}"
        )
    calls = turn.get(TOOL_CALLS)
    written = [spoken_text(turn.get(CONTENT)), stated_calls(calls) if calls else None]
    return Part(
        type="text",
        role=str(turn[ROLE]),
        text=SPOKEN_AND_STATED.join(piece for piece in written if piece),
    )


@final
class Text2Text:
    """Conversational text: read verbatim, embedded statically, shown to a person as dialogue.

    **Built with what only the edge can produce.** Identity and both embedding choices come from
    `config/modalities/text2text.yaml`, whose filename is the identity (Requirement 40), and the
    static model that turns a document into a vector is loaded at the edge and handed over,
    because no engine module opens a file (I1). `exclude_roles` is a measured choice and the
    manifest records what re-measures it; nothing about either is assigned in this class body (I5).
    """

    def __init__(self, manifest: Manifest, encode: Encoder) -> None:
        self.name = manifest.name
        self.version = manifest.version
        self._encode = encode
        self._not_embedded = frozenset(declared(manifest, EMBEDDING, EXCLUDE_ROLES))

    def content_parts(self, item: Mapping[str, Any]) -> list[Part]:
        """One source item's turns, as ordered parts. Text verbatim, media by reference.

        Byte-identical to the source (Requirement 16): normalising here would change what
        `record_id` is computed over and what an annotator is shown.
        """
        turns = item.get(MESSAGES)
        if not isinstance(turns, list):
            raise ConfigError(
                f"a text2text item carries its turns under {MESSAGES!r} as a list; "
                f"this one holds {sorted(item)}"
            )
        return [a_turn(turn) for turn in turns]

    def embedding(self, parts: Sequence[Part]) -> list[float]:
        """A static vector for near-duplicate grouping. Same input, same vector, every run.

        The document is the conversation less the excluded roles, in order, which is the half of
        this that has to be a pure function of the parts: the vector itself is only as reproducible
        as the model the edge loaded, and a static one is why Requirement 23 holds.
        """
        document = TURN_SEPARATOR.join(
            part.text or ""
            for part in text_parts(parts)
            if part.role not in self._not_embedded
        )
        return [float(value) for value in self._encode(document)]

    def personal_data_detectors(self) -> list[Detector]:
        """The high-recall pattern layer, in this modality's terms."""
        return list(DETECTORS)

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
