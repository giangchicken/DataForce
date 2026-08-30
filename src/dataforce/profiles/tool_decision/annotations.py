"""LOGIC · what one annotation said, decoded from the controls the capture half emitted.

**The only place an annotation tool's shape is read** (Requirement 49). The capture half emits three
controls and this answers for three: a verdict, a correction where the verdict says the label is
wrong, and free text. A caller reading one of them itself would be a second place that knew this
shape -- and the caller is a pipeline stage, which may not know it at all.

The control names are constants here and not in ``profile.py``, which reads four of them: they are
the annotation tool's vocabulary rather than the profile's, and ``annotation_response`` is the
member that assembles what these four functions decode.

**Malformed is never coerced** (Requirement 49). A control absent, a ``textarea`` that is a string,
arguments that are not JSON, a name outside the catalog -- every one of them is ``None``, because the
record has one place to put a correction and a half-parsed one is a value nobody typed. What a person
actually typed survives in the store either way; what the record carries is the conclusion.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.profiles.tool_decision.answers import (
    ARGUMENTS,
    NAME,
    answer_is_permitted,
)
from dataforce.record import Record, StoredAnswer

# One annotation's `result` list, by key (spec.md § *The annotation config, and what comes back*).
FROM_NAME = "from_name"
VALUE = "value"
CHOICES = "choices"
TEXT = "text"
VERDICT = "verdict"
# The two controls a correction arrives on, and the one a note does.
CORRECTED_NAMES = "corrected_names"
CORRECTED_ARGUMENTS = "corrected_arguments"
NOTE = "note"


def typed_arguments(written: Sequence[Any]) -> dict[str, Any] | None:
    """The arguments an annotator typed, keyed by tool name, or None if any of it is malformed.

    A `textarea` value is a list because `maxSubmissions` permits more than one, so every entry is
    read and later entries win. Malformed is never coerced (Requirement 49): a human's malformed
    answer is evidence about the question, and half-parsing it would put a value nobody typed into a
    shipped label.
    """
    keyed: dict[str, Any] = {}
    for entry in written:
        if not isinstance(entry, str):
            return None
        try:
            read = json.loads(entry)
        except json.JSONDecodeError:
            return None
        if not isinstance(read, Mapping):
            return None
        keyed.update(read)
    return keyed


def control_values(
    result: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """One annotation's controls, by the name the config gave each.

    By name and not by position, because a control the annotator never touched is absent from the
    list rather than present and empty -- there are no positions to read. An entry that is not a
    mapping, or whose `value` is not one, is not a control and is left out rather than raising: this
    is what a person's tool sent, and Requirement 43 gives it no channel to stop a run through.
    """
    return {
        str(entry[FROM_NAME]): value
        for entry in result
        if isinstance(entry, Mapping) and FROM_NAME in entry
        for value in [entry.get(VALUE)]
        if isinstance(value, Mapping)
    }


def corrected_answer(
    answered: Mapping[str, Mapping[str, Any]], record: Record, max_calls: int
) -> StoredAnswer | None:
    """The correction those controls carry, or None where it is not an answer this record permits.

    `None` for every way it can fail -- a control absent, a `textarea` that is a string, arguments
    that are not JSON, a name outside the catalog -- because the record has one place to put a
    correction and a half-parsed one is a value nobody typed (Requirement 49).
    """
    names = answered.get(CORRECTED_NAMES, {}).get(CHOICES)
    written = answered.get(CORRECTED_ARGUMENTS, {}).get(TEXT, [])
    if not isinstance(names, list) or not isinstance(written, list):
        return None
    arguments = typed_arguments(written)
    if arguments is None:
        return None
    answer = tuple(
        {NAME: str(name), ARGUMENTS: arguments.get(str(name)) or {}} for name in names
    )
    return answer if answer_is_permitted(record, answer, max_calls) else None


def one_written_line(written: Any) -> str | None:
    """The one thing a `textarea` holds, or None where it holds nothing.

    A `textarea` value is a list because `maxSubmissions` permits more than one; a note is one
    piece of free text, so the first entry is it. Never parsed and never joined -- what a person
    typed reaches the record as what they typed.
    """
    if not isinstance(written, list) or not written:
        return None
    return str(written[0])
