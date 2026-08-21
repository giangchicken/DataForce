"""The two `ai_review` artifacts: votes · queue.

Stages 5-6 import this module and no other. Nothing in either artifact may reach
an annotator: both carry what a model produced.
"""

from __future__ import annotations

from typing import Any

import pandera.pandas as pa


# `votes.jsonl` -- what each juror answered, and how much they agreed. The `jury` block
# keeps every vote including abstentions, because an abstention carrying the library's
# own `error` and `raw` is evidence about the juror.
def _is_jury_block(value: Any) -> bool:
    return isinstance(value, dict) and all(
        key in value for key in ("votes", "cohesion", "exact_unanimity")
    )


VOTES = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "jury": pa.Column(object, pa.Check(_is_jury_block, element_wise=True)),
    },
    name="votes",
)


# `queue.jsonl` -- which records a human should look at, and why. `strata` is a list
# because one record can be selected by more than one stratum, and which stratum selected
# it is what makes the sampling design reconstructible. The selection probability lands
# with the stage that computes the quotas.
def _is_triage_block(value: Any) -> bool:
    return isinstance(value, dict) and "bucket" in value and "strata" in value


QUEUE = pa.DataFrameSchema(
    {
        "rid": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{16}$")),
        "triage": pa.Column(object, pa.Check(_is_triage_block, element_wise=True)),
    },
    name="queue",
)
