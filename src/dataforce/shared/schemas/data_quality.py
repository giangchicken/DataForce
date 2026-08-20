"""The four `data_quality` artifacts: loaded · usable · pii_findings · deduped.

Stages 0-4 import this module and no other, so a change to the release schema
cannot put `load.py` in its blast radius. Schemas are in stage order.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa

from dataforce.shared.schemas.base import record_columns

# `loaded.jsonl` -- every source record as a canonical record, nothing judged yet.
# Unparsable records are here too, carrying `parse_status = "unparsed"`, because
# ingest drops nothing.
LOADED = pa.DataFrameSchema(record_columns(), name="loaded")


# `usable.jsonl` -- what survived the validity checks, and so what the run costs. A row
# here has an empty `invalid` list by construction: a record that failed a check went to
# `quarantine/invalid/<check>.jsonl` instead.
def _passed_every_check(value: Any) -> bool:
    return isinstance(value, list) and not value


def _usable() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["invalid"] = pa.Column(
        object, pa.Check(_passed_every_check, element_wise=True)
    )
    return pa.DataFrameSchema(columns, name="usable")


USABLE = _usable()


# `pii_findings.jsonl` -- one row per candidate span, always written. This is the artifact
# a person reads before deciding anything, so it exists whether or not `enable_redact` is
# on.
def _is_verdict(value: Any) -> bool:
    """True, False, or unverified. A verification response that failed its schema
    leaves a span unverified, which is not the same as negative. Read back from JSONL
    these are Python objects, not a pandas boolean dtype, so the column is checked
    rather than typed."""
    return value is None or isinstance(value, bool)


PII_FINDINGS = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "part": pa.Column(int),
        "type": pa.Column(str),
        "locator": pa.Column(object),
        "window": pa.Column(str),
        "verified": pa.Column(
            object, pa.Check(_is_verdict, element_wise=True), nullable=True
        ),
    },
    name="pii_findings",
)


# `deduped.jsonl` -- grouped, not thinned. Near-duplicate cluster members are all still
# here: one is marked `is_representative` and deletion happens at export from an explicit
# filter, so the decision is reversible and recorded. `group_key` is what keeps variants
# of one scenario from straddling a split.
def _deduped() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["dup_cluster_id"] = pa.Column(str)
    columns["is_representative"] = pa.Column(bool)
    columns["group_key"] = pa.Column(str)
    return pa.DataFrameSchema(columns, name="deduped")


DEDUPED = _deduped()
