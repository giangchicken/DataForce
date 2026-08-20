"""One training example, in the shape the source already uses.

SFT JSONL: the same `messages` list, with the label the record ended up with in both
the assistant message and `meta.label`. Asserted equal on the way out, because that
assertion is the one that counted 48 disagreeing records before the source was fixed.
"""

from __future__ import annotations

import json
from typing import Any

from dataforce.shared.errors import InvariantError
from dataforce.shared.record import Record, TextPart

__all__ = ["export"]


def export(record: Record) -> dict[str, Any]:
    """The record as a training example. Invariant 4 is asserted here, not downstream."""
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
