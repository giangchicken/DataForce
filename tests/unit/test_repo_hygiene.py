"""The repo-level properties: nothing a run writes is committable, and one logger.

`data/raw/` is outside DVC because the PII vault lives there, and one module
configures logging because a library that installs a handler on import is a
nuisance to everyone who imports it.

The third claim arrived with stage 0, which is what made it checkable: a run writes
files, and `git status` is where you find out whether git thinks you meant to commit
them. It did not -- `data/run.json` was outside every tier `.gitignore` listed, and
`git add -A` staged the run manifest of a 21,172-record run. Asserted through
`git check-ignore` rather than by reading `.gitignore`, because what matters is
whether the rules match the path, not whether a line resembling it is present.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import yaml

from dataforce import api

HANDLER_CALLS = frozenset(
    {
        "basicConfig",
        "addHandler",
        "StreamHandler",
        "FileHandler",
        "dictConfig",
        "fileConfig",
    }
)


def _called_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            names.add(func.attr)
        elif isinstance(func, ast.Name):
            names.add(func.id)
    return names


def test_raw_tier_is_ignored_by_git(repo_root: Path) -> None:
    lines = (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/raw/" in [line.strip() for line in lines]


def test_raw_tier_is_outside_dvc(repo_root: Path) -> None:
    for dvc_file in repo_root.rglob("*.dvc"):
        if not dvc_file.is_file():  # .dvc/ is the config directory, not a file
            continue
        assert "data/raw" not in dvc_file.read_text(encoding="utf-8"), dvc_file

    pipeline = yaml.safe_load((repo_root / "dvc.yaml").read_text(encoding="utf-8"))
    for name, stage in (pipeline.get("stages") or {}).items():
        for out in stage.get("outs") or []:
            path = out if isinstance(out, str) else next(iter(out))
            assert not str(path).startswith("data/raw"), name

    lock = repo_root / "dvc.lock"
    if lock.exists():
        assert "data/raw" not in lock.read_text(encoding="utf-8")


def test_nothing_a_run_writes_is_committable(repo_root: Path) -> None:
    """Every path `dataforce run` writes into this repository, ignored by git."""
    data_root = Path("data")
    written = [
        data_root / api.RUN_MANIFEST_FILENAME,
        api.interim_directory("data_quality", data_root=data_root) / "loaded.jsonl",
        api.interim_directory("data_quality", data_root=data_root)
        / api.METRICS_FILENAME,
        api.interim_directory("data_quality", data_root=data_root)
        / api.GATE_FAILED_FILENAME,
    ]
    tracked = [
        str(path)
        for path in written
        if subprocess.run(
            ["git", "check-ignore", "-q", str(path)], cwd=repo_root
        ).returncode
        != 0
    ]
    assert not tracked, f"git would let these be committed: {tracked}"


def test_only_the_cli_configures_logging(source_files: list[Path]) -> None:
    offenders = []
    for path in source_files:
        if path.name == "cli.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _called_names(tree) & HANDLER_CALLS:
            offenders.append(path.name)
    assert not offenders, f"configure logging in cli.py only, not in {offenders}"
