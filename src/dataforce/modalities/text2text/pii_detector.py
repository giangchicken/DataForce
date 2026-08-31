"""LOGIC · layer one for the declared language: one library scan per class of personal data.

**The library owns the whole of layer one now, and this module is what picks the four and names
them.** ``phone_number_detection_by_rules``, ``email_detection_by_rules``,
``otp_detection_by_rules`` and ``name_detection_by_rules`` are each ``(text, language) -> list[str]``,
each finds the written form and the dictated one, and each pattern behind one carries the toned and
the tone-stripped spelling together (Requirement 18). So there are no patterns here, no second pass
over a normalisation, and nothing for I6 to find: what is left is which classes this modality
records a hit under and which language the scans are bound to.

**The shapes left because a modality may not decide its family's language.** They were written here,
filled with words a manifest declared -- a table of Vietnamese digit words, an ``a còng``, a
``chấm`` -- and a regular expression is a fact about how a language dictates a number rather than
about this task family. § *PII, in two layers* is the argument: a modality provides a task family's
*framework* and cannot also decide the family's language, and every consumer of the library shares
one fix to a rule's reach instead of each carrying its own. What is left of the declaration is one
word, and it is read here because the implementation that needs a key is the one that knows what it
means.

**Four classes, and an identifier is not one of them.** ``CUSTOMER_ID`` was a fifth, matching any run
of six or more digits: a bare ``480215`` is an order number as often as a customer code, so the class
flagged every invoice in the corpus and layer two paid for each one. The library's ``OTP`` scan is
the same shape with a cue word in front of it -- ``mã xác nhận 480215`` -- which is the trade § *PII,
in two layers* states and the pilot measures. Adding a fifth class is a rule added in
``agent-toolkit``, reviewable in a diff there.
"""

from collections.abc import Callable, Mapping
from typing import NamedTuple

from agent_toolkit.string_utils import (
    NAME_TITLES,
    OTP_CUES,
    SPOKEN_AT,
    SPOKEN_DIGITS,
    SPOKEN_DOT,
    email_detection_by_rules,
    name_detection_by_rules,
    otp_detection_by_rules,
    phone_number_detection_by_rules,
)

from dataforce.declarations import declared_name
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text.schema import Detector

# The one key this module reads: the whole of what a corpus declares about layer one.
LANGUAGE = "language"

# One library scan, as this modality reaches for it.
type Scan = Callable[[str, str], list[str]]


class LibraryScan(NamedTuple):
    """One class of personal data, the library scan that finds it, and the tables that scan reads."""

    personal_data_class: (
        str  # what a hit is recorded under, which picks the placeholder
    )
    scan: Scan  # the library's, `(text, language) -> list[str]`
    tables: tuple[
        Mapping[str, str], ...
    ]  # every vocabulary table this scan looks a language up in


# The tables are named per scan rather than counted because a language written into one and not
# another is how the second lookup raises after the first has already succeeded -- so the language a
# corpus may declare is the one every table behind all four scans has a row for.
SCANS: tuple[LibraryScan, ...] = (
    LibraryScan("PHONE", phone_number_detection_by_rules, (SPOKEN_DIGITS,)),
    LibraryScan("EMAIL", email_detection_by_rules, (SPOKEN_AT, SPOKEN_DOT)),
    LibraryScan("OTP", otp_detection_by_rules, (OTP_CUES, SPOKEN_DIGITS)),
    LibraryScan("NAME", name_detection_by_rules, (NAME_TITLES,)),
)


def languages_written_down() -> frozenset[str]:
    """Every language all four scans can be built for, read off the library's own tables.

    The intersection and not any one table: a scan whose cue words a language has and whose digit
    words it does not raises a `KeyError` from inside the library on the first record, which is a
    stack trace where a `ConfigError` naming the languages there are belongs. Derived rather than
    listed, so a language the library adds is offered here without an edit.
    """
    return frozenset[str].intersection(
        *(frozenset(table) for found in SCANS for table in found.tables)
    )


def a_detector(found: LibraryScan, language: str) -> Detector:
    """One class, and its scan with the declared language already bound.

    Bound here rather than passed through the stage, because `pii_check` is handed detectors and no
    manifest: reading a declaration is the implementation's job (I2), and a scan that still wanted
    its language would make the language a fact the stage had to carry without being allowed to know
    what it means.
    """
    return Detector(
        personal_data_class=found.personal_data_class,
        scan=lambda text: found.scan(text, language),
    )


def personal_data_detectors(manifest: Manifest) -> tuple[Detector, ...]:
    """The four classes layer one has, each scanning in the language the manifest declares.

    The manifest declares one word -- which language -- and the library holds the vocabulary. A
    block of declared words was the other build and it is worse: the words for the digits do not
    vary between two Vietnamese corpora, so declaring them per corpus adds sixty lines of reader,
    validation and fixture for a fact nobody should be able to get wrong.

    A language no table has written down is refused rather than falling back to any particular one:
    silently scanning a Spanish corpus with Vietnamese digit words finds nothing, and finding
    nothing is the one failure layer one cannot tell from a clean corpus.
    """
    language = declared_name(manifest, LANGUAGE)
    written_down = languages_written_down()
    if language not in written_down:
        known = ", ".join(sorted(written_down))
        raise ConfigError(
            f"no personal-data scans for language {language!r}; written down: {known}"
        )
    return tuple(a_detector(found, language) for found in SCANS)
