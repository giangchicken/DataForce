"""`dataforce profile`, against the file it declares and against an older one.

The value of this command is entirely in the second half: measuring the corpus is
easy, and noticing that it changed is what nobody did for four weeks. So the drift
test points the profiler at the 2026-08-17 backup and asserts it names the count
that moved -- the same 48 that were found by accident.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tracemalloc
from pathlib import Path
from typing import Any

import pytest
from agent_toolkit.file_utils import read_yaml
from conftest import REPO_ROOT

from dataforce.modalities.text import TEXT
from dataforce.profiles.tool_decision import TOOL_DECISION, measure_corpus

pytestmark = pytest.mark.integration

BASELINE = REPO_ROOT / "metrics" / "corpus_profile.json"
BACKUP = REPO_ROOT / "data" / "raw" / "fc_train_final.json.bak_syncassist_20260817"

# What the profile spec's Context table says, and what this file actually holds.
DECLARED = {
    "records": 21172,
    "answer_cardinality": {"0": 7498, "1": 10596, "2": 2757, "3": 321},
    "distinct_tool_names": 14411,
    "most_frequent": ["check_past", 35],
    "relabelled_once": 1358,
    "relabelled_and_changed": 1346,
    "largest_catalog_group": 112,
    "gemma_share": 14241,
    "duplicate_user_turn_groups": 491,
    "duplicate_system_user_pairs": 1,
}


def source_path() -> Path:
    declared = read_yaml(REPO_ROOT / "params.yaml")["source"]["path"]
    path = REPO_ROOT / declared
    if not path.exists():
        pytest.skip(f"{declared} is not present; data/raw/ is deliberately untracked")
    return path


@pytest.fixture(scope="module")
def measured() -> dict[str, Any]:
    return measure_corpus.corpus_measurements(source_path(), TEXT, TOOL_DECISION)


def test_the_committed_baseline_matches_a_fresh_measurement(
    measured: dict[str, Any],
) -> None:
    """The one assertion that fails the day the source file changes."""
    if not BASELINE.exists():
        pytest.skip("no baseline committed yet; run `dataforce profile`")

    assert (
        measure_corpus.moved_measurements(
            json.loads(BASELINE.read_text(encoding="utf-8")), measured
        )
        == []
    )


def test_every_figure_is_stamped_with_the_digest_of_the_file_read(
    measured: dict[str, Any],
) -> None:
    declared = read_yaml(REPO_ROOT / "params.yaml")["source"]

    assert measured["source"]["sha256"] == declared["sha256"]
    assert measured["source"]["sha256"] == measure_corpus.source_digest(source_path())


def test_the_profiler_reproduces_the_counts_the_profile_spec_quotes(
    measured: dict[str, Any],
) -> None:
    assert measured["records"] == DECLARED["records"]
    assert measured["answer_cardinality"] == DECLARED["answer_cardinality"]
    assert measured["labels"]["distinct_tool_names"] == DECLARED["distinct_tool_names"]
    assert measured["labels"]["most_frequent"] == DECLARED["most_frequent"]
    assert measured["labels"]["relabelled_once"] == DECLARED["relabelled_once"]
    assert (
        measured["labels"]["relabelled_and_changed"]
        == DECLARED["relabelled_and_changed"]
    )
    assert (
        measured["catalog_fingerprints"]["largest"]["records"]
        == DECLARED["largest_catalog_group"]
    )
    assert measured["labelling_model"]["gemma-4-31B-it"] == DECLARED["gemma_share"]
    assert (
        measured["duplicates"]["user_turn_groups"]
        == DECLARED["duplicate_user_turn_groups"]
    )
    assert (
        measured["duplicates"]["system_user_pair_groups"]
        == DECLARED["duplicate_system_user_pairs"]
    )


def test_the_declared_invalid_counts_are_what_the_checks_count(
    measured: dict[str, Any],
) -> None:
    assert (
        measured["invalid_counts"]
        == read_yaml(REPO_ROOT / "params.yaml")["invalid_counts"]
    )


def test_no_catalog_in_this_file_is_empty(measured: dict[str, Any]) -> None:
    """`catalog_size.min` of 1 is why `empty_catalog` reads 0 rather than 841."""
    assert measured["catalog_size"]["min"] == 1
    assert measured["catalog_size"]["max"] == 20


def test_the_records_a_person_already_checked_are_counted(
    measured: dict[str, Any],
) -> None:
    """951 records carry `human_checked`, and no spec or plan mentions the key.

    Counted here because the pipeline needs a gold set in five places -- juror
    weights, annotator scoring, the pilot gate, the 100%-human-validated test split
    -- and no document says where one comes from. `human_checked` is always True and
    `human_check_src` names a targeted generation pass rather than a random sample, so
    this is a candidate pool with a known bias, not a gold set.
    """
    checked = measured["gold"]

    assert checked["field"] == "human_checked"
    assert checked["records"] == 951
    assert checked["by_source"] == {"confuse_b1": 34, "debait": 917}
    assert checked["and_the_label_changed"] == 94
    assert measured["label_source"] == {"claude_corrected": 1358}
    assert (
        measured["meta_keys"]["human_checked"]
        == measured["meta_keys"]["human_check_src"]
    )


def test_every_meta_key_is_counted_not_just_the_documented_ones(
    measured: dict[str, Any],
) -> None:
    """Six of the fourteen appear in no spec: a key-set count alone hides which."""
    assert set(measured["meta_keys"]) == {
        "base_label",
        "domain",
        "gen_category",
        "human_check_src",
        "human_checked",
        "job_id",
        "label",
        "label_source",
        "llm_model",
        "orig_label",
        "scenario",
        "source",
        "source_index",
        "subscenario",
    }
    assert measured["meta_keys"]["label"] == measured["records"]


def test_privacy_signals_are_empty_until_the_modality_declares_detectors(
    measured: dict[str, Any],
) -> None:
    """Counted through `personal_data_detectors()`, so the five appear without a second
    implementation of what a Vietnamese phone number looks like."""
    assert measured["privacy_signals"] == {}
    assert TEXT.personal_data_detectors() == []


# --- the point of the command -------------------------------------------------


def test_an_older_source_drifts_and_the_moved_count_is_named(
    measured: dict[str, Any],
) -> None:
    """The 2026-08-17 backup holds the 48 that were found by accident."""
    if not BACKUP.exists():
        pytest.skip(f"{BACKUP.name} is not present in data/raw/")

    before = measure_corpus.corpus_measurements(BACKUP, TEXT, TOOL_DECISION)

    assert before["invalid_counts"]["label_assistant_mismatch"] == 48
    moved = measure_corpus.moved_measurements(measured, before)
    assert any("invalid_counts.label_assistant_mismatch" in line for line in moved)
    assert any("was 0, now 48" in line for line in moved)


def test_drift_names_a_count_that_appeared_and_one_that_vanished() -> None:
    moved = measure_corpus.moved_measurements({"a": 1, "gone": 2}, {"a": 1, "new": 3})

    assert moved == ["gone: was 2, now '<absent>'", "new: absent before, now 3"]


def test_the_command_exits_non_zero_when_a_count_moved(tmp_path: Path) -> None:
    """A drift has to stop `dvc repro` and CI, not print a warning into a log."""
    baseline = tmp_path / "corpus_profile.json"
    stale = (
        json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    )
    if not stale:
        pytest.skip("no baseline committed yet; run `dataforce profile`")
    stale["records"] = stale["records"] + 1
    baseline.write_text(json.dumps(stale), encoding="utf-8")

    finished = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;"
            "from pathlib import Path;"
            "from dataforce.modalities.text import TEXT;"
            "from dataforce.profiles.tool_decision import TOOL_DECISION;"
            "from dataforce.profiles.tool_decision.measure_corpus import profile_corpus;"
            f"_, moved = profile_corpus(TEXT, TOOL_DECISION, baseline=Path({str(baseline)!r}));"
            "print(moved);"
            "sys.exit(1 if moved else 0)",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert finished.returncode == 1, finished.stderr
    assert "records" in finished.stdout
    assert (
        json.loads(baseline.read_text(encoding="utf-8"))["records"] == stale["records"]
    ), "a drifting measurement must not overwrite the baseline it disagrees with"


def test_the_profiler_never_holds_the_file(measured: dict[str, Any]) -> None:
    """126 MiB on disk. Traced allocation stays a fraction of it, so it streams."""
    tracemalloc.start()
    measure_corpus.corpus_measurements(source_path(), TEXT, TOOL_DECISION)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < source_path().stat().st_size // 4, f"peak traced allocation {peak}"
