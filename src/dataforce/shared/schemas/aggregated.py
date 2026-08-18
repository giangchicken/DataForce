"""`aggregated.jsonl` -- two annotators reduced to one verdict, with a confidence.

Verdicts are combined with Dawid-Skene rather than majority vote, so the
confidence reflects how reliable each annotator has been. Rows below the
confidence threshold go to adjudication rather than into the dataset.
"""

from __future__ import annotations

import pandera.pandas as pa

SCHEMA = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "verdict": pa.Column(str),
        "confidence": pa.Column(float, pa.Check.in_range(0.0, 1.0)),
        "validators": pa.Column(object),
        "correction": pa.Column(object, nullable=True),
    },
    name="aggregated",
)
