"""One pandera schema per artifact, resolved by the artifact's name.

Stages look their own schema up here rather than importing a module path, so the
round-trip test can iterate every artifact the pipeline claims to produce and no
artifact can quietly ship without one.
"""

from __future__ import annotations

import pandera.pandas as pa

from dataforce.shared.schemas import (
    aggregated,
    curated,
    deduped,
    loaded,
    pii_findings,
    published,
    questions,
    queue,
    responses,
    split,
    usable,
    votes,
)

__all__ = ["ARTIFACT_SCHEMAS", "schema_for"]

ARTIFACT_SCHEMAS: dict[str, pa.DataFrameSchema] = {
    "loaded": loaded.SCHEMA,
    "usable": usable.SCHEMA,
    "pii_findings": pii_findings.SCHEMA,
    "deduped": deduped.SCHEMA,
    "votes": votes.SCHEMA,
    "queue": queue.SCHEMA,
    "questions": questions.SCHEMA,
    "published": published.SCHEMA,
    "responses": responses.SCHEMA,
    "aggregated": aggregated.SCHEMA,
    "curated": curated.SCHEMA,
    "split": split.SCHEMA,
}


def schema_for(artifact: str) -> pa.DataFrameSchema:
    """The schema for one artifact, by name, with the known names on failure."""
    try:
        return ARTIFACT_SCHEMAS[artifact]
    except KeyError:
        known = ", ".join(sorted(ARTIFACT_SCHEMAS))
        raise KeyError(f"no schema for artifact {artifact!r}; known: {known}") from None
