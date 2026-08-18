"""`pii_findings.jsonl` -- one row per candidate span, always written.

This is the artifact a person reads before deciding anything, so it exists
whether or not `enable_redact` is on. `verified` is nullable because a
verification response that failed its schema leaves a span unverified, which is
not the same as negative.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa


def _is_verdict(value: Any) -> bool:
    """True, False, or unverified. Read back from JSONL these are Python objects,
    not a pandas boolean dtype, so the column is checked rather than typed."""
    return value is None or isinstance(value, bool)


SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "part": pa.Column(int),
        "type": pa.Column(str),
        "locator": pa.Column(object),
        "window": pa.Column(str),
        "verified": pa.Column(
            object, pa.Check(_is_verdict, element_wise=True), nullable=True
        ),
    },
    name="pii_findings",
)
