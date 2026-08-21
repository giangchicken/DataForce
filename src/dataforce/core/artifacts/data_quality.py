"""The four `data_quality` artifacts: loaded · usable · pii_findings · deduped.

Stages 0-4 import this module and no other, so a change to the release schema
cannot put `load.py` in its blast radius. Schemas are in stage order.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa

from dataforce.core.artifacts.base import record_columns

# `loaded.jsonl` -- every source record as a canonical record, nothing judged yet.
# Unparsable records are here too, carrying `parse_status = "unparsed"`, because
# ingest drops nothing.
LOADED = pa.DataFrameSchema(record_columns(), name="loaded")


# `usable.jsonl` -- what survived the validity checks, and so what the run costs. A row
# here has an empty `failed_checks` list by construction: a record that failed one went to
# `quarantine/invalid/<check>.jsonl` instead.
def _passed_every_check(value: Any) -> bool:
    return isinstance(value, list) and not value


def _usable() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["failed_checks"] = pa.Column(
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
# here; `export` drops all but one by a declared rule, so the decision is reversible and
# recorded. `scenario_hash` is what keeps variants of one scenario from straddling a
# split; `conversation_cluster` is what keeps near-identical text from straddling one.
#
# Exact duplicates need no column at all: `rid` is a hash over every part's
# `type:role:text`, so two records with identical content already share one. 21,171
# distinct rids over 21,172 records is that check, already run.
#
# The cluster's id and its size, never the list of its members: the membership exists
# once in `clusters.jsonl`, and on the largest cluster measured -- 112 records -- a
# member list on every row is 248,640 bytes against 2,240, and 112 copies of one fact.
# Size is here because it is the question a reader of one row has: of how many.
def _deduped() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["conversation_cluster"] = pa.Column(str)
    columns["conversation_cluster_size"] = pa.Column(int, pa.Check.ge(1))
    columns["scenario_hash"] = pa.Column(str)
    return pa.DataFrameSchema(columns, name="deduped")


DEDUPED = _deduped()
