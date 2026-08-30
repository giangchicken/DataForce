"""The machinery every other guard stands on, tested — because a bug here is silent.

`tree.py` decides what a module is called and what its imports resolve to. Every rule in this
directory is a filter over that, so a mistake in it does not fail a guard: it makes the guard find
nothing, and a rule that finds nothing reads exactly like a rule nothing violates.

That is not hypothetical. `module_at` named a package's `__init__.py` `dataforce.modalities.__init__`
and resolved its relative imports against that, so `from . import text2text` in a façade came out as
`dataforce.modalities.__init__.text2text` and matched no implementation. I2 and I16 were both blind
to it, and both were green. AGENTS.md: a rule that passes because there is nothing to check is a
rule nobody has tested.
"""

import pytest

from .tree import SRC, imports, module_at, module_from_source

# `from x import y` yields both, so a relative import is checked by the deeper of the two names.
FACADE = "dataforce.modalities"


def test_a_module_is_named_the_way_an_importer_writes_it() -> None:
    """`dataforce.pipeline.flow`, and the package it resolves a relative import against."""
    module = module_at(SRC / "pipeline" / "flow.py")

    assert (module.name, module.package) == (
        "dataforce.pipeline.flow",
        "dataforce.pipeline",
    )


def test_a_package_is_named_the_package_and_not_its_init() -> None:
    """`dataforce.modalities`, both times: for an `__init__.py`, the package *is* the name."""
    module = module_at(SRC / "modalities" / "__init__.py")

    assert (module.name, module.package) == (FACADE, FACADE)


@pytest.mark.parametrize(
    ("source", "reached"),
    [
        ("from . import text2text", f"{FACADE}.text2text"),
        ("from .text2text import Text2Text", f"{FACADE}.text2text"),
        ("from .base import Modality", f"{FACADE}.base"),
        ("import dataforce.modalities.text2text", f"{FACADE}.text2text"),
    ],
    ids=["from-dot", "from-dot-name", "protocol", "absolute"],
)
def test_a_relative_import_in_a_facade_resolves_to_its_sibling(
    source: str, reached: str
) -> None:
    """The resolution the façade rules depend on. One level too high and every one of them passes."""
    facade = module_from_source(source, FACADE, package=FACADE)

    assert reached in {found.module for found in imports(facade)}


def test_a_relative_import_climbing_out_of_a_sub_package_resolves() -> None:
    """`from ..flow import STAGES` inside `pipeline/data_quality/` reaches `pipeline.flow`."""
    stage = module_from_source(
        "from ..flow import STAGES", "dataforce.pipeline.data_quality.pii_check"
    )

    assert "dataforce.pipeline.flow" in {found.module for found in imports(stage)}


def test_every_real_module_resolves_to_a_name_under_the_package() -> None:
    """No module is named `…__init__`, and none escapes `dataforce.`."""
    named = [module_at(path).name for path in sorted(SRC.rglob("*.py"))]

    assert named
    assert not [name for name in named if name.endswith("__init__")]
    assert not [name for name in named if not name.startswith("dataforce")]
