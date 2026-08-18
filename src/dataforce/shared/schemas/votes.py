"""`votes.jsonl` -- what each juror answered, and how much they agreed.

The `jury` block keeps every vote including abstentions, because an abstention
carrying the library's own `error` and `raw` is evidence about the juror. Nothing
in this artifact may reach an annotator.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa


def _is_jury_block(value: Any) -> bool:
    return isinstance(value, dict) and all(
        key in value for key in ("votes", "cohesion", "exact_unanimity")
    )


SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "jury": pa.Column(object, pa.Check(_is_jury_block, element_wise=True)),
    },
    name="votes",
)
