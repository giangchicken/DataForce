"""adapter · which models this deployment serves, and the resolver that reads them.

A model is served when `config/model/<model name>.json` exists. That directory is the deployment's
-- written after cloning, kept out of the repository by `.gitignore` -- so the list of names is
read off the filesystem rather than declared a second time in a file that could disagree with it.

`agent_toolkit`'s `JsonDirConfigResolver` is the reader, registered once at the composition root.
Nothing here parses one of those files: what a model's config means is the library's business.

Refusing a name nobody serves is here too, because it is the same directory read and there is
nowhere else it could ask. Every route that asks a model has to do it, and has to do it
**before** the first call: a refusal raised after a panel has answered is N model calls paid
for and thrown away.
"""

import os
from pathlib import Path

from agent_toolkit.llm import JsonDirConfigResolver, set_config_resolver

from dataforce.errors import ConfigError

MODEL_DIR = "DATAFORCE_MODEL_DIR"
DEFAULT_MODEL_DIR = "config/model"


def read_model_directory() -> Path:
    """Where the served models' config files are."""
    return Path(os.environ.get(MODEL_DIR) or DEFAULT_MODEL_DIR)


def list_served_models() -> tuple[str, ...]:
    """Every model name this deployment serves, sorted. Empty where the directory is not there."""
    directory = read_model_directory()
    if not directory.is_dir():
        return ()
    return tuple(sorted(path.stem for path in directory.glob("*.json")))


def register_resolver() -> None:
    """Point `resolve_config` at this deployment's model directory."""
    set_config_resolver(JsonDirConfigResolver(read_model_directory()))


def check_served_models(names: tuple[str, ...]) -> None:
    served = list_served_models()
    unserved = tuple(name for name in names if name not in served)
    if unserved:
        raise ConfigError(
            f"not served here: {', '.join(unserved)}. Served: {', '.join(served) or 'nothing'}"
        )
