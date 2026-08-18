"""`published.jsonl` -- what was pushed to the annotation tool, joined on `rid`.

Publishing is idempotent on `rid`, so this is also the record of what not to push
again. The payload's key set is checked against an explicit allowlist by the
publish stage rather than here: the claim is about keys absent, and a schema
speaks about keys present.
"""

from __future__ import annotations

import pandera.pandas as pa

SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "task_id": pa.Column(int),
        "project_id": pa.Column(int),
    },
    name="published",
)
