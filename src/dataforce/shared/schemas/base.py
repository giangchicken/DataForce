"""The columns every artifact shares, and the checks that hold on all of them.

Artifact schemas are a second line of defence, not the first: a record is built
through `Record`, which is pydantic, and written through `file_utils`. What
pandera adds is a claim about a whole file -- that every row of `deduped.jsonl`
still has a `uri` on its audio parts, whoever wrote it and however long ago.

Schemas are deliberately non-strict. A stage adds fields and removes none, so an
artifact validated here will carry columns a later stage put there.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pandera.pandas as pa

from dataforce.shared.record import MEDIA_TYPES

__all__ = ["VERSION_TAG", "content_is_by_reference", "record_columns"]

VERSION_TAG = r"^[a-z0-9_]+@[^@]+$"

# Keys that would mean a media part is carrying its own bytes. Artifacts stay
# streamable and diffable only while none of them appears.
_INLINE_PAYLOAD_KEYS = frozenset({"b64", "base64", "bytes", "data", "inline"})


def _part_is_by_reference(part: Any) -> bool:
    if not isinstance(part, dict):
        return False
    part_type = part.get("type")
    if part_type == "text":
        return isinstance(part.get("text"), str)
    if part_type in MEDIA_TYPES:
        if not (
            isinstance(part.get("uri"), str) and isinstance(part.get("sha256"), str)
        ):
            return False
        return not (_INLINE_PAYLOAD_KEYS & set(part))
    return False


def content_is_by_reference(content: Any) -> bool:
    """No part is untyped, no media part lacks `uri` and `sha256`, none is inlined."""
    if not isinstance(content, list) or not content:
        return False
    return all(_part_is_by_reference(part) for part in content)


def _has_keys(*required: str) -> Callable[[Any], bool]:
    def check(value: Any) -> bool:
        return isinstance(value, dict) and all(key in value for key in required)

    return check


def _producer_is_stamped(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        isinstance(value.get(axis), str)
        and re.match(VERSION_TAG, value[axis]) is not None
        for axis in ("modality", "profile")
    )


def record_columns() -> dict[str, pa.Column]:
    """The columns every artifact that carries records has, from `load` onward."""
    return {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "source": pa.Column(
            object,
            pa.Check(
                _has_keys("file_sha256", "offset", "ingested_at"), element_wise=True
            ),
        ),
        "producer": pa.Column(
            object, pa.Check(_producer_is_stamped, element_wise=True)
        ),
        "content": pa.Column(
            object, pa.Check(content_is_by_reference, element_wise=True)
        ),
        "meta": pa.Column(object, nullable=True),
        "label": pa.Column(object, nullable=True),
        "answer_space": pa.Column(object, nullable=True),
        "parse_status": pa.Column(str, pa.Check.isin(["ok", "unparsed"])),
        "failed_checks": pa.Column(
            object, pa.Check(lambda v: isinstance(v, list), element_wise=True)
        ),
    }
