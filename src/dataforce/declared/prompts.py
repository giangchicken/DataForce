"""Prompts are files, not string literals. Read with `read_txt`, filled with `slot_filling`.

A prompt is the measuring instrument, so a change to one has to be reviewable on its
own and nameable in an artifact: votes are cached on `(rid, model, prompt_version)`
and `questions.jsonl` carries a `prompt_version` column, neither of which means
anything if the text lives inside a function nobody diffs.

`prompt_version` *is* the path, relative to `config/prompts` and without the suffix --
`profiles/tool_decision/question.v1`. The folder mirrors `src/dataforce`, so the axis
that owns a prompt owns the folder it sits in, and a version bump is a new file rather
than an edit that silently invalidates a cache.

Reading a template is here; filling one is not. `slot_filling` takes `{{double brace}}`
placeholders and touches no file, so whoever holds the template fills it -- which is how
a stage renders a prompt per record without the engine reading `config/prompts`.
"""

from __future__ import annotations

from pathlib import Path

from agent_toolkit.file_utils import read_txt
from agent_toolkit.string_utils import compute_hash

from dataforce.core.errors import ConfigError

__all__ = ["SUFFIX", "digest", "prompt_path", "read_prompt", "versions"]

SUFFIX = ".txt"


def prompt_path(version: str, *, root: Path) -> Path:
    """Where one template is, by its `prompt_version`. Public for the same reason
    `manifest_path` is: a run records the digest of every policy file it read."""
    path = root / f"{version}{SUFFIX}"
    if not path.is_file():
        raise ConfigError(
            f"no prompt at {path}; the ones that exist: {versions(root=root)}"
        )
    return path


def read_prompt(version: str, *, root: Path) -> str:
    """One prompt template, verbatim, by its `prompt_version`."""
    return read_txt(prompt_path(version, root=root))


def digest(version: str, *, root: Path) -> str:
    """The template's content hash, so a recorded `prompt_version` cannot drift from
    the file it names without the drift being visible."""
    return compute_hash(read_prompt(version, root=root), "sha256")[:12]


def versions(*, root: Path) -> list[str]:
    """Every prompt that exists, as the `prompt_version` strings that name them."""
    return sorted(
        str(path.relative_to(root).with_suffix("")).replace("\\", "/")
        for path in root.rglob(f"*{SUFFIX}")
    )
