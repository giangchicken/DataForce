"""adapter · which models this deployment serves, and the resolver that reads them.

A model is served when `config/model/<model name>.json` exists. That directory is the deployment's
-- written after cloning, kept out of the repository by `.gitignore` -- so the list of names is
read off the filesystem rather than declared a second time in a file that could disagree with it.

`agent_toolkit`'s `JsonDirConfigResolver` is the reader, registered once at the composition root.
Nothing here parses one of those files: what a model's config means is the library's business.
"""

import os
from pathlib import Path

from agent_toolkit.llm import JsonDirConfigResolver, set_config_resolver

MODEL_DIR = "DATAFORCE_MODEL_DIR"
DEFAULT_MODEL_DIR = "config/model"


def model_directory() -> Path:
    """Where the served models' config files are."""
    return Path(os.environ.get(MODEL_DIR) or DEFAULT_MODEL_DIR)


def served_models() -> tuple[str, ...]:
    """Every model name this deployment serves, sorted. Empty where the directory is not there."""
    directory = model_directory()
    if not directory.is_dir():
        return ()
    return tuple(sorted(path.stem for path in directory.glob("*.json")))


def register_resolver() -> None:
    """Point `resolve_config` at this deployment's model directory."""
    set_config_resolver(JsonDirConfigResolver(model_directory()))
