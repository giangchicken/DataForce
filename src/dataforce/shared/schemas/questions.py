"""`questions.jsonl` -- one focused, answerable question per queued record.

Keyed by `(rid, prompt_version, model)` so re-running the generator over a queue
it has already seen produces the same questions rather than new ones.
"""

from __future__ import annotations

import pandera.pandas as pa

SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "question": pa.Column(str),
        "focus": pa.Column(str),
        "prompt_version": pa.Column(str),
        "model": pa.Column(str),
    },
    name="questions",
)
