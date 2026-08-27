"""T27 · the artifacts: what a run leaves behind, and the manifest that says what produced it.

`edge/artifacts.py` is the one place a record file, `metrics.json` or a run manifest is read or
written. Three things are worth stating here:

**I14 — two runs of one unchanged configuration produce byte-identical run manifests, apart from the
`run_id` naming them.** That is what makes a policy digest evidence rather than decoration: if the
manifest moved for reasons of its own — a dict that iterates in insertion order, a float that formats
differently — a changed threshold would be one more diff among several and nobody could point at it.
The exception is why the id is an *argument* below rather than something `run_manifest` mints: a
clock is the one thing in a manifest that has to move, so it moves in a place a test can hold still.
The invariant's own row carries the same clause, because a sentence no run can satisfy is one nobody
can check.

**The fold is for reading and stops nothing** (Requirement 44). `label_check`'s counts are compared
against `params.invalid_counts` here, which is where Decision 10 put that comparison when it deleted
the gates: a declared count that moved is a line in a diff, not a crash.

**A run id says when it started and what it was configured with.** Deterministic in its second half,
so two runs that read the same files are visibly the same configuration, and a clock in front of it
so they are still two runs.

Every fixture is invented (AGENTS.md §9).
"""

import re
from pathlib import Path

import pytest
from agent_toolkit.file_utils import read_json
from agent_toolkit.string_utils import compute_hash

from dataforce.edge.artifacts import (
    MANIFEST,
    METRICS,
    RECORDS,
    corpus_counts,
    minted_run_id,
    read_records,
    run_manifest,
    written_run,
)
from dataforce.edge.bootstrap import open_engine
from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.record import DataQuality, LabelVerdict, Record

from ..stages.test_tool_decision import a_record
from .test_policy import PARAMS, a_config, a_params

RUN = "r_2026-08-26T09:15:00Z_1f3c"

DECLARING_COUNTS = (
    PARAMS
    + """\
invalid_counts:
  label_not_in_catalog: 1
  empty_catalog:
"""
)


def an_engine(root: Path, params: str = PARAMS) -> Engine:
    """One run's engine, composed the way a shell composes it."""
    return open_engine(
        profile="tool_decision",
        config_root=a_config(root),
        params=a_params(root, params),
    )


def checked(*failed: str) -> Record:
    """One record `label_check` has written on, failing the checks named."""
    return a_record(
        data_quality=DataQuality(
            label_check=LabelVerdict(
                passed=not failed, failed_checks=failed, quarantined=bool(failed)
            )
        )
    )


# --- the run manifest ---


def test_two_runs_of_one_unchanged_configuration_write_one_manifest(
    tmp_path: Path,
) -> None:
    """I14, in bytes. The run id is an input, because a run's identity is the one thing that moves."""
    records = (a_record(),)

    first = written_run(tmp_path / "one", an_engine(tmp_path / "a"), RUN, records)
    second = written_run(tmp_path / "two", an_engine(tmp_path / "b"), RUN, records)

    assert first == second
    assert (tmp_path / "one" / MANIFEST).read_bytes() == (
        tmp_path / "two" / MANIFEST
    ).read_bytes()


def test_a_changed_policy_file_changes_the_manifest(tmp_path: Path) -> None:
    """Requirement 45's other half: an unchanged manifest has to mean an unchanged configuration."""
    retuned = PARAMS.replace("overlap_floor: 1", "overlap_floor: 2", 1)

    before = run_manifest(an_engine(tmp_path / "a"), RUN, {})
    after = run_manifest(an_engine(tmp_path / "b", retuned), RUN, {})

    assert before["policy"] != after["policy"]


def test_the_manifest_names_both_axis_versions(tmp_path: Path) -> None:
    """Requirement 45, and in the same `name@version` spelling every record's provenance carries."""
    manifest = run_manifest(an_engine(tmp_path), RUN, {})

    assert manifest["producer"] == {
        "modality": "text2text@1",
        "profile": "tool_decision@1",
    }


def test_the_manifest_records_the_digest_of_every_artifact_it_wrote(
    tmp_path: Path,
) -> None:
    """One function writes all of them, so *every* is structural rather than remembered."""
    manifest = written_run(tmp_path / "run", an_engine(tmp_path), RUN, (a_record(),))

    assert sorted(manifest["artifacts"]) == [METRICS, RECORDS]
    assert all(len(digest) == 64 for digest in manifest["artifacts"].values())


def test_the_artifact_digest_is_the_digest_of_the_file_on_disk(tmp_path: Path) -> None:
    """Read back rather than computed on the way past: a digest of what we meant to write says
    nothing about what a later reader will find."""
    manifest = written_run(tmp_path / "run", an_engine(tmp_path), RUN, (a_record(),))

    written = (tmp_path / "run" / RECORDS).read_text(encoding="utf-8")

    assert manifest["artifacts"][RECORDS] == compute_hash(written)


