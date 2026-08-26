"""LOGIC · config/<axis>/*.yaml, params.yaml and prompts into declarations.

Every policy file it reads reaches the run manifest with its digest, so a changed threshold or a
changed prompt is visible in a diff rather than only in an output (Requirement 45).

**Every reader returns a ``Declared``**, so there is no way to read a file here without its digest
coming back beside what it said. The alternative was a pair of readers -- one for the value, one for
the digest -- and a composition root that remembers to call both; Requirement 45 says the manifest
records *every* policy file, and a rule kept by remembering is a rule that is eventually not
remembered (P16: the digest and the value have one writer).

**The path a ``Declared`` carries is the layout's, not the deployment's.** ``config_root`` may point
anywhere -- a temporary directory in a test, an absolute path in a container -- and a run manifest
keyed by where the checkout happened to sit would differ between two machines running one commit,
which is I14 failing for a reason that is not a configuration change. So the key is built from what
the file *is* -- ``config/profiles/tool_decision.yaml`` -- and ``params.yaml`` is recorded under its
own filename, which is the one part a caller may really vary.

**A file that is not there is a ``ConfigError``, not an empty declaration.** ``read_yaml`` answers
``{}`` for a file it cannot read and ``read_txt`` answers ``""``. That is the right default for a
tool reading a corpus and the wrong one for a run's own configuration: a missing ``params.yaml``
read as ``{}`` is an engine that holds no thresholds and says nothing about it, and P23 wants a
declaration that is missing to stop the run before the first record. So the path is checked here,
before the library is asked.

**Two reads per YAML file, on purpose.** ``agent-toolkit`` owns YAML (I6) and parses from a path, so
the text the digest is over is read separately from the parse. Four small files once per run is the
price of the digest being over the file rather than over what was recovered from it -- a reviewed
comment moved is a policy file changed, and a run manifest that could not see that would be saying
two runs were configured the same when a human had changed the reasoning behind a number.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

from agent_toolkit.file_utils import read_txt, read_yaml
from agent_toolkit.string_utils import compute_hash
from pydantic import ValidationError

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest

# What the layout calls these, whatever directory a deployment points at. § *Package layout* draws
# the same three names, and the run manifest records a file under the one it is drawn with.
CONFIG = "config"
PARAMS = "params.yaml"
MODALITIES = "modalities"
PROFILES = "profiles"
PROMPTS = "prompts"
YAML = ".yaml"
TEMPLATE = ".txt"

# The three keys `Manifest` routes itself. Everything else in the file is a declaration, kept
# verbatim for the axis implementation that knows what it means (`manifest.py`).
IDENTITY = ("name", "version", "modality")

# Where a profile names the question an annotator is asked. The one manifest key the edge reads
# rather than an axis: the profile is handed the template *string*, because no engine module opens
# a file, so the name has to be resolved by something holding a path.
QUESTION = ("prompts", "question")


class Declared[Declaration](NamedTuple):
    """What one policy file says, and what a run manifest records about the file it said it in."""

    declares: (
        Declaration  # the parsed declaration: a manifest, the thresholds, a template
    )
    path: str  # what to call the file in a run manifest, in the layout's terms
    digest: str  # over the file's own text, so a reviewed line moved is a policy file changed


def policy_text(path: Path, recorded_as: str) -> Declared[str]:
    """One policy file's text, and the digest a run manifest records it by.

    Both refusals are about the same default. The library answers `""` and `{}` for a file it cannot
    read, so *absent*, *unreadable* and *declares nothing* arrive here as one value -- and a run
    configured by none of the three is a run nobody can reproduce.
    """
    if not path.is_file():
        raise ConfigError(
            f"{recorded_as} is what this run reads, and there is no file at {path}"
        )
    text = read_txt(path)
    if not text.strip():
        raise ConfigError(
            f"{recorded_as} is empty; a run is configured by what it declares, not by defaults"
        )
    return Declared(text, recorded_as, compute_hash(text))


def read_manifest(config_root: Path, axis: str, name: str) -> Declared[Manifest]:
    """One axis's declaration, parsed, with the digest of the file that carried it.

    Requirement 40's check lands here: the filename is the identity, and only something holding a
    path can see a filename. A `name:` that disagrees with it is refused rather than preferred --
    a run resolves both axes by the same string, so a file that answers to two names is a file that
    is registered under one and looked up under the other.

    `ValidationError` is turned into a `ConfigError` naming the file. Requirement 43 permits one
    exception out of this codebase and pydantic's carries no path, which is the first thing a person
    reading it needs.
    """
    path = config_root / axis / f"{name}{YAML}"
    file = policy_text(path, f"{CONFIG}/{axis}/{name}{YAML}")
    declared = read_yaml(path)
    if not isinstance(declared, Mapping):
        raise ConfigError(f"{file.path} holds {declared!r}, which is not a declaration")
    try:
        manifest = Manifest.model_validate(
            {
                "name": declared.get("name"),
                "version": declared.get("version"),
                "modality": declared.get("modality"),
                "declarations": {
                    key: value for key, value in declared.items() if key not in IDENTITY
                },
            }
        )
    except ValidationError as wrong:
        raise ConfigError(f"{file.path} is not a manifest: {wrong}") from wrong
    if manifest.name != name:
        raise ConfigError(
            f"{file.path} declares name {manifest.name!r}; the filename is the identity "
            "(Requirement 40) and a run resolves an axis by one string, not two"
        )
    return Declared(manifest, file.path, file.digest)


def read_thresholds(params: Path) -> Declared[Mapping[str, Any]]:
    """Every number the pipeline reads, parsed, with the digest that makes a change attributable.

    Recorded under the file's own name rather than a fixed one: a deployment may point at
    `pilot.yaml`, and which file was read is a fact a run manifest is for. Where the checkout sits
    is not, so the directory is left out.
    """
    file = policy_text(params, params.name)
    declared = read_yaml(params)
    if not isinstance(declared, Mapping):
        raise ConfigError(
            f"{params.name} holds {declared!r}, which is not a set of thresholds"
        )
    return Declared(declared, file.path, file.digest)


def read_question_template(config_root: Path, profile: Manifest) -> Declared[str]:
    """What an annotator is asked, by the name the profile's manifest gives it.

    The name is read here and the file is resolved here, so a profile that declares a template
    nobody wrote fails at composition rather than asking twenty thousand people an empty question.
    Versioned in the filename (`question.v2`), which is what puts a reworded prompt in a diff and
    its digest in the run manifest.
    """
    prompts = profile.declarations.get(QUESTION[0])
    named = prompts.get(QUESTION[1]) if isinstance(prompts, Mapping) else None
    if not isinstance(named, str) or not named:
        raise ConfigError(
            f"{CONFIG}/{PROFILES}/{profile.name}{YAML} declares {'.'.join(QUESTION)} as "
            f"{named!r}, which is not the name of a template under {CONFIG}/{PROMPTS}/"
        )
    return policy_text(
        config_root / PROMPTS / f"{named}{TEMPLATE}",
        f"{CONFIG}/{PROMPTS}/{named}{TEMPLATE}",
    )
