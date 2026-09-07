"""H-8 and E-1 · every module's first word is one of five tags, and no import goes against them.

`H-8` names the five -- `shape`, `logic`, `facade`, `adapter`, `wiring` -- and gives the import
direction as a table whose fourth column is the declaration. `E-1` says a declared direction is
enforced by a check that fails the build, not by discipline, and nothing checked either until this
module: the tree wrote seven things where the rule names five, and two imports had already gone the
wrong way -- `services/` reached for `edge/store`, logic reaching for an adapter, and `edge/cli.py`
imported a deleted module for four commits.

**A facade is a door, not a destination.** As an importer it is `H-8`'s fifth row and may reach
anything inside the package. As a *target* it is whatever stands behind it, because checking the tag
on the door would let every forbidden import through by spelling it one level higher. That is not
hypothetical: `services/` reached for `edge/store` as `from dataforce.edge.store import ...`, and
`edge/store/__init__.py` is a facade. So `logic` importing that facade is `logic` importing an
`adapter`.

What stands behind a door is read two ways, because a facade leaks two ways. `dataforce.edge.store`
re-exports `records`, so its re-exports say what it opens onto. `dataforce.edge` re-exports
nothing -- and reading only re-exports made it a hole: `import dataforce.edge` binds a package
whose `edge.main` is reachable through it the moment anything loads that module, so a `shape` module
could reach `wiring` through an empty door and no tag would say so. A package name stands for its
subtree, so the subtree is read as well.

**The tag on the importer is what may be narrowed.** A module may import its own tag -- one `logic`
module calling another is a decision calling a decision -- and everything below it. `shape` may
import `shape` and nothing else, which is `H-8`'s "may import: nothing" read at the granularity a
scan works in: a noun may not reach for a decision.

**A word that is not one of the five permits nothing.** An unknown tag declares no direction, so
every import it makes is a finding. Reading it as *no constraint* is how one annotation on the
docstring buys a module unlimited import freedom -- the tag rule and the direction rule would both
fall to the same line.
"""

import ast

import pytest

from .tree import Module, imports, module_from_source, modules_in, not_exempt

RULE = "H-8"

# `H-8`'s fourth column, one row per tag. The values hold no `facade`: a facade is never a
# destination, because `exposed_tags` resolves it to what stands behind it.
MAY_IMPORT = {
    "shape": frozenset({"shape"}),
    "logic": frozenset({"shape", "logic"}),
    "adapter": frozenset({"shape", "logic", "adapter"}),
    "wiring": frozenset({"shape", "logic", "adapter", "wiring"}),
    "facade": frozenset({"shape", "logic", "adapter", "wiring"}),
}
TAGS = frozenset(MAY_IMPORT)


def tag_of(module: Module) -> str:
    """The first word of the module docstring, or `""` where there is no docstring to read."""
    docstring = ast.get_docstring(module.tree) or ""
    return docstring.split(maxsplit=1)[0] if docstring.split() else ""


TREE = {module.name: module for module in modules_in()}
TAG = {name: tag_of(module) for name, module in TREE.items()}


def reached_modules(module: Module) -> list[tuple[int, str]]:
    """Every module of this package that one reaches, and the line reaching it.

    `imports` yields a name per statement and a name per alias, so a symbol and the module holding
    it both come back; only the names that are modules here are the import graph.
    """
    return [
        (found.line, found.module)
        for found in imports(module)
        if found.module in TREE and found.module != module.name
    ]


def exposed_tags(name: str, seen: frozenset[str] = frozenset()) -> frozenset[str]:
    """What importing that module actually reaches: its own tag, or what stands behind a door.

    Behind a facade is what it re-exports and what its subtree holds -- the two ways a door leaks,
    and a facade that re-exports nothing still names a package.
    """
    tag = TAG.get(name, "")
    if tag != "facade":
        return frozenset({tag})
    if name in seen:
        return frozenset()
    behind = {reached for _, reached in reached_modules(TREE[name])}
    behind |= {under for under in TREE if under.startswith(f"{name}.")}
    return frozenset().union(
        *(exposed_tags(one, seen | {name}) for one in behind), frozenset()
    )


def tag_findings(module: Module) -> list[str]:
    """The module whose docstring opens with a word `H-8` does not name.

    No hatch: there is no sixth tag to excuse, and the finding is the docstring's own first line, so
    an exemption could only be written inside the text being rejected.
    """
    tag = tag_of(module)
    if tag in TAGS:
        return []
    said = f"the tag {tag!r}" if tag else "no docstring"
    return [f"{module.name}:1 opens with {said}, not one of {sorted(TAGS)}"]


def direction_findings(module: Module) -> list[str]:
    """Every import this module makes that `H-8`'s table sends the other way."""
    permitted = MAY_IMPORT.get(tag_of(module), frozenset())
    return not_exempt(
        module,
        RULE,
        [
            (line, f"{tag_of(module)} imports {reached}, which is {sorted(against)}")
            for line, reached in reached_modules(module)
            if (against := exposed_tags(reached) - permitted)
        ],
    )


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_every_module_opens_with_one_of_the_five_tags(module: Module) -> None:
    """H-8's first half. Two answers means the file holds two jobs; a sixth word means neither."""
    assert tag_findings(module) == []


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_no_import_goes_against_the_declared_direction(module: Module) -> None:
    """H-8's fourth column, which is what `E-1` asks to be enforced rather than remembered."""
    assert direction_findings(module) == []


