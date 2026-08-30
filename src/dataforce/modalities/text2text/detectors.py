"""LOGIC · the six shapes layer one scans for, filled with the words a declared language dictates.

**The shapes are here and the language is a parameter, and the split is the point.** A regular
expression is tested, and these six are tested against the adversarial fixtures § *Testing Strategy*
item 6 asks for -- so the shape of a dictated phone number stays in code where a test can hold it,
and which words fill it stays a declaration. They were Vietnamese literals until it was pointed out
that a modality claiming to provide "the common processing framework for a task family" cannot also
decide the family's language: an English ``text2text`` corpus registered this and got
``không|một|mốt|...``.

**Two tables, because only one of them is about a language.** ``SpokenPiiForms`` is what a language
says a digit, an ``@`` and a ``.`` with; ``PhonePlan`` is what a *country*'s numbers open with and
how long they run. The first leaves for ``agent_toolkit.string_utils`` when this repository's pin
moves past the commit that already holds it (T54) and the second stays. Each type's own docstring
says why.
"""

from collections.abc import Mapping
from typing import NamedTuple

from agent_toolkit.string_utils import normalize_text

from dataforce.declarations import declared_name
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text.schema import Detector

# The one key this module reads: the whole of what a corpus declares about layer one.
LANGUAGE = "language"

# `@` and `.` are written the same way in every language that writes an address at all, so the one
# shape that needs no language is a constant.
EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"

# Six digits is the shortest identifier this corpus's sample carries (`480215`). Not a language
# fact and not declared with the rest: raising it drops short ids out of layer one and lowering it
# makes every price a hit, and what re-measures it is layer one's recall over a declared corpus.
IDENTIFIER_DIGITS = 6


class SpokenPiiForms(NamedTuple):
    """The words one language says a digit, an `@` and a `.` with.

    **Every field is a fact about a language and none is a fact about a country or a corpus.** That
    is what makes this the half that leaves: `agent_toolkit.string_utils` holds this exact shape and
    these exact names on a branch already -- beside `normalize_text`, because the tone-stripped half
    of this scan is the same concern -- and the day this repository's pin moves past it, I6 fails on
    the `def spoken_pii_forms` below and the fix is one import and one deletion. `PhonePlan` beside
    it does *not* leave, and its own docstring says why.

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


# The language packs, under the names `agent_toolkit.string_utils` keeps them, so the migration is
# an import rather than a rename. `mốt`, `tư` and `lăm` are Vietnamese's second words for one, four
# and five; `oh` is English's for zero.
SPOKEN_PII_FORMS: Mapping[str, SpokenPiiForms] = {
    "vi": SpokenPiiForms(
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
    "en": SpokenPiiForms(
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


def spoken_pii_forms(language: str) -> SpokenPiiForms:
    """How that language dictates a digit, an `@` and a `.`."""
    return written_down(SPOKEN_PII_FORMS, "spoken PII forms", language)


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


def personal_data_detectors(manifest: Manifest) -> tuple[Detector, ...]:
    """The six shapes layer one scans for, filled with the words the declared language dictates.

    **The shapes are here and the language is a parameter, and the split is the point.** A regular
    expression is tested, and these six are tested against the adversarial fixtures § *Testing
    Strategy* item 6 asks for -- so the shape of a dictated phone number (the word for the trunk
    prefix, then eight or nine more digit words) stays in code where a test can hold it. The words
    were Vietnamese literals in this module until it was pointed out that a modality claiming to
    provide "the common processing framework for a task family" cannot also decide the family's
    language: an English `text2text` corpus registered this and got `không|một|mốt|...`.

    The manifest declares one word -- which language -- and `spoken_pii_forms` is the table. A block of
    declared vocabulary was the other build and it is worse: the words for the digits do not vary
    between two Vietnamese corpora, so declaring them per corpus adds sixty lines of reader,
    validation and fixture for a fact nobody should be able to get wrong.

    The identifier and phone shapes overlap on purpose: a phone number matches both, layer one is
    tuned for recall, and layer two is what decides which class it was.
    """
    language = declared_name(manifest, LANGUAGE)
    spoken = spoken_pii_forms(language)
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
