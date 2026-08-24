"""LOGIC · the params.yaml declarations a stage reads, checked where they are read.

Requirement 27 and P25: no stage holds a number. Every threshold and every switch is a line in
``params.yaml``, which is committed, reviewable and recorded by digest in the run manifest -- so a
change to one is attributable and a run that used the old value stays identifiable.
``Engine.thresholds`` is that file, parsed, and nothing had read it until Phase 4.

What a reader here adds is the **type**. A declaration is read before any record, so a wrong one is
a ``ConfigError`` at that point rather than a value that quietly truncates twenty thousand records
later (Requirement 43) -- the same rule both axes' manifest readers hold, and one module here
because ``pipeline/`` has no reason to keep three copies of it. The axes keep their own copies and
their own docstrings say why: they may share nothing with each other, and these modules may.

**An absent declaration is ordinary, and a wrong one is not.** ``params.yaml`` ships with every
corpus-supplied value empty on purpose -- *an empty key is not an oversight, it is a question nobody
has answered yet* -- so ``declaration`` returns ``None`` for a key nobody has answered and the
reader that cannot work without a value is the one that says so.
"""

from collections.abc import Mapping
from typing import Any

from dataforce.engine import Engine
from dataforce.errors import ConfigError


def declaration(engine: Engine, *path: str) -> Any:
    """One value `params.yaml` declares at that path, or None where it declares nothing there."""
    reached: Any = engine.thresholds
    for key in path:
        if not isinstance(reached, Mapping) or key not in reached:
            return None
        reached = reached[key]
    return reached


def declared_switch(engine: Engine, *path: str) -> bool:
    """Whether `params.yaml` turned that switch on. An absent one is off.

    Off by default is Requirement 21's whole mechanism: `enable_redact: false` means `pii_check`
    reports and leaves content untouched, the downstream personal-data scan then fails, and nothing
    ships — so turning it on has to be an edit to a committed file, which is what makes the decision
    attributable.

    **Anything that is not `true` or `false` raises rather than being read as truthy.** `bool("no")`
    is `True`, so a coerced switch turns redaction *on* for a value written to turn it off, and the
    run that rewrote twenty thousand records is the one that tells you. T46 learned this on
    `exclude_roles` for a smaller price.
    """
    value = declaration(engine, *path)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ConfigError(
            f"params.yaml declares {'.'.join(path)} as {value!r}, which is not true or false"
        )
    return value


def declared_digest(engine: Engine, *path: str) -> str:
    """The digest `params.yaml` declares at that path, or `""` where no corpus is declared yet.

    Only the type is checked here and not the shape: a digest of the wrong length can never match
    a real one, so the comparison at the caller already reports it -- with both values, which is
    what a person needs -- and a second rule about hex characters would prevent no failure.
    """
    value = declaration(engine, *path)
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise ConfigError(
            f"params.yaml declares {'.'.join(path)} as {value!r}, which is not a digest"
        )
    return value
