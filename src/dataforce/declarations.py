"""LOGIC · the manifest declarations an axis reads, checked where they are read.

The relationship ``pipeline/params.py`` has to ``params.yaml``, one axis over. A declaration is read
once, at composition, so this is where a wrong *type* is still a ``ConfigError`` (Requirement 43)
rather than a value that quietly truncates twenty thousand records later: ``str()`` turned a list
declared where a name belongs into ``"['a']"``, which is a model nobody has and a key no item
carries, and ``int()`` read ``2.7`` as 2 and ``true`` as 1.

**There were two copies of this, and the argument for them was real.** § *The two axes* says the two
axes share ``name``, ``version`` and ``Part`` *and nothing else*, so a shared reader looked like a
fourth shared thing -- and the first key one axis needed and the other did not would put a profile's
vocabulary in a module the modality imports. What answers that objection is the **signature**: every
function here takes ``*path: str`` and names no key, so there is nothing here for either axis to
learn about the other. The vocabulary stays in the module that means it -- ``EMBEDDING`` and
``LANGUAGE`` in ``text2text/``, ``MAX_CALLS`` and ``ROLES`` in ``tool_decision/`` -- and I25 is what
says so mechanically rather than by intention.

**The directory in the message is read off the manifest.** ``config/profiles/`` where a manifest
names the concept it composes with, ``config/modalities/`` where it is that concept, which is what
``Manifest.modality`` already means. A field saying which directory a manifest came out of would be
a second thing that can disagree with the first.
"""

from collections.abc import Mapping
from typing import Any

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest

# Where each axis's manifests live, as § *Package layout* draws them. Not a key either axis
# declares: which directory a file came out of is the edge's arrangement, not the file's content.
MODALITIES = "config/modalities/"
PROFILES = "config/profiles/"


def declaring_file(manifest: Manifest) -> str:
    """The file a person has to go and edit, named the way the repository lays it out."""
    return f"{PROFILES if manifest.modality else MODALITIES}{manifest.name}.yaml"


def declaration(manifest: Manifest, *path: str) -> Any:
    """One value the manifest declares, or a `ConfigError` naming the path and what is there."""
    reached: Any = manifest.declarations
    for key in path:
        if not isinstance(reached, Mapping) or key not in reached:
            held = sorted(reached) if isinstance(reached, Mapping) else reached
            raise ConfigError(
                f"{declaring_file(manifest)} declares no "
                f"{'.'.join(path)}: {key!r} is missing from {held!r}"
            )
        reached = reached[key]
    return reached


def declared_name(manifest: Manifest, *path: str) -> str:
    """One declared non-empty string, or a `ConfigError` naming the path and what it holds.

    Coercing with `str()` is what this replaced, in both axes and for the same reason: a list
    declared where a name belongs becomes `"['a']"` -- a model nobody has, or a key no item carries
    -- and the run then fails once per record with a message about the *item* rather than about the
    line that was wrong.
    """
    value = declaration(manifest, *path)
    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"{declaring_file(manifest)} declares {'.'.join(path)} as "
            f"{value!r}, which is not a name"
        )
    return value


def declared_count(manifest: Manifest, *path: str) -> int:
    """One declared whole number of one or more, or a `ConfigError` naming what is there.

    `int()` was doing this and doing it silently: `max_calls: 2.7` truncated to 2 and
    `max_calls: true` became 1, so a mistyped ceiling became `maxItems` and
    `label_cardinality_anomaly`'s boundary without anything to read in a diff. `bool` is excluded
    before `int` because `True` *is* an `int` in Python, which is exactly how the `true` case got
    through.
    """
    value = declaration(manifest, *path)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(
            f"{declaring_file(manifest)} declares {'.'.join(path)} as "
            f"{value!r}, which is not a count"
        )
    return value


def declared_roles(manifest: Manifest, *path: str) -> frozenset[str]:
    """The roles a declaration names, or a `ConfigError` for anything that is not a list of them.

    `exclude_roles: system` -- a bare string where a list belongs -- is the slip this exists for.
    `frozenset("system")` is five letters, so no role matches, the instruction turn goes into the
    vector anyway, and nothing anywhere says a word: the run succeeds and every vector is wrong.
    Wrong vectors are invisible and a refused run is not, which is why this raises rather than
    reading a lone string as a one-role list.
    """
    value = declaration(manifest, *path)
    if not isinstance(value, list) or any(not isinstance(role, str) for role in value):
        raise ConfigError(
            f"{declaring_file(manifest)} declares {'.'.join(path)} as "
            f"{value!r}, which is not a list of role names"
        )
    return frozenset(value)
