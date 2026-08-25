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
from typing import TYPE_CHECKING, Any, NamedTuple, final

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
LANGUAGE = "language"
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

# `@` and `.` are written the same way in every language that writes an address at all, so the one
# shape that needs no language is a constant.
EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"

# Six digits is the shortest identifier this corpus's sample carries (`480215`). Not a language
# fact and not declared with the rest: raising it drops short ids out of layer one and lowering it
# makes every price a hit, and what re-measures it is layer one's recall over a declared corpus.
IDENTIFIER_DIGITS = 6


class SpokenForms(NamedTuple):
    """The words one language says a digit, an `@` and a `.` with.

    **Every field is a fact about a language and none is a fact about a country or a corpus.** That
    is what makes this the half that leaves: `agent_toolkit.language` holds this exact shape on a
    branch already, and the day this repository's pin moves past it, I6 fails on the `def
    spoken_forms` below and the fix is an import and a deletion. `PhonePlan` beside it does *not*
    leave, and its own docstring says why.

    `digits` is a set of words rather than ten indexed by value, because a language may say a digit
    more than one way -- `một`/`mốt`, `bốn`/`tư`, `năm`/`lăm`. `zero` is separate because it is the
    one word whose position matters: a dictated number opens with it.
    """

    digits: tuple[str, ...]  # every word this language says a digit with
    zero: str  # the word a dictated number opens with
    at: str  # `@`, read aloud
    dot: str  # `.`, read aloud


class PhonePlan(NamedTuple):
    """How long a phone number is, written and dictated, and what it opens with.

    **Not a language fact, which is why it did not go into the library** -- and this is what writing
    the library half turned up. How many digits a mobile number carries is a fact about a *country*
    and changes when a regulator says so. Worse, one of these numbers is wrong: `written_digits` is
    ten or eleven, which is a Vietnamese mobile and its pre-2018 form, and `spoken_words` is nine or
    ten, where nine dictated digits is not a valid number at all. Both patterns read `{8,9}` before
    either was named -- one of them with an extra digit atom in front -- so it was invisible.

    It stays as it is on purpose. A refactor that moves a literal may not move a boundary: a
    detector's reach decides what gets redacted, and correcting this shrinks what layer one finds.
    What settles it is a measurement of layer one's recall over a declared corpus, which is the
    pilot's. Shipping it to `agent-toolkit` would have made this repository's off-by-one a fact
    about Vietnamese.
    """

    prefix: str  # the national trunk prefix, written
    written_digits: tuple[int, int]  # total digits written, shortest first
    spoken_words: tuple[int, int]  # total words dictated, shortest first


# The language packs, in the shape `agent_toolkit.language` keeps them. `mốt`, `tư` and `lăm` are
# Vietnamese's second words for one, four and five; `oh` is English's for zero.
SPOKEN_FORMS: Mapping[str, SpokenForms] = {
    "vi": SpokenForms(
        digits=(
            "không",
            "một",
            "mốt",
            "hai",
            "ba",
            "bốn",
            "tư",
            "năm",
            "lăm",
            "sáu",
            "bảy",
            "tám",
            "chín",
        ),
        zero="không",
        at="a còng",
        dot="chấm",
    ),
    "en": SpokenForms(
        digits=(
            "zero",
            "oh",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        ),
        zero="zero",
        at="at",
        dot="dot",
    ),
}

# Keyed by the same names, and one test asserts the two key sets are equal: two tables under one
# name is how a language arrives in one and not the other, and the second lookup is the one that
# raises after the first has already succeeded.
PHONE_PLANS: Mapping[str, PhonePlan] = {
    "vi": PhonePlan(prefix="0", written_digits=(10, 11), spoken_words=(9, 10)),
    "en": PhonePlan(prefix="0", written_digits=(10, 11), spoken_words=(9, 10)),
}


def written_down[Pack](table: Mapping[str, Pack], what: str, language: str) -> Pack:
    """One row of a language table, or a `ConfigError` naming the languages there are.

    A language nobody has written down is refused rather than falling back to any particular one:
    silently scanning a Spanish corpus with Vietnamese digit words finds nothing, and finding
    nothing is the one failure layer one cannot tell from a clean corpus.
    """
    if language not in table:
        known = ", ".join(sorted(table))
        raise ConfigError(f"no {what} for language {language!r}; written down: {known}")
    return table[language]


def spoken_forms(language: str) -> SpokenForms:
    """How that language dictates a digit, an `@` and a `.`."""
    return written_down(SPOKEN_FORMS, "spoken forms", language)


def phone_plan(language: str) -> PhonePlan:
    """That language's numbering plan: what a number opens with and how long it runs."""
    return written_down(PHONE_PLANS, "a phone plan", language)


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


def spaced(phrase: str) -> str:
    """One dictated phrase as a pattern: its words in order, any whitespace between them.

    `a còng` has to match `a  còng` and a newline between them, so a declared phrase is joined on
    ``\\s+`` rather
    than written in verbatim. Nothing is escaped because nothing needs to be -- `declared_words`
    refuses a token that is not alphanumeric, which is also what keeps a declaration out of the
    pattern's syntax and keeps the tone-stripped twin derivable.
    """
    return r"\s+".join(phrase.split())


