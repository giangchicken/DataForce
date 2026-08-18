"""The pinned library resolves, and its own consumer contract holds against it.

`agent-toolkit` is on no registry, so it is pinned to an immutable git ref. A ref
that does not resolve, or a release whose contract moved, is a failure worth
having here -- at `make integration` -- rather than at the first jury run.

The library's `tests/consumer_smoke.py` is not in the wheel: it builds
`packages = ["src/agent_toolkit"]`. So this test fetches it from the pinned ref.
Needs the network, and a populated `TIKTOKEN_CACHE_DIR` on a host without egress.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _pinned_ref(repo_root: Path) -> tuple[str, str]:
    manifest = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    for requirement in manifest["project"]["dependencies"]:
        if requirement.startswith("agent-toolkit"):
            _, _, reference = requirement.partition("git+")
            url, _, ref = reference.rpartition("@")
            assert url and ref, f"cannot read a git ref out of {requirement!r}"
            return url, ref
    raise AssertionError("agent-toolkit is not a declared dependency")


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300
    )


def test_the_installed_library_satisfies_its_own_consumer_contract(
    repo_root: Path, tmp_path: Path
) -> None:
    url, ref = _pinned_ref(repo_root)

    clone = tmp_path / "agent-toolkit"
    clone.mkdir()
    assert _git("init", "-q", cwd=clone).returncode == 0
    assert _git("remote", "add", "origin", url, cwd=clone).returncode == 0

    fetched = _git("fetch", "-q", "--depth", "1", "origin", ref, cwd=clone)
    assert fetched.returncode == 0, (
        f"the pinned ref {ref!r} does not resolve at {url}: {fetched.stderr.strip()}"
    )
    assert _git("checkout", "-q", "FETCH_HEAD", cwd=clone).returncode == 0

    smoke = clone / "tests" / "consumer_smoke.py"
    assert smoke.exists(), "the pinned release no longer ships tests/consumer_smoke.py"

    done = subprocess.run(
        [sys.executable, str(smoke)],
        cwd=clone,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stdout + done.stderr
