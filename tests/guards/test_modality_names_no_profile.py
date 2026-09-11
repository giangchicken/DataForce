"""H-10 · no name in `modalities/` is written in a profile's vocabulary.

`modalities/<modality>/` serves every task of that modality, so a name there that only makes sense
for one of them has given the layer knowledge it cannot have: the next task inherits a parameter it
has nothing to put in.

**The forbidden words are read off the tree, not off a list kept here.** They are the words of the
directories under `profile/`, so adding `profile/text_summarization/` forbids `summarization` in the
modality without anybody remembering to come back and say so. A hand-written list would be a second
copy of which profiles exist, and the copy is the one that goes stale.

**Names only, never prose.** Measured before this guard was written: over the package as it stood,
scanning names found six violations and all six were real -- one `tools` parameter on each of two
sockets, and the third on the arithmetic that calls them. Scanning docstrings as well found two
more, and both were English: `human_review/schema.py` says *the annotation tool*, meaning the
instrument a person labels in. A word is a profile's only where this codebase chose to write it, so
what is read is what this codebase chose: the defined names. Reading the docstring is the other half
of `H-10` and it is a person's job, not this file's.
"""

import ast
import re

import pytest

from .tree import SRC, Module, module_from_source, modules_in, not_exempt

# What a profile owns: the words of its own directory name. `profile/tool_decision/` owns `tool`
# and `decision`, and owning a word means the modality above may not use it.
PROFILE_WORDS = frozenset(
    word
    for directory in (SRC / "profile").iterdir()
    if directory.is_dir() and not directory.name.startswith("_")
    for word in directory.name.split("_")
)


def words_in(name: str) -> frozenset[str]:
    """One name as the words it is made of, singular, whichever case it was written in.

    A trailing `s` goes because `tools` is the plural of a word a profile owns, and the guard that
    misses it is the guard that misses the only violation this codebase actually had. `toolkit`
    keeps its own shape, which is why the split is into words before anything is stripped.
    """
    return frozenset(
        stem.lower().rstrip("s") or stem.lower()
        for part in re.split(r"_+", name)
        for stem in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|\d+", part)
    )


def defined_names(module: Module) -> list[tuple[int, str]]:
    """Every name this module chose, with the line it chose it on."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(module.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.append((node.lineno, node.name))
        elif isinstance(node, ast.ClassDef):
            found.append((node.lineno, node.name))
        elif isinstance(node, ast.arg):
            found.append((node.lineno, node.arg))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            found.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            found.append((node.lineno, node.attr))
    return found


def profile_words_in_names(module: Module) -> list[str]:
    """Every name in that module carrying a word a profile owns, unless a line excuses itself."""
    return not_exempt(
        module,
        "H-10",
        [
            (line, f"`{name}` is written in {', '.join(sorted(owned))} vocabulary")
            for line, name in defined_names(module)
            if (owned := PROFILE_WORDS & words_in(name))
        ],
    )


def test_a_profile_directory_is_what_says_which_words_are_owned() -> None:
    """The list is derived, so this pins that it was derived from something and is not empty."""
    assert "tool" in PROFILE_WORDS
    assert "decision" in PROFILE_WORDS


@pytest.mark.parametrize("module", modules_in("modalities"), ids=lambda m: m.name)
def test_no_modality_name_is_written_in_a_profile_vocabulary(module: Module) -> None:
    """H-10 over the layer it governs. The profile below may say `tool` as often as it likes."""
    assert profile_words_in_names(module) == []


@pytest.mark.parametrize(
    "violation",
    [
        "def predict(self, turns: list[str], tools: list[object]) -> None: ...",
        "def build_tool_catalog(offered: list[object]) -> str: ...",
        "class ToolDecisionPanel: ...",
        "tool_descriptions = ()",
    ],
    ids=["a parameter", "a function", "a class", "a module constant"],
)
def test_a_name_carrying_a_profile_word_is_caught(violation: str) -> None:
    """Red first, in the four places a name gets chosen."""
    source = f'"""logic · a decision."""\n\n\n{violation}\n'
    assert profile_words_in_names(module_from_source(source)) != []


def test_the_same_word_in_prose_is_not_caught() -> None:
    """The measured false positive, kept as the reason this reads names and not lines.

    `the annotation tool` is the instrument a person labels in. A guard that failed here would be
    exempted into uselessness within a week, which is worse than the rule having no check.
    """
    source = '"""shape · what one person\'s answer says, in the tool\'s own words."""\n'
    assert profile_words_in_names(module_from_source(source)) == []


def test_an_annotated_exemption_covers_one_name() -> None:
    """`E-4`: a break is written where the next reader hits it, and excuses that line alone."""
    excused = (
        '"""logic · a decision."""\n\n\n'
        "def predict(tools: list[object]) -> None:"
        "  # guard-exempt: H-10 · the reason · the owner · 2026-09-11\n"
        "    unexcused_tools = ()\n"
    )
    found = profile_words_in_names(module_from_source(excused))
    assert len(found) == 1
    assert "unexcused_tools" in found[0]
