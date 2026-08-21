"""One pandera schema per artifact, resolved by the artifact's name.

Stages look their own schema up here rather than importing a module path, so the
round-trip test can iterate every artifact the pipeline claims to produce and no
artifact can quietly ship without one.

The schemas themselves are one module per pipeline phase -- the boundary along
which artifacts change and along which stages import -- so a stage depends on its
own phase and not on the other three. `schema_for` is for the test that must
iterate all of them; a stage never calls it.
"""

from __future__ import annotations

import pandera.pandas as pa

from dataforce.core.artifacts import ai_review, data_quality, human_review, release

__all__ = ["ARTIFACT_SCHEMAS", "schema_for"]

ARTIFACT_SCHEMAS: dict[str, pa.DataFrameSchema] = {
    "loaded": data_quality.LOADED,
    "usable": data_quality.USABLE,
    "pii_findings": data_quality.PII_FINDINGS,
    "deduped": data_quality.DEDUPED,
    "votes": ai_review.VOTES,
    "queue": ai_review.QUEUE,
    "questions": human_review.QUESTIONS,
    "published": human_review.PUBLISHED,
    "responses": human_review.RESPONSES,
    "aggregated": human_review.AGGREGATED,
    "curated": human_review.CURATED,
    "split": release.SPLIT,
}


def schema_for(artifact: str) -> pa.DataFrameSchema:
    """The schema for one artifact, by name, with the known names on failure."""
    try:
        return ARTIFACT_SCHEMAS[artifact]
    except KeyError:
        known = ", ".join(sorted(ARTIFACT_SCHEMAS))
        raise KeyError(f"no schema for artifact {artifact!r}; known: {known}") from None
