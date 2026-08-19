"""Prompts are files, not string literals. Read with `read_txt`, filled with `slot_filling`.

A prompt is the measuring instrument, so a change to one has to be reviewable on its
own and nameable in an artifact: votes are cached on `(rid, model, prompt_version)`
and `questions.jsonl` carries a `prompt_version` column, neither of which means
anything if the text lives inside a function nobody diffs.

`prompt_version` *is* the path, relative to `config/prompts` and without the suffix --
`profiles/tool_decision/question.v1`. The folder mirrors `src/dataforce`, so the axis
that owns a prompt owns the folder it sits in, and a version bump is a new file rather
than an edit that silently invalidates a cache.

`slot_filling` takes `{{double brace}}` placeholders, which is why the marker DSL's
single braces pass through untouched: `{trigger}` is not a placeholder to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_txt
from agent_toolkit.string_utils import compute_hash, slot_filling

from dataforce.shared.errors import ConfigError

__all__ = ["PROMPTS", "SUFFIX", "digest", "load", "render", "versions"]

PROMPTS = Path("config/prompts")
SUFFIX = ".txt"


def _path(version: str, root: Path) -> Path:
    path = root / f"{version}{SUFFIX}"
    if not path.is_file():
        raise ConfigError(
            f"no prompt at {path}; the ones that exist: {versions(root=root)}"
        )
    return path


def load(version: str, *, root: Path = PROMPTS) -> str:
    """One prompt template, verbatim, by its `prompt_version`."""
    return read_txt(_path(version, root))


def render(version: str, values: dict[str, Any], *, root: Path = PROMPTS) -> str:
    """One prompt, filled. An unknown placeholder is left in place, not blanked."""
    return slot_filling(load(version, root=root), values)


def digest(version: str, *, root: Path = PROMPTS) -> str:
    """The template's content hash, so a recorded `prompt_version` cannot drift from
    the file it names without the drift being visible."""
    return compute_hash(load(version, root=root), "sha256")[:12]


def versions(*, root: Path = PROMPTS) -> list[str]:
    """Every prompt that exists, as the `prompt_version` strings that name them."""
    return sorted(
        str(path.relative_to(root).with_suffix("")).replace("\\", "/")
        for path in root.rglob(f"*{SUFFIX}")
    )
