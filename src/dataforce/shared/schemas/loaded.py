"""`loaded.jsonl` -- every source record as a canonical record, nothing judged yet.

Unparsable records are here too, carrying `parse_status = "unparsed"`, because
ingest drops nothing.
"""

from __future__ import annotations

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns

SCHEMA = pa.DataFrameSchema(record_columns(), name="loaded")
