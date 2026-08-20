"""One raw source item, and the canonical record it becomes.

The catalog is read through `catalog`, whose format is defined once and round-trips
byte-identically over all 21,172 records. Which of the two shapes an item is in, which
turn is which, and where the answer is stated all come from the manifest, so nothing
here spells a field name belonging to one corpus.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_toolkit.string_utils import compute_hash

from dataforce.profiles.tool_decision import catalog as catalog_format
from dataforce.profiles.tool_decision.source import TOOLS_KEY, SourceContract
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
    "PROVENANCE_KEY",
    "adapt",
    "answer_space_for",
    "catalog_fingerprint",
    "catalog_names",
    "catalog_of",
]

# Where the load stage puts the two things only it knows: which file this item came from
# and which implementations were resolved to read it. Required rather than defaulted, so
# a record without provenance cannot be constructed at all.
PROVENANCE_KEY = "__provenance__"

# A catalog fingerprint, in hex characters. Long enough that two different catalogs
# colliding is not a thing that happens to 21,172 records.
_FINGERPRINT_LENGTH = 16


def catalog_of(
    raw: Mapping[str, Any], parts: Sequence[Part], contract: SourceContract
) -> catalog_format.Catalog:
    """This item's catalog, from wherever its shape keeps it.

    Under the canonical shape the tools are data and nothing is parsed. Under the legacy
    shape they were rendered into the instruction turn, so they are read back out of it.
    """
    if not contract.renders_the_catalog_into_the_prompt:
        return catalog_format.Catalog(
            tools=tuple(
                catalog_format.Tool(
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
    return catalog_format.parse(rendered)


def catalog_fingerprint(names: Sequence[str]) -> str:
    """What makes two records the same scenario: the tools they were offered.

    Order-sensitive, because the catalog is presented in order and two orderings are two
    prompts. `source_index` is not this: it is unique per record, measured, and so gives
    no leakage protection at all.
    """
    return compute_hash("|".join(names), "sha256")[:_FINGERPRINT_LENGTH]


def answer_space_for(catalog: catalog_format.Catalog) -> dict[str, Any]:
    """This record's answer space: an array of names drawn from its own catalog.

    The `enum` is requirement 5's catalog constraint, and the jury hands this straight to
    `complete_structured`, which is why no stage validates an answer against a catalog.
    """
    return {"type": "array", "items": {"type": "string", "enum": list(catalog.names)}}


def catalog_names(record: Record) -> list[str]:
    """The catalog a record was adapted with, read back off its answer space."""
    if record.answer_space is None:
        raise ConfigError(
            f"record {record.rid} carries no answer space; "
            "it was not adapted by the tool_decision profile"
        )
    names: list[str] = record.answer_space["items"]["enum"]
    return names


def _provenance(raw: Mapping[str, Any]) -> tuple[Source, Producer]:
    """Where this item came from and what read it, both supplied by the stage."""
    try:
        given = raw[PROVENANCE_KEY]
        return Source(**given["source"]), Producer(**given["producer"])
    except KeyError as missing:
        raise ConfigError(
            f"a raw item reached adapt() without {PROVENANCE_KEY}[{missing}]; the load "
            "stage supplies the source file's digest, this item's offset, the read time, "
            "and the modality and profile it resolved"
        ) from None


def adapt(
    raw: Mapping[str, Any], parts: list[Part], contract: SourceContract
) -> Record:
    """One canonical record, keeping every field this profile does not own.

    `meta` is the source's own `meta` plus whatever else the item carried, because what
    looks like noise now is what a later question turns out to need. The label is kept in
    source order: it means a set, and δ reads it as one, but rewriting it here would put
    export's `meta.label` out of step with the assistant message that invariant 4
    asserts it equals.
    """
    catalog = catalog_of(raw, parts, contract)
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
        answer_space=answer_space_for(catalog),
        label=contract.read_label(raw),
        meta={**unowned, **(raw.get("meta") or {})},
    )
