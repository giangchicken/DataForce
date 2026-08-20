"""What an implementation *is*, declared rather than assigned.

A modality and a profile each stamp their `name@version` onto every record they touch,
through `producer`. That makes the version a claim about how a dataset was made, and a
claim edited as a class attribute is one no review ever sees. So identity is a line in
`config/<axis>/<name>.yaml`, next to the other things about an implementation that are
declarations and not behaviour: which modality a profile composes with, which prompts
it asks, what its source is shaped like, and what that source's field names mean.

Only the shape is here. Reading one out of a file is `declared/manifest.py`'s job, and
the split is what lets both axes be handed a parsed declaration instead of a path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dataforce.shared.errors import ConfigError

__all__ = ["Manifest"]


@dataclass(frozen=True)
class Manifest:
    """One implementation's declaration. `declared` is the rest of the file, verbatim."""

    name: str
    version: str
    declared: Mapping[str, Any]

    def require(self, key: str) -> Any:
        """One declared value, or an error naming what the file does hold."""
        try:
            return self.declared[key]
        except KeyError:
            raise ConfigError(
                f"{self.name}: nothing declares {key!r}; the manifest holds "
                f"{sorted(self.declared)}"
            ) from None
