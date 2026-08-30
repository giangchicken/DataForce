"""I23 · an axis implementation's public surface is exactly its protocol's members.

*Closed* is a claim about two sides and I21 only checks one of them. It compares the ``Protocol`` to
the document, so a member added to the *document* and not the class fails -- and a member added to the
**class** and to neither is invisible to it, because a protocol says nothing about what an
implementation may have on top.

That is not a hypothetical. ``final_label`` shipped as a public method on ``ToolDecision``, used no
``self``, and appeared in neither § *Profile*'s members nor the plan. It is a conversion over a
record, so it belongs beside the other module-level ones; what made it a method was that a method was
the closest thing to hand. T13's own note had refused ``redact_label`` a place on the protocol on §30
grounds -- *a member with no caller is a guess about a future one* -- so the argument existed and this
one arrived without it. That is what this guard says. (``redact_label`` is a member as of T16, which
brought the caller: ``pii_check`` cannot rewrite a label without knowing what an answer is.)

**The classes checked are the ones the façade exports**, which is also what makes a façade exporting a
second class a finding: an axis package's front door is the implementation and the things it is built
with, and a class nobody above can name has no business being public either. ``Encoder`` is a type
alias and ``embedding_model`` is a function, so both are skipped -- this rule is about classes.

Read from the tree rather than from an instance on purpose: constructing one needs a manifest and an
encoder, and a guard that needs fixtures is a guard that gets skipped when the fixtures move.
"""

import ast

import pytest

from dataforce.modalities import Modality
from dataforce.profiles import Profile

from .tree import SRC, Module, axis_implementations, module_at, module_from_source

AXES = [
    pytest.param("modalities", Modality, id="modality"),
    pytest.param("profiles", Profile, id="profile"),
]


def exported_names(package: str) -> list[str]:
    """What that implementation's façade puts in `__all__`, in the order it lists them."""
    facade = module_at(SRC / package / "__init__.py")
    for node in ast.walk(facade.tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
            and isinstance(node.value, ast.List)
        ):
            return [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
    return []


def classes_in(modules: list[Module]) -> dict[str, ast.ClassDef]:
    """Every class those modules define, by name."""
    return {
        node.name: node
        for module in modules
        for node in ast.walk(module.tree)
        if isinstance(node, ast.ClassDef)
    }


def public_surface(declared: ast.ClassDef) -> set[str]:
    """Every name a caller can reach on one of these: its methods, and what `__init__` sets.

    `self._encode` and `_answers_its_protocol` are not surface. A method is read off the class body
    and an attribute off any assignment to `self`, which is where identity lands -- Requirement 40
    forbids it being in the class body, so a scan of the body alone would find no `name` at all.
    """
    surface = {
        node.name
        for node in declared.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    }
    return surface | {
        target.attr
        for node in ast.walk(declared)
        if isinstance(node, ast.Assign | ast.AnnAssign)
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
        and not target.attr.startswith("_")
    }


def surface_findings(package: str, protocol: type) -> list[str]:
    """Every way a class that façade exports departs from the protocol's closed set."""
    modules = [module_at(path) for path in sorted((SRC / package).glob("*.py"))]
    defined = classes_in(modules)
    members = set(protocol.__protocol_attrs__)
    return [
        f"{package}.{exported} has {sorted(surface - members)} and is missing "
        f"{sorted(members - surface)}"
        for exported in exported_names(package)
        if (declared := defined.get(exported)) is not None
        for surface in [public_surface(declared)]
        if surface != members
    ]


@pytest.mark.parametrize(("axis", "protocol"), AXES)
def test_every_exported_class_is_exactly_its_protocol(
    axis: str, protocol: type
) -> None:
    """I23, over both axes. Six and fifteen, on the side I21 cannot see."""
    for package in axis_implementations():
        if package.parent.name != axis:
            continue
        assert surface_findings(f"{axis}/{package.name}", protocol) == []


def test_the_scan_reads_the_classes_it_is_supposed_to_find() -> None:
    """Guards the discovery: a scan that resolved no exported class would pass everything."""
    assert exported_names("profiles/tool_decision") == ["ToolDecision"]
    assert "Text2Text" in exported_names("modalities/text2text")
    assert surface_findings("profiles/tool_decision", Profile) == []


@pytest.mark.parametrize(
    "violation",
    [
        "class Text2Text:\n    def spare(self):\n        return 1",
        "class Text2Text:\n    def __init__(self):\n        self.spare = 1",
    ],
    ids=["a-fifteenth-method", "a-public-attribute"],
)
def test_the_scan_rejects_a_member_the_protocol_does_not_declare(
    violation: str,
) -> None:
    """§39: the shape `final_label` had -- public, on the class, in no contract."""
    declared = classes_in([module_from_source(violation)])["Text2Text"]

    assert public_surface(declared) - set(Modality.__protocol_attrs__)


def test_the_scan_permits_what_is_private() -> None:
    """The rule is about surface: what a method holds for itself is nobody else's business."""
    private = "class Text2Text:\n    def __init__(self):\n        self._encode = None\n\n    def _helper(self):\n        return 1"
    declared = classes_in([module_from_source(private)])["Text2Text"]

    assert public_surface(declared) == set()
