"""I22 · every module's docstring opens with one of the five kinds Requirement 2 names.

Requirement 2 says the first word declares what the module is: `DEFINITION`, `LOGIC`, `STEP`,
`TOOL`, and `façade` for an `__init__.py` that re-exports and holds nothing of its own. I19 compares
a module's docstring line to its row in the layout tree, which means a module and its row can be
wrong *together* -- they are one edit apart and nothing else reads either.

**The five words are read out of the requirement, not listed here.** A list in this file would be a
second statement of the vocabulary, and §41 is the reason there is not one: the requirement's own
sentence is parsed, so adding a sixth kind to the document is what makes a sixth kind legal in the
tree.

**One module is exempt and says so in its own docstring.** `dataforce/__init__.py` opens with
`DataForce —` because none of the five kinds describes the package itself; AGENTS.md §8 says a rule
broken on purpose is recorded where the next reader will hit it, and it is recorded there, in
Requirement 2, and here. The exemption is one named module rather than a rule, so a second module
claiming it fails.
"""

import ast
import re

import pytest

from .tree import SPEC, Module, module_from_source, modules_in

# The one docstring that opens with none of the five kinds, because it is the package's own.
THE_PACKAGE = "dataforce"
REQUIREMENT_2 = re.compile(r"^2\. (.+?)(?=^3\. )", re.DOTALL | re.MULTILINE)


def code_shape() -> str:
    """§ *Code shape*, on its own. Other sections number their own lists, and one starts at 2."""
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("### Code shape")
    return text[start : text.index("\n### ", start + 1)]


def declared_kinds() -> set[str]:
    """The kinds Requirement 2 names, as it names them: a backticked word before a `·`."""
    stated = REQUIREMENT_2.search(code_shape())

    assert stated, "spec.md § *Code shape* no longer has a Requirement 2 to read"
    return set(re.findall(r"`(\w+) ·`", stated[1]))


def kind_findings(module: Module, kinds: set[str]) -> list[str]:
    """The module's opening word, if it is not one of the kinds and the module is not the package."""
    if module.name == THE_PACKAGE:
        return []
    docstring = ast.get_docstring(module.tree)
    if not docstring:
        return [f"{module.name} opens with no docstring at all"]
    first = docstring.split()[0]
    return (
        []
        if first in kinds
        else [
            f"{module.name} opens with {first!r}, which is not one of {sorted(kinds)}"
        ]
    )


def test_the_requirement_was_found_and_names_five_kinds() -> None:
    """Guards the parse: an empty set would fail every module, a wrong one would pass everything."""
    kinds = declared_kinds()

    assert kinds == {"DEFINITION", "LOGIC", "STEP", "TOOL", "façade"}


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_every_module_declares_one_of_the_five_kinds(module: Module) -> None:
    """I22, over the tree. I19 checks the words after the kind; this checks the kind."""
    assert kind_findings(module, declared_kinds()) == []


def test_the_package_docstring_is_the_only_module_exempt() -> None:
    """The recorded break, held to one module: any other opening with `DataForce` fails."""
    package = [m for m in modules_in() if not kind_findings(m, declared_kinds())]
    imposter = module_from_source('"""DataForce -- a second package docstring."""')

    assert len(package) == len(modules_in())
    assert kind_findings(imposter, declared_kinds()) != []


@pytest.mark.parametrize(
    "violation",
    [
        '"""HELPER · a kind nobody declared."""',
        '"""definition · the right word, the wrong case."""',
        '"""Holds the record and its parts."""',
        "x = 1",
    ],
    ids=["invented", "lowercased", "no-kind", "no-docstring"],
)
def test_the_scan_rejects_a_module_that_declares_no_kind(violation: str) -> None:
    """§39: an invented kind, a miscased one, a prose docstring, and no docstring at all."""
    assert kind_findings(module_from_source(violation), declared_kinds()) != []


@pytest.mark.parametrize(
    "permitted",
    [
        '"""DEFINITION · one noun and its shape."""',
        '"""façade · re-exports and holds nothing of its own."""',
        '"""STEP · load_data · every source item becomes one record."""',
    ],
    ids=["definition", "façade", "step"],
)
def test_the_scan_permits_a_module_that_declares_one(permitted: str) -> None:
    """The green case, so the rule is known to be a rule and not a refusal."""
    assert kind_findings(module_from_source(permitted), declared_kinds()) == []