def declaration(manifest: Manifest, *path: str) -> Any:
    """One value the manifest declares, or a `ConfigError` naming the path and what is there.

    Duplicated in `tool_decision/utils.py` on purpose, and the note is here as well as there because
    whichever module a reader lands in first is the one that has to explain it: § *Package layout*
    says the two axes share `name`, `version`, `Part` and one separator *and nothing else*, so a
    shared reader would be a fifth, and the first key one axis needed and the other did not would put
    a profile's vocabulary in a module the modality imports.
    """
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


def declared_name(manifest: Manifest, *path: str) -> str:
    """One declared non-empty string, or a `ConfigError` naming the path and what it holds.

    A declaration is read once, at composition, so this is where a wrong *type* can still be a
    `ConfigError` (Requirement 43). Coercing with `str()` is what it replaced: a list declared where
    a name belongs becomes `"['a']"`, which is a model nobody has and an error a hundred records
    later.
    """
    value = declaration(manifest, *path)
    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"config/modalities/{manifest.name}.yaml declares {'.'.join(path)} as "
            f"{value!r}, which is not a name"
        )
    return value


def declared_roles(manifest: Manifest, *path: str) -> frozenset[str]:
    """The roles a declaration names, or a `ConfigError` for anything that is not a list of them.

    `exclude_roles: system` -- a bare string where a list belongs -- is the slip this exists for.
    `frozenset("system")` is five letters, so no role matches, the instruction turn goes into the
    vector anyway, and nothing anywhere says a word: the run succeeds and every vector is wrong.
    Wrong vectors are invisible and a refused run is not, which is why this raises rather than
    reading a lone string as a one-role list.
    """
    value = declaration(manifest, *path)
    if not isinstance(value, list) or any(not isinstance(role, str) for role in value):
        raise ConfigError(
            f"config/modalities/{manifest.name}.yaml declares {'.'.join(path)} as "
            f"{value!r}, which is not a list of role names"
        )
    return frozenset(value)


def embedding_model(manifest: Manifest) -> str:
    """Which static model this modality's vectors come from.

    Read here rather than at the edge because the implementation that needs a key is the one that
    knows what it means (`manifest.py`), and loaded there rather than here because loading it opens
    a file (I1). `edge/bootstrap.py` calls this, builds the `Encoder`, and hands it over.
    """
    return declared_name(manifest, EMBEDDING, MODEL)


def personal_data_detectors(manifest: Manifest) -> tuple[Detector, ...]:
    """The six shapes layer one scans for, filled with the words the declared language dictates.

    **The shapes are here and the language is a parameter, and the split is the point.** A regular
    expression is tested, and these six are tested against the adversarial fixtures § *Testing
    Strategy* item 6 asks for -- so the shape of a dictated phone number (the word for the trunk
    prefix, then eight or nine more digit words) stays in code where a test can hold it. The words
    were Vietnamese literals in this module until it was pointed out that a modality claiming to
    provide "the common processing framework for a task family" cannot also decide the family's
    language: an English `text2text` corpus registered this and got `không|một|mốt|...`.

    The manifest declares one word -- which language -- and `spoken_forms` is the table. A block of
    declared vocabulary was the other build and it is worse: the words for the digits do not vary
    between two Vietnamese corpora, so declaring them per corpus adds sixty lines of reader,
    validation and fixture for a fact nobody should be able to get wrong.

    The identifier and phone shapes overlap on purpose: a phone number matches both, layer one is
    tuned for recall, and layer two is what decides which class it was.
    """
    language = declared_name(manifest, LANGUAGE)
    spoken = spoken_forms(language)
    plan = phone_plan(language)
    digits = "|".join(spaced(word) for word in spoken.digits)
    least = IDENTIFIER_DIGITS - 1
    written = plan.written_digits
    dictated = plan.spoken_words
    return (
        a_detector(
            "phone_digits",
            "PHONE",
            rf"\b{plan.prefix}\d(?:[\s.-]?\d){{{written[0] - 2},{written[1] - 2}}}\b",
        ),
        a_detector(
            "phone_spoken",
            "PHONE",
            rf"{spaced(spoken.zero)}(?:[\s.,]+(?:{digits}))"
            rf"{{{dictated[0] - 1},{dictated[1] - 1}}}",
        ),
        a_detector(
            "customer_id_digits", "CUSTOMER_ID", rf"\d(?:[\s.-]?\d){{{least},}}"
        ),
        a_detector(
            "customer_id_spoken",
            "CUSTOMER_ID",
            rf"(?:{digits})(?:[\s.,]+(?:{digits})){{{least},}}",
        ),
        a_detector("email_written", "EMAIL", EMAIL),
        a_detector(
            "email_spoken",
            "EMAIL",
            rf"[\w.+-]+\s+{spaced(spoken.at)}\s+[\w.\s-]+?\s+{spaced(spoken.dot)}\s+\w+",
        ),
    )


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
    profile's vocabulary in a module the modality imports. What that costs is copies that can
    drift, and I24 is what pays it rather than the seam.
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
        return "".join(
            block[TEXT]
            if isinstance(block, Mapping) and isinstance(block.get(TEXT), str)
            else canonical_json(block)
            for block in content
        )
    return canonical_json(content)


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

    **Layer one's language is a declaration too**, for the same reason and found later: the shapes
    it scans for are this module's and the words they are filled with are the corpus's, so
    `personal_data_detectors` is built once here rather than being a module constant.
    """

    def __init__(self, manifest: Manifest, encode: Encoder) -> None:
        self.name = manifest.name
        self.version = manifest.version
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
        move the check to (§8).
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
