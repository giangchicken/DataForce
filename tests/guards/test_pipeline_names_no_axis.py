"""I2 · `pipeline/` imports no concrete modality and no concrete profile.

Both axes arrive through a registry (Requirement 38). A stage that names ``text2text`` is a stage
that has to be edited when the second modality lands, which is the whole reason the axis is an axis
-- and the registry stops being a seam the moment one caller goes around it.

The list of implementations is not written here. It is the sub-packages beside each ``base.py``,
so registering a second profile puts it under this guard without anyone remembering to.
"""

import pytest

from .tree import (
    Module,
    axis_implementations,
    imports,
    module_from_source,
    modules_in,
    not_exempt,
)


def concrete_axis_findings(module: Module, forbidden: tuple[str, ...]) -> list[str]:
    """Every import in this module that names one of those implementations, or something in it."""
    return not_exempt(
        module,
        "I2",
        [
            (reached.line, f"names the concrete axis {reached.module}")
            for reached in imports(module)
            if reached.module.startswith(forbidden)
        ],
    )


def registered() -> tuple[str, ...]:
    """Every implementation's dotted name, from the tree rather than from a list kept by hand."""
    return tuple(
        f"dataforce.{package.parent.name}.{package.name}"
        for package in axis_implementations()
    )


def test_the_tree_has_implementations_to_be_blind_to() -> None:
    """Guards the discovery, not the code: an empty list would make every scan below vacuous."""
    assert set(registered()) == {
        "dataforce.modalities.text2text",
        "dataforce.profiles.tool_decision",
    }


@pytest.mark.parametrize("module", modules_in("pipeline"), ids=lambda m: m.name)
def test_no_pipeline_module_names_a_concrete_axis(module: Module) -> None:
    """I2, over every module of the flow."""
    assert concrete_axis_findings(module, registered()) == []


@pytest.mark.parametrize(
    "violation",
    [
        "from dataforce.profiles.tool_decision import ToolDecision",
        "from dataforce.profiles import tool_decision",
        "import dataforce.modalities.text2text",
        "from dataforce.modalities.text2text.schema import TextDetector",
    ],
    ids=["from-impl", "from-axis", "import", "deep"],
)
def test_the_scan_rejects_a_module_that_names_an_implementation(violation: str) -> None:
    """§39: proved red against a synthetic violation, one per spelling of the import."""
    assert concrete_axis_findings(module_from_source(violation), registered()) != []


@pytest.mark.parametrize(
    "permitted",
    [
        "from dataforce.profiles.base import Profile",
        "from dataforce.modalities.base import Modality",
        "from dataforce.engine import Engine",
    ],
    ids=["profile-base", "modality-base", "engine"],
)
def test_the_scan_permits_the_protocols_the_registry_hands_over(permitted: str) -> None:
    """The rule is about implementations. Naming the protocol is the point of having one."""
    assert concrete_axis_findings(module_from_source(permitted), registered()) == []
