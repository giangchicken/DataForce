"""I5 · identity comes from the manifest filename, never from a class body.

`name`, `version` and `modality` are `config/<axis>/<name>.yaml`'s to say, and the filename *is* the
identity (Requirement 40). A class that assigns one of them holds a second copy of a fact the
manifest already states, and it is always the copy that goes stale -- the manifest gets renamed and
the class keeps answering with the old string.

**Seven names, not three, since T52 split the identity.** One object answers both axes now, so the
axes spell their identity `modality_name` and `profile_name` -- and a rule that knew only the bare
three would have gone quiet on exactly the classes it exists for, while still passing. The bare
three stay because `Manifest` still declares them and pinning one there is the same mistake.

Only a **pinned** value is a finding. `name: str` declares a field and says nothing about whose
name it is, and `name: str = Field(..., description=…)` is a required field with no value in it.
What this catches is a string written into the class body, in the three spellings that put one
there: `name = "text2text"`, `name: str = Field("text2text", …)`, and
`name: str = Field(default="text2text", …)`.

**The two `Field` spellings are the ones that would actually happen here.** Every axis type in this
codebase is a pydantic model or is built beside one, so an identity that slips in slips in through
a `Field`, and reading only `ast.Constant` missed both -- the scan was green against the violation
it exists to catch. `None` is not a pin: `modality: str | None = Field(default=None, …)` in
`manifest.py` declares that a modality's own manifest names no modality, which is the opposite of
claiming one.

A value behind any *other* call -- `name = str("text2text")` -- is left alone on purpose. Any call
can produce a constant, and a scan that special-cases `str(` reads like coverage while providing
one name's worth of it.
"""

import ast

import pytest

from .tree import Module, called_name, module_from_source, modules_in, not_exempt

IDENTITY = (
    "modality",
    "modality_name",
    "modality_version",
    "name",
    "profile_name",
    "profile_version",
    "version",
)


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
    """The identity keys this statement pins to a value, directly in a class body."""
    if isinstance(statement, ast.AnnAssign):
        targets, value = [statement.target], statement.value
    elif isinstance(statement, ast.Assign):
        targets, value = statement.targets, statement.value
    else:
        return []
    if not _is_pinned(value) and not _field_default_is_pinned(value):
        return []
    return [t.id for t in targets if isinstance(t, ast.Name) and t.id in IDENTITY]


def _is_pinned(value: ast.expr | None) -> bool:
    """A literal that claims something. `...` is a required field and `None` is an absence."""
    return (
        isinstance(value, ast.Constant)
        and value.value is not None
        and value.value is not ...
    )


def _field_default_is_pinned(value: ast.expr | None) -> bool:
    """The same literal one call deeper: `Field("text2text")` and `Field(default="text2text")`."""
    if not isinstance(value, ast.Call) or called_name(value).split(".")[-1] != "Field":
        return False
    keyword = next((k.value for k in value.keywords if k.arg == "default"), None)
    return _is_pinned(keyword) or _is_pinned(value.args[0] if value.args else None)


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
        'class Text2Text:\n    modality_name = "text2text"',
        'class Text2Text:\n    modality_version: str = "1"',
        'class ToolDecision:\n    profile_name = "tool_decision"',
        'class ToolDecision:\n    profile_version: str = Field("1", description="x")',
        'class Text2Text:\n    name: str = Field("text2text", description="the pair")',
        'class Text2Text:\n    version: str = Field(default="1", description="stamped")',
        'class ToolDecision:\n    modality: str = Field(default="text2text", description="x")',
    ],
    ids=[
        "name",
        "annotated-version",
        "modality",
        "modality-name",
        "modality-version",
        "profile-name",
        "profile-version",
        "field-positional",
        "field-default",
        "field-default-modality",
    ],
)
def test_the_scan_rejects_a_class_that_hardcodes_an_identity(violation: str) -> None:
    """P29: proved red against a synthetic violation, one per key and both spellings."""
    assert identity_findings(module_from_source(violation)) != []


@pytest.mark.parametrize(
    "permitted",
    [
        "class Tool:\n    name: str",
        'class Tool:\n    name: str = Field(..., description="the tool")',
        'class Manifest:\n    modality: str | None = Field(default=None, description="none")',
        'class Tool:\n    name: str = Field(default_factory=str, description="the tool")',
        'class Manifest:\n    def read(self):\n        name = "text2text"\n        return name',
    ],
    ids=["declaration", "described-field", "absent", "factory", "local"],
)
def test_the_scan_permits_a_field_that_merely_has_a_name(permitted: str) -> None:
    """A model whose field is called `name` is not a class claiming a name."""
    assert identity_findings(module_from_source(permitted)) == []
