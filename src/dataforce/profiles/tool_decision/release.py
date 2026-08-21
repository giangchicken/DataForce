"""STEP · release (stages 12-14) · what one scenario is, and what one example is.

Stage 12 splits on scenario so no scenario straddles a split, and stage 13 exports one
training example per record. Stage 14 documents the release and asks a profile for
nothing. Two members, and the reason they are together is that they are the last two
questions anything asks of this profile: what may not be separated, and what ships.

Before this layout they were in two modules named for other phases -- `scenario_hash`
in the one that built records and `training_example` in the one that compared them --
which is the clearest case the module-layout spec makes.
"""

from __future__ import annotations

import json
from typing import Any

from dataforce.core.errors import InvariantError
from dataforce.core.record import Record, TextPart
from dataforce.profiles.tool_decision.schema import SourceContract
from dataforce.profiles.tool_decision.utils import catalog_hash, catalog_names

__all__ = ["scenario_hash", "training_example"]


def scenario_hash(record: Record, contract: SourceContract) -> str:
    """This profile's answer to *same scenario*: the hash of the record's catalog.

    Never `source_index`, which is unique per record and measured to be so. The generic
    name is `scenario_hash` because a profile without a catalog still has to answer the
    question; `catalog_hash` is what answering it means here.

    Reads the catalog rather than a stored copy of its names, and asserting this stays
    byte-identical over the whole reference source is what proves requirement 71
    removed a field without moving any behaviour.
    """
    return catalog_hash(catalog_names(record, contract))


def training_example(record: Record) -> dict[str, Any]:
    """The record as a training example. Invariant 4 is asserted here, not downstream.

    SFT JSONL: the same `messages` list, with the label the record ended up with in both
    the assistant message and `meta.label`. Asserted equal on the way out, because that
    assertion is the one that counted 48 disagreeing records before the source was fixed.
    """
    label = record.label or []
    assistant = json.dumps(label, ensure_ascii=False)
    messages = [
        {
            "role": part.role,
            "content": assistant if part.role == "assistant" else part.text,
        }
        for part in record.content
        if isinstance(part, TextPart)
    ]
    meta = {**record.meta, "label": label}
    if json.loads(assistant) != meta["label"]:
        raise InvariantError(
            f"record {record.rid}: the assistant message and meta.label disagree "
            f"on export -- {assistant} against {meta['label']!r}"
        )
    return {"messages": messages, "meta": meta}
