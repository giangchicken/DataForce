"""LOGIC · the answer a record carries: the one that ships, the one its turns restate, the redacted one.

Three conversions over a record's label, and not one of them is a member of anything. ``final_label``
was a public method on ``ToolDecision`` for one commit, used no ``self``, and appeared in neither
§ *Profile*'s members nor the plan; I23 is the guard that says so now, and this is where such a
conversion belongs.

**Redacting the label and redacting the content are one decision applied twice** (Requirement 17),
which is why ``redacted_text`` is ``record.py``'s and not this module's. The stage owns the content
and knows nothing about what an answer is; the profile owns the label and knows nothing about the
content; and if the two applied their replacements in different orders they would manufacture the
very ``label_assistant_mismatch`` that requirement exists to prevent.

**The tool's name is never rewritten and everything else is** -- ``redact_label`` says why in full.
The short of it is that a name is the catalog's and not the customer's.
"""

import json
from collections.abc import Mapping
from typing import Any

from dataforce.profiles.tool_decision.answers import NAME
from dataforce.record import (
    SPOKEN_AND_STATED,
    FinalLabel,
    Record,
    StoredAnswer,
    redacted_text,
)


def final_label(record: Record) -> StoredAnswer:
    """The answer that ships: what `curate` decided, or the one the record arrived with.

    A conversion over a record, not a fifteenth member. It was a public method on `ToolDecision` for
    one commit, used no `self`, and appeared in neither § *Profile*'s members nor the plan -- the
    same guess T13 refused to make for `redact_label`, arrived at by accident instead of by argument.
    I23 is the guard that now says so.
    """
    curated: FinalLabel | None = record.human_review.curate
    if curated is None or curated.status == "unresolved":
        return record.label
    return curated.label


def redacted_arguments(value: Any, replacements: Mapping[str, str]) -> Any:
    """One argument value with every personal-data string inside it replaced, at any depth.

    An argument may itself be an object or an array -- the same reason δ compares them through
    canonical JSON -- so a scan that only looked at the top level would rewrite
    `{"ma_khach": "480215"}` and miss `{"khach": {"ma": "480215"}}`, which is the shape a tool with a
    nested parameter schema declares.
    """
    if isinstance(value, str):
        return redacted_text(value, replacements)
    if isinstance(value, Mapping):
        return {
            key: redacted_arguments(item, replacements) for key, item in value.items()
        }
    if isinstance(value, list):
        return [redacted_arguments(item, replacements) for item in value]
    return value


def redact_label(label: StoredAnswer, replacements: Mapping[str, str]) -> StoredAnswer:
    """The label with every value `pii_check` replaced in the content replaced too.

    Requirement 17, and the half of it that is this profile's: the stage owns the content and knows
    nothing about what an answer is, so the shape of the label is read here. Redacting one and not
    the other is worse than redacting neither -- it manufactures a `label_assistant_mismatch` on the
    next run, and `export` emits a training example whose input reads `<CUSTOMER_ID_1>` and whose
    target reads the original, teaching a model to produce an identifier absent from its input.

    **The tool's name is never rewritten and everything else is.** A name is the catalog's, not the
    customer's; rewriting one would invent a tool no record offers and fire `label_not_in_catalog` --
    the same class of defect this exists to prevent, one stage later. A bare-name entry is returned
    untouched for that reason, and a key this profile does not write is rewritten rather than trusted,
    because a value carrying personal data is personal data wherever the source put it.
    """
    return tuple(
        entry
        if isinstance(entry, str)
        else {
            key: value if key == NAME else redacted_arguments(value, replacements)
            for key, value in entry.items()
        }
        for entry in label
    )


def restated_answer(record: Record, role: str) -> StoredAnswer | None:
    """The answer as this record's own final turn states it, or None if it does not.

    The **final** part, and only that one. An earlier target-role turn is history -- a tool called
    before the customer supplied what was missing, and then called again on the result -- so
    comparing the label against the last one *of that role* reports a mismatch on every multi-turn
    record; a fixture caught exactly that. Where the conversation ends with the customer, the label
    answers that turn and nothing restates it, which is the declared shape's ordinary case. Prose is
    not a restatement either.

    **The calls are the segment after the last `record.SPOKEN_AND_STATED`**, because a turn that both
    speaks and acts is written down as both and this check went silent on exactly those turns until a
    review found it -- a `data_quality` check reading 0 on the common shape is worse than no check,
    since Requirement 22 compares its count against `params.invalid_counts` and a zero reads as
    health. The separator is the record's constant rather than a copy of the modality's, and a
    crossing test builds the turn through `text2text` and reads it here, so neither end can move
    alone. Splitting on it costs nothing where there is no separator: `rsplit` returns the whole
    text, which is what a calls-only turn carries.
    """
    if not record.content or record.content[-1].role != role:
        return None
    tail = (record.content[-1].text or "").rsplit(SPOKEN_AND_STATED, 1)[-1]
    try:
        stated = json.loads(tail)
    except json.JSONDecodeError:
        return None
    return tuple(stated) if isinstance(stated, list) else None