@pytest.mark.parametrize(
    "sixth",
    [
        '"""helper · what it does."""',
        '"""DEFINITION · a noun."""',
        '"""façade · a door."""',
    ],
    ids=["helper", "the-deleted-spec-s-tag", "the-cedilla"],
)
def test_the_scan_rejects_a_sixth_tag(sixth: str) -> None:
    """Proved red. The cedilla is a finding because the tag is read by a machine, this one."""
    assert tag_findings(module_from_source(sixth)) != []


def test_the_scan_rejects_a_module_with_no_docstring() -> None:
    """A module with nothing to read declares no job, which is the same gap as a sixth word."""
    assert tag_findings(module_from_source("import os")) != []


@pytest.mark.parametrize(
    "wrong_way",
    [
        '"""logic · a decision."""\n\nfrom dataforce.edge.store.records import stored_row',
        '"""logic · a decision."""\n\nfrom dataforce.edge.store import stored_row',
        '"""shape · a noun."""\n\nfrom dataforce.profile.tool_decision.utils import x',
        '"""adapter · a translation."""\n\nfrom dataforce.edge.main import create_app',
        '"""shape · a noun."""\n\nimport dataforce.edge',
        '"""logic · a decision."""\n\nfrom dataforce import edge',
    ],
    ids=[
        "logic-to-adapter",
        "logic-through-a-facade",
        "shape-to-logic",
        "adapter-to-wiring",
        "shape-through-an-empty-facade",
        "logic-through-an-empty-facade",
    ],
)
def test_the_scan_rejects_an_import_against_the_direction(wrong_way: str) -> None:
    """Proved red, one per row of the table that forbids something.

    `logic-through-a-facade` is the case that happened: spelling the same import one level higher
    is what a scan reading the tag on the door would have allowed. The two empty-facade cases are
    the same bypass one level higher again -- `dataforce/edge/__init__.py` re-exports nothing, so
    only its subtree says that `edge.main` is `wiring`.
    """
    assert direction_findings(module_from_source(wrong_way)) != []


def test_an_unknown_tag_permits_no_import_at_all() -> None:
    """The bypass the two rules would otherwise share.

    A tag rule reported on line 1 and a direction rule that skips a tag it does not know means one
    annotation on the docstring excuses the tag *and* every import under it. So an unknown tag
    declares no direction, and every import it makes is a finding.
    """
    unknown = (
        '"""helper · a bucket."""'
        "  # guard-exempt: H-8 · the reason · the owner · 2026-09-07"
        "\n\nfrom dataforce.edge.main import create_app"
    )

    assert direction_findings(module_from_source(unknown)) != []


def test_a_facade_importing_across_the_package_is_permitted_by_the_table_itself() -> (
    None
):
    """`H-8`'s fifth row, read rather than fallen through.

    A facade re-exports, so it reaches anything inside the package -- but it has to be *permitted*
    that, not merely unrecognised: a tag the table does not know must permit nothing.
    """
    door = '"""facade · a door."""\n\nfrom dataforce.edge.main import create_app'

    assert MAY_IMPORT["facade"] >= frozenset({"wiring"})
    assert direction_findings(module_from_source(door)) == []


@pytest.mark.parametrize(
    "permitted",
    [
        '"""logic · a decision."""\n\nfrom dataforce.errors import ConfigError',
        '"""logic · a decision."""\n\nfrom dataforce.profile.tool_decision.utils import x',
        '"""adapter · a translation."""\n\nfrom dataforce.services.tool_decision import x',
        '"""wiring · the root."""\n\nfrom dataforce.edge.routers import router',
        '"""facade · a door."""\n\nfrom dataforce.edge.store.records import stored_row',
        '"""logic · a decision."""\n\nfrom agent_toolkit.llm import complete',
    ],
    ids=[
        "logic-to-shape",
        "logic-to-logic",
        "adapter-to-logic",
        "wiring-to-anything",
        "facade-to-anything",
        "outside-the-package",
    ],
)
def test_the_scan_permits_the_direction_the_table_declares(permitted: str) -> None:
    """A tag narrows what a module may reach; it does not forbid the axis below it.

    The last case is the rule's edge: `H-8`'s table is about this package, so a library import is
    not an edge in the graph it declares.
    """
    assert direction_findings(module_from_source(permitted)) == []


def test_an_annotated_exemption_covers_one_import() -> None:
    """The hatch, on the line -- so an excused import is readable as one, with an owner and a date."""
    excused = (
        '"""logic · a decision."""\n\n'
        "from dataforce.edge.store import stored_row"
        "  # guard-exempt: H-8 · the reason · the owner · 2026-09-07"
    )

    assert direction_findings(module_from_source(excused)) == []
