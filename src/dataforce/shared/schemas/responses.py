"""`responses.jsonl` -- one row per annotator per record, normalized.

A response marked incorrect with no correction is rejected rather than repaired,
so it never reaches this artifact; it returns to the queue with the reason.
"""

from __future__ import annotations

import pandera.pandas as pa

SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "annotator": pa.Column(str),
        "verdict": pa.Column(str),
        "correction": pa.Column(object, nullable=True),
        "flags": pa.Column(object),
    },
    name="responses",
)
