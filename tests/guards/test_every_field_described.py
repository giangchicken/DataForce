"""I7 · every field of every data class carries a description.

Requirement 1, checked by introspection rather than by reading. For a request or response model
that text is the OpenAPI a caller reads in `/docs`; for the record it is the only place a key's
meaning is written down next to the key. A field with no description is a key whose meaning lives
in someone's head.

**It was vacuous when it was written** -- no module defined a model yet -- and that was the point
of writing it before `record.py` rather than after. What was not vacuous then is the proof below:
the rule is run over synthetic models, and over a synthetic module, so it was known to work before
it had anything to find. `record.py` and `manifest.py` gave it something to find.

**Two halves, because Requirement 1 names two kinds of data class.** Introspection covers a pydantic
field's `description`. The other half is an AST scan for the trailing comment the requirement asks of
"a plain dataclass attribute" -- `Engine`, `ServiceResult` and `Stage` carry theirs by hand, and a
model's introspection cannot see them because a comment is not in the tree. The scan reads every line
a field's declaration spans, not just its first: `Stage.phase` in `flow.py` is a parenthesised
annotation whose comment sits on the line below, and a scan reading one line would have called it
undescribed and been switched off for being wrong.
"""

import ast
import importlib
import pkgutil
from collections.abc import Iterable
from types import ModuleType

import pytest
from pydantic import BaseModel, Field

import dataforce

from .tree import Module, called_name, module_from_source, modules_in, not_exempt

# The two shapes pydantic does not introspect for us, and the ones Requirement 1 asks a comment of.
DATA_CLASS = ("dataclass", "NamedTuple")


def models_defined_in(module: ModuleType) -> list[type[BaseModel]]:
    """Every pydantic model that module defines. One it merely imported belongs to its own module."""
    return [
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == module.__name__
    ]


def dataforce_models() -> list[type[BaseModel]]:
    """Every model the package defines, found by importing all of it."""
    modules = [dataforce] + [
        importlib.import_module(found.name)
        for found in pkgutil.walk_packages(dataforce.__path__, "dataforce.")
    ]
    return [model for module in modules for model in models_defined_in(module)]


def undescribed_fields(models: Iterable[type[BaseModel]]) -> list[str]:
    """Every field with nothing said about it, named so the failure says which one."""
    return [
        f"{model.__module__}.{model.__qualname__}.{name}"
        for model in models
        for name, field in model.model_fields.items()
        if not (field.description or "").strip()
    ]


def test_every_field_the_package_defines_is_described() -> None:
    """I7, over every model in the tree."""
    assert undescribed_fields(dataforce_models()) == []


def test_the_walk_reaches_every_module() -> None:
    """Guards the discovery: a walk that found nothing would make the assertion above vacuous."""
    walked = {
        found.name for found in pkgutil.walk_packages(dataforce.__path__, "dataforce.")
    }

    assert "dataforce.record" in walked
    assert "dataforce.edge.routers.schemas" in walked


def test_the_rule_rejects_a_field_with_no_description() -> None:
    """§39."""

    class Undescribed(BaseModel):
        described: str = Field(..., description="what it is for")
        bare: str

    found = undescribed_fields([Undescribed])

    assert len(found) == 1
    assert found[0].endswith(".Undescribed.bare")


def test_the_rule_rejects_a_description_that_is_only_whitespace() -> None:
    """§39: an empty string satisfies `description=` and says nothing."""

    class Blank(BaseModel):
        hollow: str = Field(..., description="  ")

    assert undescribed_fields([Blank]) != []


def test_the_rule_permits_a_model_whose_fields_are_all_described() -> None:
    """The green case, so the guard is known to be a rule and not a refusal."""

    class Described(BaseModel):
        key: str = Field(..., description="the join key")
        count: int = Field(0, description="how many there were")

    assert undescribed_fields([Described]) == []


def test_the_collection_ignores_a_model_the_module_only_imported(
    tmp_path: object,
) -> None:
    """A model is one module's to describe. Counting it twice would name the wrong module."""
    borrower = ModuleType("borrower")
    owned = type("Owned", (BaseModel,), {"__module__": "borrower"})
    borrowed = type("Borrowed", (BaseModel,), {"__module__": "elsewhere"})
    borrower.__dict__.update({"Owned": owned, "Borrowed": borrowed})

    assert models_defined_in(borrower) == [owned]


def _plain_name(node: ast.expr) -> str:
    """`dataclass` out of `@dataclass`, `@dataclasses.dataclass` or a `NamedTuple` base."""
    if isinstance(node, ast.Call):
        return called_name(node).split(".")[-1]
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.id if isinstance(node, ast.Name) else ""


def _is_a_plain_data_class(node: ast.ClassDef) -> bool:
    """A dataclass or a NamedTuple. A pydantic model is the other half's business."""
    named = [_plain_name(n) for n in [*node.decorator_list, *node.bases]]
    return any(name in DATA_CLASS for name in named)


def uncommented_fields(module: Module) -> list[str]:
    """Every dataclass or NamedTuple field with no comment anywhere in its declaration."""
    found = []
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.ClassDef) or not _is_a_plain_data_class(node):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            spans = module.lines[statement.lineno - 1 : statement.end_lineno]
            if not any("#" in line for line in spans):
                target = ast.unparse(statement.target)
                found.append((statement.lineno, f"{node.name}.{target} has no comment"))
    return not_exempt(module, "I7", found)


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_every_dataclass_field_the_package_defines_is_described(module: Module) -> None:
    """I7's other half, over the tree: `Engine`, `ServiceResult` and `Stage` today."""
    assert uncommented_fields(module) == []


def test_the_scan_looks_at_the_classes_it_is_supposed_to_find() -> None:
    """Guards the selection: a detector that recognised neither shape would pass everything."""
    shapes = (
        "@dataclass\nclass A:\n    a: str  # one\n\n\nclass B(NamedTuple):\n    b: str"
    )

    assert uncommented_fields(module_from_source(shapes)) != []
    assert "B.b" in uncommented_fields(module_from_source(shapes))[0]


@pytest.mark.parametrize(
    "violation",
    [
        "@dataclass\nclass Engine:\n    modality: str",
        "@dataclasses.dataclass(frozen=True)\nclass Engine:\n    modality: str",
        "class Stage(NamedTuple):\n    phase: str",
    ],
    ids=["dataclass", "qualified-and-called", "namedtuple"],
)
def test_the_scan_rejects_a_dataclass_field_with_no_comment(violation: str) -> None:
    """§39, one per spelling of the two shapes."""
    assert uncommented_fields(module_from_source(violation)) != []


@pytest.mark.parametrize(
    "permitted",
    [
        "@dataclass\nclass Engine:\n    modality: str  # the resolved modality",
        "@dataclass\nclass Stage(NamedTuple):\n    phase: (\n        str  # the endpoint\n    )",
        'class Described(BaseModel):\n    key: str = Field(..., description="the join key")',
    ],
    ids=["trailing", "parenthesised-annotation", "a-model-is-the-other-half"],
)
def test_the_scan_permits_what_the_requirement_permits(permitted: str) -> None:
    """A comment anywhere in the declaration, including the line below an open bracket."""
    assert uncommented_fields(module_from_source(permitted)) == []
