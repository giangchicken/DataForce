"""I19 · every module is in the layout tree, described the way it describes itself.

`spec.md` § *Package layout* draws the whole package and says what each module is for. That is where
a person looks to find out where something lives, so it is also the first thing to go stale: a module
added without a row is invisible, and a row left behind after a rename points at nothing. §41 -- a
fact stated in a document and in code is compared by a test.

**A row is the module's own docstring, not a second description of it.** Two summaries of one module
drift the moment either is edited, and the drift is silent because both still read fine. So the tree's
text for `errors.py` *is* the first line of `errors.py`'s docstring, and this guard compares them word
for word. A directory row describes a directory, which has no docstring, and its text is not checked;
the modules under it carry the meaning.

**No §40 hatch.** An exemption annotates a line, and "this module has no row" has no line to annotate
-- the same shape as I4's file-set half. The fix is the row.
"""

import ast
from collections.abc import Mapping

import pytest

from .tree import SPEC, SRC, module_at, plain

FENCE = "```"
ROOT = "src/dataforce/"


def layout_fence() -> list[str]:
    """The lines of the § *Package layout* code block that draws the package."""
    blocks = SPEC.read_text(encoding="utf-8").split(FENCE)
    drawings = [block for block in blocks if block.lstrip().startswith(ROOT)]

    assert len(drawings) == 1, (
        f"expected exactly one {ROOT} tree in {SPEC.name}, found {len(drawings)}"
    )
    return drawings[0].splitlines()


def layout_rows() -> dict[str, str]:
    """Every module the tree lists, as a path under `src/dataforce/`, and what it says it is for.

    Indentation is the nesting and a trailing `/` is a directory, which is how the drawing already
    reads to a person. Nothing else marks structure.
    """
    stack: list[tuple[int, str]] = []
    rows: dict[str, str] = {}
    for line in layout_fence():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        name, _, purpose = line.strip().partition(" ")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if name.endswith("/"):
            stack.append((indent, name))
        else:
            rows["".join(part for _, part in stack[1:]) + name] = purpose.strip()
    return rows


def modules_on_disk() -> dict[str, str]:
    """Every module under `src/dataforce/`, and the first line of the docstring it opens with."""
    return {
        path.relative_to(SRC).as_posix(): next(
            iter((ast.get_docstring(module_at(path).tree) or "").splitlines()), ""
        )
        for path in sorted(SRC.rglob("*.py"))
    }


def layout_findings(rows: Mapping[str, str]) -> list[str]:
    """Every way the drawing and the package disagree, named by the module each is about."""
    disk = modules_on_disk()
    found = [f"{path}: a row with no module" for path in rows if path not in disk]
    found += [f"{path}: a module with no row" for path in disk if path not in rows]
    found += [
        f"{path}: the tree says {rows[path]!r}, the module says {summary!r}"
        for path, summary in disk.items()
        if path in rows and plain(rows[path]) != plain(summary)
    ]
    return sorted(found)


def test_the_drawing_was_found_and_parsed() -> None:
    """Guards the parser: an unread tree makes every assertion below vacuous."""
    rows = layout_rows()

    assert "errors.py" in rows
    assert "pipeline/data_quality/pii_check.py" in rows
    assert "edge/routers/schemas.py" in rows
    assert "edge/cli.py" in rows


def test_the_tree_and_the_package_hold_the_same_modules() -> None:
    """I19, both directions, and the text with them."""
    assert layout_findings(layout_rows()) == []


def test_the_scan_rejects_a_module_with_no_row() -> None:
    """§39: the common one -- a module added and the drawing not touched."""
    rows = dict(layout_rows())
    rows.pop("errors.py")

    assert layout_findings(rows) != []


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            {"pipeline/ghost.py": "STEP · ghost · nothing"}, id="row-with-no-module"
        ),
        pytest.param(
            {"errors.py": "DEFINITION · something else entirely"}, id="reworded-row"
        ),
    ],
)
def test_the_scan_rejects_a_tree_that_has_drifted(mutation: dict[str, str]) -> None:
    """§39: a row that outlived its module, and a row reworded on one side only."""
    assert layout_findings({**layout_rows(), **mutation}) != []


def test_the_scan_permits_markup_the_two_mediums_spell_differently() -> None:
    """A docstring writes ``content`` and `--`; the spec writes `content` and an em dash."""
    respelled = {
        path: text.replace("--", "—").replace("`", "") + "."
        for path, text in layout_rows().items()
    }

    assert layout_findings(respelled) == []
