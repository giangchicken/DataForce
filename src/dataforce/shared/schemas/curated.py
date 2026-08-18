"""`curated.jsonl` -- the accepted corrections applied, and who decided what.

Every record says how its label came to be, because "which records humans looked
at" is part of how the dataset was made and belongs in the datasheet.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns

VALIDATION_STATUSES = ("original", "corrected", "jury_consensus", "unvalidated")


def _is_validation_block(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not all(key in value for key in ("status", "validators", "decided_at")):
        return False
    return value["status"] in VALIDATION_STATUSES


def _schema() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["validation"] = pa.Column(
        object, pa.Check(_is_validation_block, element_wise=True)
    )
    return pa.DataFrameSchema(columns, name="curated")


SCHEMA = _schema()
