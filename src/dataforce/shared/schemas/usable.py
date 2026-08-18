"""`usable.jsonl` -- what survived the validity checks, and so what the run costs.

A row here has an empty `invalid` list by construction: a record that failed a
check went to `quarantine/invalid/<check>.jsonl` instead.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns


def _passed_every_check(value: Any) -> bool:
    return isinstance(value, list) and not value


def _schema() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["invalid"] = pa.Column(
        object, pa.Check(_passed_every_check, element_wise=True)
    )
    return pa.DataFrameSchema(columns, name="usable")


SCHEMA = _schema()
