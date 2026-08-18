"""`{train,val,test}.jsonl` -- one file per split, group-based and never random.

`group_key` is declared here because the split gate's only job is a set
intersection over it: a group wholly in one split, or the run stops.
"""

from __future__ import annotations

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns


def _schema() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["group_key"] = pa.Column(str)
    columns["split"] = pa.Column(str, pa.Check.isin(["train", "val", "test"]))
    return pa.DataFrameSchema(columns, name="split")


SCHEMA = _schema()
