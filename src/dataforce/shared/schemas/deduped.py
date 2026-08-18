"""`deduped.jsonl` -- grouped, not thinned.

Near-duplicate cluster members are all still here: one is marked
`is_representative` and deletion happens at export from an explicit filter, so
the decision is reversible and recorded. `group_key` is what keeps variants of
one scenario from straddling a split.
"""

from __future__ import annotations

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns


def _schema() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["dup_cluster_id"] = pa.Column(str)
    columns["is_representative"] = pa.Column(bool)
    columns["group_key"] = pa.Column(str)
    return pa.DataFrameSchema(columns, name="deduped")


SCHEMA = _schema()
