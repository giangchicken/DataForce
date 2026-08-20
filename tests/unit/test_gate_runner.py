"""The gate engine: what it writes, what it refuses, and that it exits non-zero."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from agent_toolkit.file_utils import read_json

from dataforce.declared.thresholds import thresholds
from dataforce.shared.errors import DataForceError
from dataforce.shared.gates.runner import (
    GATE_FAILED_FILENAME,
    MAX_OFFENDING_RIDS,
    GateFailed,
    GateResult,
    check,
    conservation,
    require_upstream_ok,
)


def _passing() -> GateResult:
    return GateResult(name="ok", assertion="1 == 1", ok=True, observed=1, expected=1)


def test_conservation_reconciles_a_stage_that_quarantined_and_grouped() -> None:
    result = conservation(
        input_count=21172, output_count=19609, quarantined=1563, deduped_out=0
    )
    assert result.ok


def test_conservation_catches_a_stage_that_dropped_records() -> None:
    result = conservation(input_count=100, output_count=97, quarantined=1)
    assert not result.ok
    assert result.observed["accounted"] == 98
    assert result.expected == {"input": 100}


def test_a_passing_stage_writes_its_metrics(tmp_path: Path) -> None:
    check("load", [conservation(input_count=3, output_count=3)], out_dir=tmp_path)
    metrics = read_json(tmp_path / "metrics.json")
    assert metrics["stage"] == "load"
    assert metrics["gates"][0]["gate"] == "conservation"
    assert not (tmp_path / GATE_FAILED_FILENAME).exists()


def test_a_failing_gate_writes_all_four_fields_and_stops_the_run(
    tmp_path: Path,
) -> None:
    failing = conservation(
        input_count=100, output_count=90, offending_rids=("a" * 16, "b" * 16)
    )
    with pytest.raises(GateFailed, match="conservation"):
        check("remove_invalid", [failing], out_dir=tmp_path)

    written = read_json(tmp_path / GATE_FAILED_FILENAME)
    assert written["assertion"] == "output + quarantined + deduped_out == input"
    assert written["observed"]["output"] == 90
    assert written["expected"] == {"input": 100}
    assert written["offending_rids"] == ["a" * 16, "b" * 16]


def test_offending_ids_are_capped(tmp_path: Path) -> None:
    many = tuple(f"{i:016x}" for i in range(500))
    with pytest.raises(GateFailed):
        check(
            "dedup",
            [conservation(input_count=1, output_count=0, offending_rids=many)],
            out_dir=tmp_path,
        )
    written = read_json(tmp_path / GATE_FAILED_FILENAME)
    assert len(written["offending_rids"]) == MAX_OFFENDING_RIDS


def test_a_fixed_stage_clears_its_previous_failure(tmp_path: Path) -> None:
    (tmp_path / GATE_FAILED_FILENAME).write_text("{}", encoding="utf-8")
    check("load", [_passing()], out_dir=tmp_path)
    assert not (tmp_path / GATE_FAILED_FILENAME).exists()


def test_no_stage_consumes_an_input_whose_gate_did_not_pass(tmp_path: Path) -> None:
    upstream = tmp_path / "1_data_quality"
    upstream.mkdir()
    require_upstream_ok(upstream)

    (upstream / GATE_FAILED_FILENAME).write_text("{}", encoding="utf-8")
    with pytest.raises(DataForceError, match="refusing to consume"):
        require_upstream_ok(upstream)


def test_a_failing_gate_exits_non_zero_which_is_what_halts_dvc(tmp_path: Path) -> None:
    script = f"""
from pathlib import Path
from dataforce.shared.gates.runner import check, conservation
check("load", [conservation(input_count=2, output_count=1)], out_dir=Path({str(tmp_path)!r}))
"""
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert done.returncode != 0
    assert "GateFailed" in done.stderr


def test_thresholds_come_from_the_config_file(tmp_path: Path) -> None:
    config = tmp_path / "gates.yaml"
    config.write_text("jury:\n  max_invalid_vote_rate: 0.05\n", encoding="utf-8")
    assert thresholds("jury", path=config) == {"max_invalid_vote_rate": 0.05}
    assert thresholds("nothing_declared", path=config) == {}


def test_the_shipped_config_declares_the_universal_gate(repo_root: Path) -> None:
    assert thresholds("conservation", path=repo_root / "config" / "gates.yaml") == {}


def test_the_engine_holds_no_threshold(repo_root: Path) -> None:
    """Any number a gate compares against belongs in a config file, not here."""
    runner = repo_root / "src" / "dataforce" / "shared" / "gates" / "runner.py"
    tree = ast.parse(runner.read_text(encoding="utf-8"))
    numbers = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    }
    assert numbers <= {0, MAX_OFFENDING_RIDS}, f"threshold in {runner}: {numbers}"
