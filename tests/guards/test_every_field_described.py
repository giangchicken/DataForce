"""I7 · every field of every data class carries a description.

Requirement 1, checked by introspection rather than by reading. For a request or response model
that text is the OpenAPI a caller reads in `/docs`; for the record it is the only place a key's
meaning is written down next to the key. A field with no description is a key whose meaning lives
in someone's head.

**This guard is vacuous over the tree today** -- no module defines a model yet -- and that is the
point of writing it now rather than after `record.py`. What is not vacuous is the proof below: the
rule is run over synthetic models, and over a synthetic module, so it is known to work before it
has anything to find.
"""

import importlib
import pkgutil
from collections.abc import Iterable
from types import ModuleType

from pydantic import BaseModel, Field

import dataforce


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
    """P29."""

    class Undescribed(BaseModel):
        described: str = Field(..., description="what it is for")
        bare: str

    found = undescribed_fields([Undescribed])

    assert len(found) == 1
    assert found[0].endswith(".Undescribed.bare")


def test_the_rule_rejects_a_description_that_is_only_whitespace() -> None:
    """P29: an empty string satisfies `description=` and says nothing."""

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
