"""I5 · identity comes from the manifest filename, never from a class body.

`name`, `version` and `modality` are `config/<axis>/<name>.yaml`'s to say, and the filename *is* the
identity (Requirement 40). A class that assigns one of them holds a second copy of a fact the
manifest already states, and it is always the copy that goes stale -- the manifest gets renamed and
the class keeps answering with the old string.

Only a **constant** assignment is a finding. `name: str` declares a field and says nothing about
whose name it is; `name: str = Field(..., description=…)` is a pydantic field with a default
factory, not an identity. What this catches is `name = "text2text"`, which is the thing that
happens.
"""

import ast

import pytest

from .tree import Module, module_from_source, modules_in, not_exempt

IDENTITY = ("modality", "name", "version")


def identity_findings(module: Module) -> list[str]:
    """Every class in this module that hardcodes an identity the manifest owns."""
    found = []
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            for target in _assigned_constants(statement):
                found.append(
                    (statement.lineno, f"{node.name}.{target} is assigned in the body")
                )
    return not_exempt(module, "I5", found)


def _assigned_constants(statement: ast.stmt) -> list[str]:
    """The identity keys this statement assigns a literal to, directly in a class body."""
    if isinstance(statement, ast.AnnAssign):
        targets, value = [statement.target], statement.value
    elif isinstance(statement, ast.Assign):
        targets, value = statement.targets, statement.value
    else:
        return []
    if not isinstance(value, ast.Constant):
        return []
    return [t.id for t in targets if isinstance(t, ast.Name) and t.id in IDENTITY]


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_no_class_assigns_its_own_identity(module: Module) -> None:
    """I5, over the whole package -- the edge is no more entitled to it than the engine."""
    assert identity_findings(module) == []


@pytest.mark.parametrize(
    "violation",
    [
        'class Text2Text:\n    name = "text2text"',
        'class Text2Text:\n    version: str = "1"',
        'class ToolDecision:\n    modality = "text2text"',
    ],
    ids=["name", "annotated-version", "modality"],
)
def test_the_scan_rejects_a_class_that_hardcodes_an_identity(violation: str) -> None:
    """P29: proved red against a synthetic violation, one per key and both spellings."""
    assert identity_findings(module_from_source(violation)) != []


@pytest.mark.parametrize(
    "permitted",
    [
        "class Tool:\n    name: str",
        'class Tool:\n    name: str = Field(..., description="the tool")',
        'class Manifest:\n    def read(self):\n        name = "text2text"\n        return name',
    ],
    ids=["declaration", "described-field", "local"],
)
def test_the_scan_permits_a_field_that_merely_has_a_name(permitted: str) -> None:
    """A model whose field is called `name` is not a class claiming a name."""
    assert identity_findings(module_from_source(permitted)) == []
