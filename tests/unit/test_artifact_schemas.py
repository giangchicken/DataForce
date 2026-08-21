"""Every artifact the pipeline claims to produce has a schema, and it round-trips.

The claim worth checking is the one no single stage can make: that a file written
by `write_jsonlines` and read back by `read_jsonlines` still satisfies what its
artifact is supposed to be, media references included.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa
import pytest
from agent_toolkit.file_utils import read_jsonlines, write_jsonlines

from dataforce.shared.schemas import ARTIFACT_SCHEMAS, schema_for

RID = "0123456789abcdef"
TEXT_PART = {"type": "text", "role": "user", "text": "Book me a flight"}
AUDIO_PART = {
    "type": "audio",
    "role": "user",
    "uri": "media/ab/abc123.wav",
    "sha256": "abc123",
    "duration_s": 12.4,
}


def _record_row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "rid": RID,
        "source": {
            "file_sha256": "6f7d2a40",
            "offset": 1043,
            "ingested_at": "2026-08-18T00:00:00Z",
        },
        "producer": {"modality": "text@1", "profile": "tool_decision@1"},
        "content": [TEXT_PART],
        "meta": {"label": 1},
        "label": ["SendMail"],
        "answer_space": {"tools": ["SendMail"]},
        "parse_status": "ok",
        "failed_checks": [],
    }
    row.update(extra)
    return row


SAMPLES: dict[str, dict[str, Any]] = {
    "loaded": _record_row(failed_checks=["label_contradiction"]),
    "usable": _record_row(),
    "pii_findings": {
        "rid": RID,
        "part": 1,
        "type": "PHONE",
        "locator": {"start": 12, "end": 22},
        "window": "call me on <PHONE_1> tomorrow",
        "verified": None,
    },
    "deduped": _record_row(
        dup_cluster_id="c_0331",
        dup_cluster_size=112,
        is_representative=True,
        group_key="g_7a1e",
    ),
    "votes": {
        "rid": RID,
        "jury": {
            "votes": [{"juror": "j1", "family": "glm", "answer": ["SendMail"]}],
            "cohesion": 0.67,
            "exact_unanimity": False,
        },
    },
    "queue": {"rid": RID, "triage": {"bucket": "agreed", "strata": ["audit"]}},
    "questions": {
        "rid": RID,
        "question": "Does the assistant need SendMail here?",
        "focus": "tool_necessity",
        "prompt_version": "question.v1",
        "model": "glm-4.6",
    },
    "published": {"rid": RID, "task_id": 41, "project_id": 7},
    "responses": {
        "rid": RID,
        "annotator": "u12",
        "verdict": "incorrect",
        "correction": ["SendMail", "Search"],
        "flags": [],
    },
    "aggregated": {
        "rid": RID,
        "verdict": "incorrect",
        "confidence": 0.82,
        "validators": ["u12", "u07"],
        "correction": ["SendMail"],
    },
    "curated": _record_row(
        validation={
            "status": "corrected",
            "validators": ["u12", "u07"],
            "decided_at": "2026-08-18T00:00:00Z",
        }
    ),
    "split": _record_row(group_key="g_7a1e", split="test"),
}

CONTENT_ARTIFACTS = sorted(
    name for name, schema in ARTIFACT_SCHEMAS.items() if "content" in schema.columns
)


def test_every_artifact_has_a_sample_so_none_goes_unchecked() -> None:
    assert set(SAMPLES) == set(ARTIFACT_SCHEMAS)


@pytest.mark.parametrize("artifact", sorted(ARTIFACT_SCHEMAS))
def test_round_trip_through_the_toolkit_and_back(artifact: str, tmp_path: Path) -> None:
    path = tmp_path / f"{artifact}.jsonl"
    write_jsonlines(path, [SAMPLES[artifact]])
    rows = read_jsonlines(path)
    schema_for(artifact).validate(pd.DataFrame(rows))


@pytest.mark.parametrize("artifact", CONTENT_ARTIFACTS)
def test_an_audio_part_by_reference_passes_unchanged(artifact: str) -> None:
    """The seam: a non-text part changes nothing about the shape of an artifact."""
    row = dict(SAMPLES[artifact], content=[TEXT_PART, AUDIO_PART])
    schema_for(artifact).validate(pd.DataFrame([row]))


@pytest.mark.parametrize("artifact", CONTENT_ARTIFACTS)
def test_no_artifact_admits_a_media_part_without_a_reference(artifact: str) -> None:
    unreferenced = {"type": "audio", "role": "user", "uri": "media/ab/a.wav"}
    row = dict(SAMPLES[artifact], content=[unreferenced])
    with pytest.raises(pa.errors.SchemaError):
        schema_for(artifact).validate(pd.DataFrame([row]))


@pytest.mark.parametrize("artifact", CONTENT_ARTIFACTS)
def test_no_artifact_admits_an_inlined_blob(artifact: str) -> None:
    inlined = dict(AUDIO_PART, base64="UklGRgAAAABXQVZF")
    row = dict(SAMPLES[artifact], content=[inlined])
    with pytest.raises(pa.errors.SchemaError):
        schema_for(artifact).validate(pd.DataFrame([row]))


def test_usable_admits_no_record_that_failed_a_check() -> None:
    row = _record_row(failed_checks=["label_contradiction"])
    with pytest.raises(pa.errors.SchemaError):
        schema_for("usable").validate(pd.DataFrame([row]))


def test_an_unstamped_producer_is_rejected() -> None:
    row = _record_row(producer={"modality": "text", "profile": "tool_decision@1"})
    with pytest.raises(pa.errors.SchemaError):
        schema_for("loaded").validate(pd.DataFrame([row]))


def test_an_unknown_artifact_names_the_known_ones() -> None:
    with pytest.raises(KeyError, match="loaded"):
        schema_for("embeddings")
