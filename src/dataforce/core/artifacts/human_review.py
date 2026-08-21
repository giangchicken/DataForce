"""The five `human_review` artifacts: questions · published · responses · aggregated
· curated.

Stages 7-11 import this module and no other. It is the widest phase because the
publish → annotate → pull → aggregate → adjudicate loop is where the most
artifacts change shape.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa

from dataforce.core.artifacts.base import record_columns

VALIDATION_STATUSES = ("original", "corrected", "jury_consensus", "unvalidated")

# `questions.jsonl` -- one focused, answerable question per queued record. Keyed by
# `(rid, prompt_version, model)` so re-running the generator over a queue it has already
# seen produces the same questions rather than new ones.
QUESTIONS = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "question": pa.Column(str),
        "focus": pa.Column(str),
        "prompt_version": pa.Column(str),
        "model": pa.Column(str),
    },
    name="questions",
)

# `published.jsonl` -- what was pushed to the annotation tool, joined on `rid`.
# Publishing is idempotent on `rid`, so this is also the record of what not to push
# again. The payload's key set is checked against an explicit allowlist by the publish
# stage rather than here: the claim is about keys absent, and a schema speaks about keys
# present.
PUBLISHED = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "task_id": pa.Column(int),
        "project_id": pa.Column(int),
    },
    name="published",
)

# `responses.jsonl` -- one row per annotator per record, normalized. A response marked
# incorrect with no correction is rejected rather than repaired, so it never reaches this
# artifact; it returns to the queue with the reason.
RESPONSES = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "annotator": pa.Column(str),
        "verdict": pa.Column(str),
        "correction": pa.Column(object, nullable=True),
        "flags": pa.Column(object),
    },
    name="responses",
)

# `aggregated.jsonl` -- two annotators reduced to one verdict, with a confidence.
# Verdicts are combined with Dawid-Skene rather than majority vote, so the confidence
# reflects how reliable each annotator has been. Rows below the confidence threshold go
# to adjudication rather than into the dataset.
AGGREGATED = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "verdict": pa.Column(str),
        "confidence": pa.Column(float, pa.Check.in_range(0.0, 1.0)),
        "validators": pa.Column(object),
        "correction": pa.Column(object, nullable=True),
    },
    name="aggregated",
)


# `curated.jsonl` -- the accepted corrections applied, and who decided what. Every record
# says how its label came to be, because "which records humans looked at" is part of how
# the dataset was made and belongs in the datasheet.
def _is_validation_block(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not all(key in value for key in ("status", "validators", "decided_at")):
        return False
    return value["status"] in VALIDATION_STATUSES


def _curated() -> pa.DataFrameSchema:
    columns = record_columns()
    columns["validation"] = pa.Column(
        object, pa.Check(_is_validation_block, element_wise=True)
    )
    return pa.DataFrameSchema(columns, name="curated")


CURATED = _curated()
