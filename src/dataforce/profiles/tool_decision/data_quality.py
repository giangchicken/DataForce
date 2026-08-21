"""STEP · data_quality (stages 0-4) · one raw item into one record, then the five checks.

Stage 0 builds the record; stage 1 asks the five questions that can be answered by
counting. They share a module because what stage 1 checks is exactly what stage 0
wrote, and because `validity_checks` serves stage 1 and nothing else. Stages 2-4 --
personal data, embedding, duplicates -- ask nothing of a profile, which is why this
module covers a five-stage phase in two sections.

The catalog is read through `utils`, whose format is defined once and round-trips
byte-identically over all 21,172 records. Which of the two shapes an item is in, which
turn is which, and where the answer is stated all come from the manifest, so nothing
here spells a field name belonging to one corpus.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from dataforce.core.errors import ConfigError
from dataforce.core.record import (
    Part,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
)
from dataforce.profiles.tool_decision.schema import SourceContract
from dataforce.profiles.tool_decision.utils import (
    answer_distance,
    calls_by_name,
    catalog_names,
)

__all__ = [
    "CHECK_NAMES",
    "PROVENANCE_KEY",
    "build_record",
    "validity_checks",
]


# Where the load stage puts the two things only it knows: which file this item came from
# and which implementations were resolved to read it. Required rather than defaulted, so
# a record without provenance cannot be constructed at all.
PROVENANCE_KEY = "__provenance__"

# The order the checks are reported in, and the keys `params.yaml` declares counts
# against.
CHECK_NAMES = (
    "label_assistant_mismatch",
    "label_not_in_catalog",
    "empty_catalog",
    "label_cardinality_anomaly",
    "label_names_one_tool_twice",
)


# --- stage 0: build the record -----------------------------------------------


def _provenance(raw: Mapping[str, Any]) -> tuple[Source, Producer]:
    """Where this item came from and what read it, both supplied by the stage."""
    try:
        given = raw[PROVENANCE_KEY]
        return Source(**given["source"]), Producer(**given["producer"])
    except KeyError as missing:
        raise ConfigError(
            f"a raw item reached build_record() without "
            f"{PROVENANCE_KEY}[{missing}]; the load "
            "stage supplies the source file's digest, this item's offset, the read time, "
            "and the modality and profile it resolved"
        ) from None


def build_record(
    raw: Mapping[str, Any], parts: list[Part], contract: SourceContract
) -> Record:
    """One canonical record, keeping every field this profile does not own.

    `meta` is the source's own `meta` plus whatever else the item carried, because what
    looks like noise now is what a later question turns out to need. The label is kept in
    source order: it means a set, and δ reads it as one, but rewriting it here would put
    `training_example`'s `meta.label` out of step with the assistant message that
    invariant 4 asserts it equals.
    """
    source, producer = _provenance(raw)
    # `tools` is carried through rather than consumed, and that is the whole of what
    # this profile stores about its answer space: the names and each name's
    # `parameters` are both already in it, so requirement 71's derived space needs no
    # field of its own. Under the legacy shape there is no such key and the catalog is
    # in the content instead, which `read_catalog` is the one place that knows.
    unowned = {
        key: value
        for key, value in raw.items()
        if key not in ("messages", "meta", PROVENANCE_KEY)
    }
    return Record(
        rid=compute_rid(parts),
        source=source,
        producer=producer,
        content=list(parts),
        label=contract.read_label(raw),
        meta={**unowned, **(raw.get("meta") or {})},
    )


# --- stage 1: the five validity checks ---------------------------------------
#
# Each returns True when its named failure holds, so the name reads as what is wrong with
# the record and `Record.failed_checks` is the list of names that fired. No person decides
# of them.
#
# The names are declared identifiers -- they appear in `params.yaml` and in the profile
# spec's table -- but the *fields* they read are not: which turn restates the answer and
# where the answer is stated both come from the source contract.
#
# Four of the five read 0 on the reference source, and that is a measurement rather than
# an omission: `empty_catalog` and `label_not_in_catalog` count records the catalog format
# resolves, and the 841 and 722 the profile spec quotes are what a stricter name pattern
# reports about names carrying a dot, hyphen, space or tab. The fifth,
# `label_names_one_tool_twice`, reads 10 -- measured, against an earlier claim in this
# comment that it read 0 because a set cannot repeat a name. A JSON array can, and ten do;
# `params.yaml` has carried the 10 since C2 and this text had not caught up. They stay as
# gates, the way `label_assistant_mismatch` stayed at 0 after it was fixed upstream: a
# check that reads 0 is what tells you when it stops reading 0.


def _restated_answer(record: Record, role: str) -> Any:
    """The label as the restating turn states it, or None if it does not."""
    text = next(
        (
            part.text
            for part in reversed(record.content)
            if isinstance(part, TextPart) and part.role == role
        ),
        None,
    )
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def validity_checks(
    contract: SourceContract, *, answer_ceiling: int
) -> dict[str, Callable[[Record], bool]]:
    """The five, bound to one source's vocabulary and one declared answer ceiling.

    The ceiling is the largest answer this source is declared to contain, and it is
    handed in rather than read -- so an undeclared threshold fails before a profile
    exists to check with, earlier than the first of 21,172 rows and without this
    module knowing what a file is. `declared/thresholds.py` reads it, off the
    `max_answer_cardinality` key that is its name on disk.
    """
    restating_role = contract.restating_role

    def label_assistant_mismatch(record: Record) -> bool:
        """The two statements of the target disagree.

        The restating turn *is* the training target, so a record where it and the label
        differ would train a model on the losing side of two disagreeing sources. Was 48
        records; upstream drove it to 0 and the gate expects 0.
        """
        stated = _restated_answer(record, restating_role)
        if stated is None:
            return True
        try:
            return answer_distance(stated, record.label) != 0.0
        except TypeError:
            return True

    def label_not_in_catalog(record: Record) -> bool:
        """The target calls a tool the record never offered -- unlearnable, and it
        teaches hallucination. Never truncated to the catalog: that would be a guess
        about which of two disagreeing sources is right, applied invisibly at scale.

        An entry that is neither a name nor a call fires too, so an answer of the wrong
        shape entirely belongs in quarantine where a person reads it, not in a
        `TypeError` that stops the run at record one.

        Only the names are checked here. Whether a call's *arguments* are in the space
        is a JSON Schema question, and `answer_schema_for` is what answers it at the
        two moments requirement 71 names -- neither of which is a counting check.
        """
        offered = set(catalog_names(record, contract))
        try:
            called = calls_by_name(record.label or [])
        except TypeError:
            return True
        return any(name not in offered for name in called)

    def empty_catalog(record: Record) -> bool:
        """The record offers no tools. A quarantine for triage, not a verdict."""
        return not catalog_names(record, contract)

    def label_cardinality_anomaly(record: Record) -> bool:
        """More tools in the answer than this source is declared to contain."""
        return len(record.label or []) > answer_ceiling

    def label_names_one_tool_twice(record: Record) -> bool:
        """Two calls to one tool, which makes the answer a multiset.

        Requirement 73 declares that out rather than teaching δ to match two calls to
        one tool pairwise before comparing their arguments -- a second decision δ would
        have to make silently. A person reads the record and decides whether the source
        means parallel calls or is malformed.

        An answer that cannot be read as calls at all is not this check's failure:
        `label_not_in_catalog` names that one, and firing both would report one defect
        under two names.
        """
        label = record.label or []
        try:
            called = calls_by_name(label)
        except TypeError:
            return False
        return len(called) != len(list(label))

    return {
        "label_assistant_mismatch": label_assistant_mismatch,
        "label_not_in_catalog": label_not_in_catalog,
        "empty_catalog": empty_catalog,
        "label_cardinality_anomaly": label_cardinality_anomaly,
        "label_names_one_tool_twice": label_names_one_tool_twice,
    }
