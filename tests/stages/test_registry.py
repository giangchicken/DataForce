"""Requirement 39: a registry is instance state, and one name is registered once.

Beside `test_record.py` for the reason its docstring gives. The `Engine` half of T9 has no
behaviour to prove here -- that it opens nothing is I1's AST scan, and that it cannot be edited
after `edge/bootstrap.py` builds it is the last test below.

The doubles are enough of an axis to be *stored*: a registry holds implementations and never calls
one, so a double carrying only the identity its manifest would give it is the honest fixture. A
double that satisfies all six or fifteen members is T12's and T13's business.
"""

import pytest

from dataforce.engine import Engine, Registry
from dataforce.errors import ConfigError


class AnAxisImplementation:
    """A stand-in for either axis: the two things a registry reads off one, and nothing else."""

    def __init__(self, name: str, version: str = "1") -> None:
        self.name = name
        self.version = version


def a_registry_holding(*names: str) -> Registry:
    """One registry with those modalities registered, and a profile of the same name in the other
    axis, so every test below runs against a registry where both halves are populated."""
    registry = Registry()
    for name in names:
        registry.register_modality(name, AnAxisImplementation(name))  # type: ignore[arg-type]
        registry.register_profile(name, AnAxisImplementation(name))  # type: ignore[arg-type]
    return registry


def test_two_registries_in_one_process_hold_different_implementations() -> None:
    """Requirement 39. A module-level dict would make this pass by accident and fail by order."""
    one = a_registry_holding("text2text")
    another = a_registry_holding("speech2text")

    assert one.modality("text2text").name == "text2text"
    with pytest.raises(ConfigError):
        another.modality("text2text")


def test_the_two_axes_are_separate_namespaces() -> None:
    """A name is unique within the `config/<axis>/` directory it was read from, and no further."""
    registry = a_registry_holding("text2text")

    assert registry.profile("text2text").name == "text2text"


@pytest.mark.parametrize("axis", ["modality", "profile"], ids=["modality", "profile"])
def test_a_second_implementation_of_one_name_is_refused(axis: str) -> None:
    """Requirement 39's other half: registering over the first is silent, and this is not."""
    registry = a_registry_holding("text2text")
    register = getattr(registry, f"register_{axis}")

    with pytest.raises(ConfigError, match="registered"):
        register("text2text", AnAxisImplementation("text2text"))


def test_an_unknown_name_is_told_which_names_there_are() -> None:
    """§ *Error Behavior*: `ConfigError` listing the registered ones."""
    registry = a_registry_holding("text2text", "speech2text")

    with pytest.raises(ConfigError, match="speech2text, text2text"):
        registry.modality("image2text")


def test_an_empty_registry_says_none() -> None:
    """The same sentence with nothing in it, because "registered: " reads as a bug in the message."""
    with pytest.raises(ConfigError, match="none"):
        Registry().profile("tool_decision")


def test_an_engine_cannot_be_edited_after_the_composition_root_built_it() -> None:
    """A pair that changes mid-run is a run whose records disagree about what produced them."""
    registry = a_registry_holding("text2text")
    engine = Engine(
        modality=registry.modality("text2text"),
        profile=registry.profile("text2text"),
        registry=registry,
        thresholds={"enable_redact": False},
        policy_digests={"params.yaml": "a1b2c3d4"},
    )

    with pytest.raises(AttributeError):
        engine.thresholds = {}  # type: ignore[misc]
