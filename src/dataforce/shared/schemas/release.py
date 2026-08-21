"""The one `release` artifact: split. Stages 12-14 import this module and no other.

`export` and `document` produce training files and a datasheet rather than a
records artifact, so neither has a schema here.
"""

from __future__ import annotations

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns


# `{train,val,test}.jsonl` -- one file per split, group-based and never random.
# `scenario_hash` is declared here because the split gate's only job is a set intersection
# over it: a group wholly in one split, or the run stops.
def _split() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["scenario_hash"] = pa.Column(str)
    columns["split"] = pa.Column(str, pa.Check.isin(["train", "val", "test"]))
    return pa.DataFrameSchema(columns, name="split")


SPLIT = _split()
