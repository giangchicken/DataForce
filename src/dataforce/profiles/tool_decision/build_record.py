"""STEP · stages 0-1 · one raw source item into one canonical record, then checked.

Stage 0 builds the record; stage 1 asks the four questions that can be answered by
counting. They share a module because what stage 1 checks is exactly what stage 0
wrote, and because `validity_checks` serves stage 1 and nothing else.

The catalog is read through `tool_schema`, whose format is defined once and round-trips
byte-identically over all 21,172 records. Which of the two shapes an item is in, which
turn is which, and where the answer is stated all come from the manifest, so nothing
here spells a field name belonging to one corpus.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_yaml

from dataforce.profiles.tool_decision.answer import answer_distance, answer_space
from dataforce.profiles.tool_decision.source_contract import TOOLS_KEY, SourceContract
from dataforce.profiles.tool_decision.tool_schema import (
    Catalog,
    Tool,
    catalog_fingerprint,
    catalog_names,
    catalog_to_tools,
)
from dataforce.shared.errors import ConfigError
from dataforce.shared.record import (
    Part,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
)

__all__ = [
    "CHECK_NAMES",
    "PARAMS",
    "PROVENANCE_KEY",
    "build_record",
    "group_key",
    "max_answer_cardinality",
    "read_catalog",
    "validity_checks",
]

# Where the load stage puts the two things only it knows: which file this item came from
# and which implementations were resolved to read it. Required rather than defaulted, so
# a record without provenance cannot be constructed at all.
PROVENANCE_KEY = "__provenance__"

PARAMS = Path("params.yaml")

# The order the checks are reported in, and the keys `params.yaml` declares counts
# against.
CHECK_NAMES = (
    "label_assistant_mismatch",
    "label_not_in_catalog",
    "empty_catalog",
    "label_cardinality_anomaly",
)


# --- stage 0: build the record -----------------------------------------------


def read_catalog(
    raw: Mapping[str, Any], parts: Sequence[Part], contract: SourceContract
) -> Catalog:
    """This item's catalog, from wherever its shape keeps it.

    Under the canonical shape the tools are data and nothing is parsed. Under the legacy
    shape they were rendered into the instruction turn, so they are read back out of it.
    """
    if not contract.renders_the_catalog_into_the_prompt:
        return Catalog(
            tools=tuple(
                Tool(
                    name=entry["function"]["name"],
                    description=entry["function"].get("description", ""),
                    parameters=entry["function"].get("parameters", {}),
                )
                for entry in raw.get(TOOLS_KEY) or []
            )
        )
    instruction = contract.role_name("instruction")
    rendered = next(
        (
            part.text
            for part in parts
            if isinstance(part, TextPart) and part.role == instruction
        ),
        "",
    )
    return catalog_to_tools(rendered)


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
    catalog = read_catalog(raw, parts, contract)
    source, producer = _provenance(raw)
    # `tools` is kept rather than consumed: the answer space takes the names, and the
    # descriptions are what an annotator reads. Under the legacy shape there is no such
    # key and the catalog is already in the content.
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
        answer_space=answer_space(catalog),
        label=contract.read_label(raw),
        meta={**unowned, **(raw.get("meta") or {})},
    )


def group_key(record: Record) -> str:
    """The catalog fingerprint. Never `source_index`, which is unique per record."""
    return catalog_fingerprint(catalog_names(record))


# --- stage 1: the four validity checks ---------------------------------------
#
# Each returns True when its named failure holds, so the name reads as what is wrong with
# the record and `Record.invalid` is the list of names that fired. No person decides any
# of them.
#
# The names are declared identifiers -- they appear in `params.yaml` and in the profile
# spec's table -- but the *fields* they read are not: which turn restates the answer and
# where the answer is stated both come from the source contract.
#
# Two of the four read 0 on the current file, and that is a measurement rather than an
# omission: `empty_catalog` and `label_not_in_catalog` count records the catalog format
# resolves, and the 841 and 722 the profile spec quotes are what a stricter name pattern
# reports about names carrying a dot, hyphen, space or tab. They stay as gates, the way
# `label_assistant_mismatch` stayed at 0 after it was fixed upstream: a check that reads 0
# is what tells you when it stops reading 0.


def max_answer_cardinality(*, params: Path = PARAMS) -> int:
    """The largest answer this source is declared to contain."""
    declared = (read_yaml(params) or {}).get("max_answer_cardinality")
    if not isinstance(declared, int):
        raise ConfigError(
            f"{params}: max_answer_cardinality must be declared as an integer, got "
            f"{declared!r} -- thresholds are committed, not inferred"
        )
    return declared


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
    contract: SourceContract, *, params: Path = PARAMS
) -> dict[str, Callable[[Record], bool]]:
    """The four, bound to one source's vocabulary and one declared ceiling.

    The ceiling is read once here rather than once per record, so an undeclared threshold
    fails when a stage builds its checks and not on the first row of 21,172.
    """
    restating_role = contract.restating_role
    ceiling = max_answer_cardinality(params=params)

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
        """The target names a tool the record never offered -- unlearnable, and it
        teaches hallucination. Never truncated to the catalog: that would be a guess
        about which of two disagreeing sources is right, applied invisibly at scale."""
        offered = set(catalog_names(record))
        return any(name not in offered for name in record.label or [])

    def empty_catalog(record: Record) -> bool:
        """The record offers no tools. A quarantine for triage, not a verdict."""
        return not catalog_names(record)

    def label_cardinality_anomaly(record: Record) -> bool:
        """More tools in the answer than this source is declared to contain."""
        return len(record.label or []) > ceiling

    return {
        "label_assistant_mismatch": label_assistant_mismatch,
        "label_not_in_catalog": label_not_in_catalog,
        "empty_catalog": empty_catalog,
        "label_cardinality_anomaly": label_cardinality_anomaly,
    }
