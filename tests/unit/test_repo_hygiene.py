"""The two repo-level properties that hold before any stage exists.

`data/raw/` is outside DVC because the PII vault lives there, and one module
configures logging because a library that installs a handler on import is a
nuisance to everyone who imports it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

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


def test_only_the_cli_configures_logging(source_files: list[Path]) -> None:
    offenders = []
    for path in source_files:
        if path.name == "cli.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _called_names(tree) & HANDLER_CALLS:
            offenders.append(path.name)
    assert not offenders, f"configure logging in cli.py only, not in {offenders}"
