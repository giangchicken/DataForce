"""I1 · the engine opens no file, names no path, and never imports the edge.

Two halves, and neither is enough alone. The scan catches the line that would read the world
before it ever runs; the subprocess catches whatever the scan's list of names does not know about,
by importing both axis implementations from a directory with no ``config/`` in it -- Requirement
37, stated as something a machine runs.

The engine is the package less ``edge/``, and the arrow points one way
(Requirement 36). ``logging`` is permitted by name: a logger call opens no file and names no path,
which is what keeps the observability design inside this invariant -- the engine emits and the edge
installs the handler.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from .tree import (
    Module,
    called_name,
    engine_modules,
    imports,
    module_from_source,
    not_exempt,
)

AXES = "import dataforce.modalities.text2text, dataforce.profiles.tool_decision"

# Roots that only exist to reach the world. `datetime` is absent on purpose -- a timestamp is a
# type the record needs; it is the clock *call* below that is the edge's.
FORBIDDEN_ROOTS = (
    "fastapi",
    "http",
    "httpx",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "starlette",
    "subprocess",
    "tempfile",
    "time",
    "urllib",
)
FORBIDDEN_CALLS = (
    "open",
    "input",
    "date.today",
    "datetime.now",
    "datetime.today",
    "datetime.utcnow",
)
EDGE = ("dataforce.edge",)


def world_reading_findings(module: Module) -> list[str]:
    """Every place this module reads something the edge is supposed to hand it."""
    found: list[tuple[int, str]] = []
    for reached in imports(module):
        if reached.module.split(".")[0] in FORBIDDEN_ROOTS:
            found.append((reached.line, f"imports {reached.module}"))
        if reached.module.startswith(EDGE):
            found.append((reached.line, f"imports the edge: {reached.module}"))
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Call):
            name = called_name(node)
            if (
                name in FORBIDDEN_CALLS
                or ".".join(name.split(".")[-2:]) in FORBIDDEN_CALLS
            ):
                found.append((node.lineno, f"calls {name}()"))
    return not_exempt(module, "I1", found)


@pytest.mark.parametrize("module", engine_modules(), ids=lambda m: m.name)
def test_no_engine_module_reads_the_world(module: Module) -> None:
    """I1, the scan half, over every module the engine owns."""
    assert world_reading_findings(module) == []


@pytest.mark.parametrize(
    "violation",
    [
        "from pathlib import Path",
        "import os",
        "import os.path",
        "from dataforce.edge.artifacts import write_records",
        "from dataforce.edge.cli import main",
        "def read(p):\n    return open(p).read()",
        "from datetime import datetime\nstamped = datetime.now()",
        "import time\nstamped = time.time()",
    ],
    ids=["pathlib", "os", "os.path", "edge", "cli", "open", "clock", "time"],
)
def test_the_scan_rejects_a_module_that_reads_the_world(violation: str) -> None:
    """P29: proved red against a synthetic violation, one per way in."""
    assert world_reading_findings(module_from_source(violation)) != []


def test_the_scan_permits_logging_by_name() -> None:
    """The engine emits events; the edge decides where they go (spec.md § *Observability*)."""
    emitting = (
        "import logging\n\nlog = logging.getLogger(__name__)\nlog.info('started')"
    )

    assert world_reading_findings(module_from_source(emitting)) == []


def test_an_annotated_exemption_is_honoured() -> None:
    """P30: a rule with no escape hatch is a rule someone deletes."""
    excused = "import os  # guard-exempt: I1 · a reason · an owner · 2026-08-23"

    assert world_reading_findings(module_from_source(excused)) == []


def test_an_exemption_for_a_different_invariant_is_not_honoured() -> None:
    """An exemption excuses the rule it names and no other."""
    mislabelled = "import os  # guard-exempt: I6 · a reason · an owner · 2026-08-23"

    assert world_reading_findings(module_from_source(mislabelled)) != []


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
