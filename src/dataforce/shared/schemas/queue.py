"""`queue.jsonl` -- which records a human should look at, and why.

`strata` is a list because one record can be selected by more than one stratum,
and which stratum selected it is what makes the sampling design reconstructible.
The selection probability lands with the stage that computes the quotas.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa


def _is_triage_block(value: Any) -> bool:
    return isinstance(value, dict) and "bucket" in value and "strata" in value


SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "triage": pa.Column(object, pa.Check(_is_triage_block, element_wise=True)),
    },
    name="queue",
)
