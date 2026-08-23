"""I1 · the engine opens no file and names no path.

Two halves. This module holds the second: a subprocess that imports both axis implementations
from a directory with no ``config/`` in it, which is Requirement 37 stated as something a machine
can run. The first half -- the AST scan over every engine module -- lands with the rest of the
guards.

A subprocess rather than an import in-process, because by the time this test runs the package has
already been imported by the collector, and an import that read a file would have read it already.
"""

import subprocess
import sys
from pathlib import Path

AXES = "import dataforce.modalities.text2text, dataforce.profiles.tool_decision"


def test_importing_both_axes_needs_no_config_directory(tmp_path: Path) -> None:
    """Requirement 37: the import succeeds where there is nothing to read."""
    done = subprocess.run(
        [sys.executable, "-c", AXES], cwd=tmp_path, capture_output=True, text=True
    )

    assert not list(tmp_path.iterdir()), "the fixture directory is supposed to be empty"
    assert done.returncode == 0, done.stderr


def test_importing_both_axes_writes_nothing(tmp_path: Path) -> None:
    """Requirement 37: and it leaves the directory it was run from as it found it."""
    subprocess.run([sys.executable, "-c", AXES], cwd=tmp_path, check=True)

    assert list(tmp_path.rglob("*")) == []
