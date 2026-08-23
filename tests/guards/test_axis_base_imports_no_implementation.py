"""I16 · no axis `base.py` imports an implementation of its own axis.

The same mechanism as I2 and a different reason, which is why it is a different module. I2 keeps a
*consumer* axis-blind so a second implementation costs nothing. This keeps the *protocol* from
depending on the thing that satisfies it -- a cycle, and an abstraction that has quietly become a
description of its single implementation (P18).

Its own axis only. `profiles/base.py` naming `dataforce.modalities.text2text` is I2's kind of
mistake, not this one, and would be caught where the profile actually uses it.
"""

import pytest

from .tree import (
    SRC,
    Module,
    axis_implementations,
    imports,
    module_at,
    module_from_source,
    not_exempt,
)


def own_axis_findings(module: Module, axis: str) -> list[str]:
    """Every import in that axis's `base.py` naming an implementation of that same axis."""
    siblings = tuple(
        f"dataforce.{axis}.{package.name}"
        for package in axis_implementations()
        if package.parent.name == axis
    )
    return not_exempt(
        module,
        "I16",
        [
            (
                reached.line,
                f"the {axis} protocol names its own implementation {reached.module}",
            )
            for reached in imports(module)
            if reached.module.startswith(siblings)
        ],
    )


@pytest.mark.parametrize("axis", ["modalities", "profiles"])
def test_neither_protocol_names_an_implementation_of_itself(axis: str) -> None:
    """I16, over both `base.py` modules."""
    assert own_axis_findings(module_at(SRC / axis / "base.py"), axis) == []


@pytest.mark.parametrize(
    ("axis", "violation"),
    [
        ("modalities", "from dataforce.modalities.text2text import Text2Text"),
        (
            "modalities",
            "from dataforce.modalities.text2text.schema import TextDetector",
        ),
        ("profiles", "from dataforce.profiles.tool_decision import ToolDecision"),
    ],
    ids=["modality", "modality-deep", "profile"],
)
def test_the_scan_rejects_a_protocol_that_names_its_implementation(
    axis: str, violation: str
) -> None:
    """P29: proved red against a synthetic violation."""
    assert own_axis_findings(module_from_source(violation), axis) != []


def test_the_scan_leaves_the_other_axis_to_the_rule_that_owns_it() -> None:
    """I16 is about a cycle. A profile naming a concrete modality is I2's finding, not this one."""
    crossing = "from dataforce.modalities.text2text import Text2Text"

    assert own_axis_findings(module_from_source(crossing), "profiles") == []
