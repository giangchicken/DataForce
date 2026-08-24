"""I16 · nothing above an axis implementation names one — not `base.py`, not the façade.

The same mechanism as I2 and a different reason, which is why it is a different module. I2 keeps a
*consumer* axis-blind so a second implementation costs nothing. This keeps everything *above* an
implementation from depending on it -- a cycle, and an abstraction that has quietly become a
description of its single implementation (P18).

**Two modules per axis, because I2 cannot see through a re-export.** I2 reads imports, so it catches
a stage that writes ``dataforce.modalities.text2text``. It permits
``from dataforce.modalities.base import Modality``, which is the point of having a protocol. But a
façade that re-exports its implementations makes *any* import of the axis load them, and no scan of
the consumer would show it: the consumer's line is clean and the coupling is one hop away. So the
rule is enforced where the hop is -- on ``base.py`` and on ``__init__.py``, the only two modules that
sit above an implementation.

Its own axis only. `profiles/base.py` naming `dataforce.modalities.text2text` is I2's kind of
mistake, not this one, and would be caught where the profile actually uses it.
"""

from pathlib import Path

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

AXES = ("modalities", "profiles")
ABOVE = ("__init__.py", "base.py")


def own_axis_findings(module: Module, axis: str) -> list[str]:
    """Every import in that module naming an implementation of that same axis."""
    siblings = tuple(
        f"dataforce.{axis}.{package.name}"
        for package in axis_implementations()
        if package.parent.name == axis
    )
    return not_exempt(
        module,
        "I16",
        [
            (reached.line, f"the {axis} axis names its own {reached.module}")
            for reached in imports(module)
            if reached.module.startswith(siblings)
        ],
    )


def modules_above_an_implementation() -> list[tuple[str, Path]]:
    """The two modules per axis that a consumer reaches without naming an implementation."""
    return [(axis, SRC / axis / name) for axis in AXES for name in ABOVE]


def test_the_scan_has_all_four_modules_to_look_at() -> None:
    """Guards the selection: the façade was the half this rule did not cover, and missed."""
    looked_at = {(axis, path.name) for axis, path in modules_above_an_implementation()}

    assert looked_at == {(axis, name) for axis in AXES for name in ABOVE}


@pytest.mark.parametrize(
    ("axis", "path"),
    modules_above_an_implementation(),
    ids=lambda v: getattr(v, "name", v),
)
def test_nothing_above_an_implementation_names_one(axis: str, path: Path) -> None:
    """I16, over both protocols and both façades."""
    assert own_axis_findings(module_at(path), axis) == []


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


@pytest.mark.parametrize(
    ("axis", "violation"),
    [
        ("modalities", "from . import text2text"),
        ("modalities", "from .text2text import Text2Text"),
        ("profiles", "from . import tool_decision"),
    ],
    ids=["re-export", "re-export-name", "profile-re-export"],
)
def test_the_scan_rejects_a_facade_that_re_exports_its_implementation(
    axis: str, violation: str
) -> None:
    """P29, the hole this rule grew to cover: a relative re-export, which is how a façade writes it.

    `from . import text2text` in `modalities/__init__.py` makes every importer of the axis load the
    implementation. Nothing named it, so I2 sees a clean consumer and the registry becomes a fiction.
    """
    facade = module_from_source(
        violation, f"dataforce.{axis}", package=f"dataforce.{axis}"
    )

    assert own_axis_findings(facade, axis) != []


@pytest.mark.parametrize("axis", AXES)
def test_the_scan_permits_a_facade_that_re_exports_its_protocol(axis: str) -> None:
    """The rule is about implementations. Re-exporting `base.py` is what a façade is for."""
    facade = module_from_source(
        "from .base import Modality", f"dataforce.{axis}", package=f"dataforce.{axis}"
    )

    assert own_axis_findings(facade, axis) == []


def test_the_scan_leaves_the_other_axis_to_the_rule_that_owns_it() -> None:
    """I16 is about a cycle. A profile naming a concrete modality is I2's finding, not this one."""
    crossing = "from dataforce.modalities.text2text import Text2Text"

    assert own_axis_findings(module_from_source(crossing), "profiles") == []
