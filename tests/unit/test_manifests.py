"""Identity is declared, and the guard that keeps it declared.

`producer` stamps `name@version` for both axes onto every record, so those two strings
are claims about how a dataset was made. The first version of this profile assigned
them in the class body, where a bump is an edit nobody reviews and nothing ties the
number to the artifacts it appears in. The AST scan below is what catches that.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from conftest import CONFIG, SOURCE_ROOT, TEXT, TOOL_DECISION

from dataforce.declared import manifest
from dataforce.shared.errors import ConfigError

DECLARED = ("name", "version", "modality")
GENERIC = frozenset({"__init__", "base", "registry"})


def concrete_modules() -> list[Path]:
    """Every module belonging to a concrete implementation of either axis."""
    found: list[Path] = []
    for axis in manifest.AXES:
        for child in sorted((SOURCE_ROOT / axis).iterdir()):
            if child.stem in GENERIC or child.stem.startswith("_"):
                continue
            found.extend(sorted(child.rglob("*.py")) if child.is_dir() else [child])
    return found


def class_level_identity(tree: ast.Module) -> list[str]:
    """Assignments like `version = "1"` in a class body -- identity, hardcoded.

    A bare annotation carries no value: `name: str` in a dataclass declares a field,
    which is the opposite of hardcoding one.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                targets = statement.targets
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                targets = [statement.target]
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id in DECLARED:
                    found.append(f"{node.name}.{target.id}")
    return found


def test_no_implementation_hardcodes_its_own_identity() -> None:
    modules = concrete_modules()

    assert modules, (
        "no concrete implementation was scanned -- this would pass vacuously"
    )
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = class_level_identity(tree)
        assert not found, (
            f"{path.relative_to(SOURCE_ROOT)} assigns {found} in a class body; "
            f"identity belongs in {CONFIG.name}/<axis>/<name>.yaml"
        )


def test_the_check_catches_the_assignment_it_exists_to_catch() -> None:
    offending = ast.parse('class P:\n    name = "tool_decision"\n    version = "1"\n')
    assert class_level_identity(offending) == ["P.name", "P.version"]

    annotated = ast.parse('class P:\n    modality: str = "text"\n')
    assert class_level_identity(annotated) == ["P.modality"]

    innocent = ast.parse(
        "class P:\n    def __init__(self, m):\n        self.name = m.name\n"
    )
    assert class_level_identity(innocent) == []


# --- what the two axes declare -----------------------------------------------


def test_both_implementations_are_what_their_manifests_say() -> None:
    profile = manifest.read_manifest(
        manifest.manifest_path("profiles", "tool_decision", root=CONFIG)
    )
    modality = manifest.read_manifest(
        manifest.manifest_path("modalities", "text", root=CONFIG)
    )

    assert (TOOL_DECISION.name, TOOL_DECISION.version) == (
        profile.name,
        profile.version,
    )
    assert (TEXT.name, TEXT.version) == (modality.name, modality.version)
    assert TOOL_DECISION.modality == modality.name


def test_a_version_must_be_a_string_because_it_is_not_a_number(tmp_path: Path) -> None:
    """`version: 1` unquoted is an int in YAML, and `text@1.0` is a different stamp."""
    (tmp_path / "modalities").mkdir()
    probe = tmp_path / "modalities" / "probe.yaml"
    probe.write_text("name: probe\nversion: 1\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="not a number"):
        manifest.read_manifest(probe)


def test_a_manifest_cannot_be_copied_and_left_claiming_the_old_name(
    tmp_path: Path,
) -> None:
    (tmp_path / "profiles").mkdir()
    copied = tmp_path / "profiles" / "copied.yaml"
    copied.write_text('name: original\nversion: "1"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="filename is its identity"):
        manifest.read_manifest(copied)


def test_a_missing_manifest_names_the_ones_that_exist() -> None:
    with pytest.raises(ConfigError, match="tool_decision"):
        manifest.manifest_path("profiles", "nonexistent", root=CONFIG)


def test_a_missing_declaration_names_what_the_manifest_does_hold() -> None:
    declared = manifest.read_manifest(
        manifest.manifest_path("profiles", "tool_decision", root=CONFIG)
    )

    with pytest.raises(ConfigError, match="modality"):
        declared.require("nothing_declares_this")


def test_there_are_exactly_two_axes() -> None:
    with pytest.raises(ConfigError, match="there are two"):
        manifest.manifest_path("stages", "load", root=CONFIG)