# --- the record file ---


def test_the_records_written_come_back_the_records_that_went_in(tmp_path: Path) -> None:
    """The round trip both shells stand on: JSONL out of one run is JSONL into the next."""
    records = (a_record(), checked("label_not_in_catalog"))

    written_run(tmp_path / "run", an_engine(tmp_path), RUN, records)

    assert read_records(tmp_path / "run" / RECORDS) == records


def test_a_file_of_something_else_is_a_config_error(tmp_path: Path) -> None:
    """Requirement 43: the only exception, and it carries the path pydantic's would not."""
    (tmp_path / "wrong.jsonl").write_text('{"a": 1}\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="wrong.jsonl"):
        read_records(tmp_path / "wrong.jsonl")


def test_a_record_file_that_is_not_there_says_so(tmp_path: Path) -> None:
    """`read_jsonlines` answers `[]` for a file it cannot read, which reads as an empty corpus."""
    with pytest.raises(ConfigError, match="missing.jsonl"):
        read_records(tmp_path / "missing.jsonl")


# --- the fold ---


def test_the_fold_counts_the_records_and_what_each_stage_wrote(tmp_path: Path) -> None:
    """Requirement 44: corpus-level numbers are a fold at the edge, over the records themselves."""
    counts = corpus_counts(
        an_engine(tmp_path), (a_record(), checked(), checked("empty_catalog"))
    )

    assert counts["records"] == 3
    assert counts["stages"]["label_check"] == 2
    assert counts["stages"]["curate"] == 0


def test_the_fold_names_no_stage_that_has_no_module(tmp_path: Path) -> None:
    """`release` is declared in the flow and built nowhere; a zero beside it would read as a run."""
    counts = corpus_counts(an_engine(tmp_path), ())

    assert "export" not in counts["stages"]
    assert "load_data" not in counts["stages"]


def test_a_declared_count_that_moved_is_a_line_in_the_fold(tmp_path: Path) -> None:
    """Requirement 22 as Decision 10 left it: found beside declared, and nothing stops."""
    counts = corpus_counts(
        an_engine(tmp_path, DECLARING_COUNTS),
        (checked("label_not_in_catalog"), checked("label_not_in_catalog")),
    )

    assert counts["label_checks"]["label_not_in_catalog"] == {"found": 2, "declared": 1}


def test_a_check_nobody_declared_a_count_for_is_still_counted(tmp_path: Path) -> None:
    """`params.invalid_counts` ships empty until a corpus is declared, and a run still reports."""
    counts = corpus_counts(
        an_engine(tmp_path), (checked("label_names_one_tool_twice"),)
    )

    assert counts["label_checks"]["label_names_one_tool_twice"] == {
        "found": 1,
        "declared": None,
    }


def test_a_declared_check_nothing_failed_is_reported_as_zero(tmp_path: Path) -> None:
    """A check that stopped firing is the interesting case, and an absent key would hide it."""
    counts = corpus_counts(an_engine(tmp_path, DECLARING_COUNTS), (checked(),))

    assert counts["label_checks"]["label_not_in_catalog"]["found"] == 0


def test_the_fold_is_written_where_a_human_reads_it(tmp_path: Path) -> None:
    """`metrics.json`, beside the records it is a fold over."""
    written_run(tmp_path / "run", an_engine(tmp_path), RUN, (checked(),))

    assert (tmp_path / "run" / METRICS).is_file()


# --- the run id ---


def test_a_run_id_says_when_it_started_and_what_it_was_configured_with(
    tmp_path: Path,
) -> None:
    """The shape the record's own drawing states, and the join key to the manifest above."""
    minted = minted_run_id(an_engine(tmp_path).policy_digests)

    assert re.fullmatch(r"r_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z_[0-9a-f]{4}", minted)


def test_two_configurations_do_not_get_one_run_id(tmp_path: Path) -> None:
    """The suffix is what the run read, so a re-tuned threshold is visible in the id itself."""
    retuned = PARAMS.replace("overlap_floor: 1", "overlap_floor: 2", 1)

    first = minted_run_id(an_engine(tmp_path / "a").policy_digests)
    second = minted_run_id(an_engine(tmp_path / "b", retuned).policy_digests)

    assert first.split("_")[-1] != second.split("_")[-1]


def test_the_manifest_a_run_writes_is_the_manifest_it_returns(tmp_path: Path) -> None:
    """One value, written once: a response body and a file that could disagree is two manifests."""
    returned = written_run(tmp_path / "run", an_engine(tmp_path), RUN, ())

    assert returned["run_id"] == RUN
    assert read_json(tmp_path / "run" / MANIFEST) == returned
