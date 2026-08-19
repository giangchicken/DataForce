"""Prompts live in files, and the guard that keeps them there.

Core requirement 45 says prompts are files read with `read_txt` and filled with
`slot_filling`. The first version of this profile put its question in a module
constant instead, which is how a prompt gets edited without a review and how a
`prompt_version` in an artifact stops naming the text that produced it. The AST scan
below is what catches that, so it is proved against source rather than trusted.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from conftest import REPO_ROOT, SOURCE_ROOT, parsed_sources

from dataforce.profiles.tool_decision import TOOL_DECISION
from dataforce.shared import prompts
from dataforce.shared.errors import ConfigError

ROOT = REPO_ROOT / prompts.PROMPTS

MARKERS = (
    "{trigger}",
    "{hold_other}",
    "{hold_missing}",
    "{constraint}",
    "{turn_trigger}",
)


def _docstrings(tree: ast.Module) -> set[int]:
    """Which string constants are documentation. Prose about placeholders is prose."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def templates(tree: ast.Module) -> list[str]:
    """String constants that carry a `slot_filling` placeholder -- i.e. templates."""
    documentation = _docstrings(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "{{" in node.value
        and "}}" in node.value
        and id(node) not in documentation
    ]


def test_no_module_holds_a_prompt_template() -> None:
    scanned = 0
    for path, tree in parsed_sources():
        scanned += 1
        found = templates(tree)
        assert not found, (
            f"{path.relative_to(SOURCE_ROOT)} holds a template: {found!r} -- "
            f"prompts belong under {prompts.PROMPTS}"
        )
    assert scanned, "no module was scanned -- this test would pass vacuously"


def test_the_check_catches_the_literal_it_exists_to_catch() -> None:
    offending = ast.parse('_Q = "Tập trung vào: {{focus}}"\n')
    assert templates(offending) == ["Tập trung vào: {{focus}}"]

    innocent = ast.parse('QUESTION_PROMPT = "profiles/tool_decision/question.v1"\n')
    assert templates(innocent) == []

    a_marker_is_not_a_placeholder = ast.parse('M = "{trigger} khách hàng"\n')
    assert templates(a_marker_is_not_a_placeholder) == []

    prose = ast.parse('"""slot_filling takes {{double brace}} placeholders."""\n')
    assert templates(prose) == []


# --- the loader --------------------------------------------------------------


def test_every_prompt_on_disk_loads_by_its_version() -> None:
    found = prompts.versions(root=ROOT)

    assert found, f"no prompt files under {ROOT}"
    for version in found:
        assert prompts.load(version, root=ROOT).strip()


def test_the_prompt_folder_mirrors_the_two_axes() -> None:
    """A prompt is owned by the axis that owns the folder it sits in."""
    for version in prompts.versions(root=ROOT):
        assert version.split("/")[0] in ("profiles", "modalities"), version


def test_a_version_names_a_file_and_a_missing_one_says_what_exists() -> None:
    with pytest.raises(ConfigError, match="profiles/tool_decision/question.v1"):
        prompts.load("profiles/tool_decision/question.v99", root=ROOT)


def test_the_profile_asks_with_a_prompt_that_exists() -> None:
    """The version it declares, not a constant a test happens to agree with."""
    assert TOOL_DECISION.question_prompt in prompts.versions(root=ROOT)


def test_rendering_leaves_the_marker_dsl_alone() -> None:
    """Single braces are the DSL's; `slot_filling` only fills doubled ones."""
    focus = " ".join(MARKERS)

    rendered = prompts.render(
        TOOL_DECISION.question_prompt, {"focus": focus}, root=ROOT
    )

    for marker in MARKERS:
        assert marker in rendered
    assert "{{focus}}" not in rendered


def test_an_unknown_placeholder_is_left_in_place_rather_than_blanked(
    tmp_path: Path,
) -> None:
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "probe.v1.txt").write_text(
        "{{known}} và {{unknown}}", encoding="utf-8"
    )

    assert (
        prompts.render("profiles/probe.v1", {"known": "a"}, root=tmp_path)
        == "a và {{unknown}}"
    )


def test_the_digest_names_the_text_and_moves_when_it_moves(tmp_path: Path) -> None:
    """So a `prompt_version` recorded in an artifact cannot drift from its file."""
    (tmp_path / "profiles").mkdir()
    template = tmp_path / "profiles" / "probe.v1.txt"
    template.write_text("một", encoding="utf-8")
    before = prompts.digest("profiles/probe.v1", root=tmp_path)

    template.write_text("hai", encoding="utf-8")

    assert prompts.digest("profiles/probe.v1", root=tmp_path) != before
    assert len(before) == 12
