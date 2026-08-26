"""TOOL · the one place a record file, metrics.json or a run manifest is read or written.

Corpus-level numbers are a fold here, for reading -- never computed by a service and never
compared against a threshold that stops anything (Requirement 44).

**The manifest is what makes a run identifiable afterwards** (Requirement 45): its id, the pair that
produced it, every policy file it read and every artifact it wrote, each by digest. I14 asks two
runs of one unchanged configuration for byte-identical manifests, so ``run_manifest`` reads no clock
and no path of its own: the run id is an argument, both maps are sorted, and everything else comes
off the engine the composition root already built. The clock is one line, in ``minted_run_id``,
where it names a run rather than appearing inside one.

**``written_run`` writes all three artifacts rather than exposing one writer each.** Requirement 45
says the manifest records *every* artifact digest, and a caller who writes a file and then remembers
to digest it is a caller who will one day not remember -- the same argument ``policy.py`` makes for
returning a digest beside every declaration. What that costs is a caller who wants only one of the
three, and there is none: a shell either persists a run or answers over HTTP and persists nothing.

**A digest is taken by reading the file back**, not by hashing the value on its way past. A digest
of what we meant to write is not evidence about what a later reader will find, and the whole point
of putting it in the manifest is that someone reads it later.

**Side output is not written here yet.** ``ServiceResult.side_output`` is keyed by the stage that
produced it and each key wants its own destination -- ``pii_check``'s placeholder map is a file that
is never committed (I13), ``load_data``'s unreadable items are the quarantine tier. The shell that
has one to write is T28's and T29's, and inventing a layout for them now would be a layout nobody
has a caller for (§2).
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import (
    read_jsonlines,
    read_txt,
    write_json,
    write_jsonlines,
)
from agent_toolkit.string_utils import compute_hash
from pydantic import ValidationError

from dataforce.engine import Engine
from dataforce.errors import ConfigError
from dataforce.pipeline.flow import DECLARED_ONLY, FROM_SOURCE, STAGES
from dataforce.pipeline.load_data import stamped_version
from dataforce.pipeline.params import declaration
from dataforce.record import Record

# What one run leaves behind, in the directory it was given. § *Repository layout* names two of
# them: `metrics.json`, and `run.json` -- *one run, one manifest, at the root of what it wrote*.
# Which tier of `data/` a shell hands over is that shell's decision and not this module's.
RECORDS = "records.jsonl"
METRICS = "metrics.json"
MANIFEST = "run.json"

# The manifest's own keys. Named because `POST /<phase>` answers with the same three under `run`
# (§ *Request and response models*), and T28 reads them rather than spelling them a second time.
RUN_ID = "run_id"
PRODUCER = "producer"
POLICY = "policy"
ARTIFACTS = "artifacts"

# What the fold reports. `records` is the denominator every other number is read against.
COUNTED = "records"
PER_STAGE = "stages"
CHECKS = "label_checks"
FOUND = "found"
DECLARED = "declared"

# Where `params.yaml` declares what each label check found last time (Requirement 22).
INVALID_COUNTS = "invalid_counts"

# How a run is named: when it started, by the clock the edge owns, and four hex of what it read.
RUN_PREFIX = "r_"
RUN_LENGTH = 4
STARTED_AT = "%Y-%m-%dT%H:%M:%SZ"
DIGEST_SEPARATOR = "|"


def minted_run_id(policy_digests: Mapping[str, str]) -> str:
    """A new run's id: when it started, and which configuration it started under.

    The one clock call that names a run. The suffix is over the policy digests rather than over
    randomness, so a re-tuned threshold is visible in the id itself and two runs that read the same
    files say so -- which is what Requirement 45 asks a manifest for, one field earlier.

    Two runs of one configuration started inside the same second are one id. That is the resolution
    the record's own drawing states, a run is minutes of work, and the alternative is a random
    suffix that says nothing and cannot be re-derived from anything.
    """
    joined = DIGEST_SEPARATOR.join(
        f"{path}={digest}" for path, digest in sorted(policy_digests.items())
    )
    started = datetime.now(UTC).strftime(STARTED_AT)
    return f"{RUN_PREFIX}{started}_{compute_hash(joined)[:RUN_LENGTH]}"


def artifact_digest(path: Path) -> str:
    """The digest of the file at that path, as the manifest records it."""
    return compute_hash(read_txt(path))


def read_records(path: Path) -> tuple[Record, ...]:
    """Every record one file holds, validated on the way in.

    `read_jsonlines` answers `[]` for a file it cannot read, which reads as an empty corpus and is
    the same wrong default `policy.py` refuses for a declaration -- so the path is checked first.
    A row that is not a record is a `ConfigError` naming the file, because Requirement 43 permits
    one exception out of here and pydantic's carries no path.
    """
    if not path.is_file():
        raise ConfigError(f"there is no file of records at {path}")
    try:
        return tuple(Record.model_validate(row) for row in read_jsonlines(path))
    except ValidationError as wrong:
        raise ConfigError(f"{path} is not a file of records: {wrong}") from wrong


def failed_check_names(record: Record) -> tuple[str, ...]:
    """Which named label checks this record failed, and none where the stage has not run."""
    written = record.data_quality.label_check
    return written.failed_checks if written else ()


def corpus_counts(engine: Engine, records: Sequence[Record]) -> dict[str, Any]:
    """What a run came to, corpus-wide: the fold a human reads (Requirement 44).

    Three numbers and no verdict. How many records there were; how many carry each stage's key,
    which is the same sentence as *how many that stage skipped*, read from the other end; and what
    each label check found beside what `params.invalid_counts` declared it found last time.

    That last pair is Requirement 22 as Decision 10 left it -- a count that moved is a line in a
    diff and stops nothing. Both sides are listed even where one is absent: a check that fired for
    the first time and a declared check that stopped firing are the two interesting cases, and
    either would be invisible if the fold only reported what it happened to see.
    """
    failed = Counter(name for record in records for name in failed_check_names(record))
    # A malformed `invalid_counts` reads as *nothing declared* rather than raising: this fold is
    # for reading and Requirement 44 says a number here stops nothing, so the one thing it may not
    # do is become the reason a run does not finish.
    declared = declaration(engine, INVALID_COUNTS)
    counts = declared if isinstance(declared, Mapping) else {}
    return {
        COUNTED: len(records),
        PER_STAGE: {
            row.stage: sum(
                1
                for record in records
                if getattr(getattr(record, row.phase), row.stage, None) is not None
            )
            for row in STAGES
            if row.phase not in FROM_SOURCE and row.phase not in DECLARED_ONLY
        },
        CHECKS: {
            name: {FOUND: failed[name], DECLARED: counts.get(name)}
            for name in sorted(set(counts) | set(failed))
        },
    }


def run_manifest(
    engine: Engine, run_id: str, artifacts: Mapping[str, str]
) -> dict[str, Any]:
    """What one run was: its id, the pair that produced it, and every file it read or wrote.

    Both maps are sorted, which is the whole of I14: a manifest that iterated in the order files
    happened to be read would move for reasons that are not configuration changes, and then a
    changed threshold is one diff among several instead of the only one.

    The pair is stamped by `load_data`'s own `stamped_version`, so the manifest and every record's
    provenance say `text2text@1` the same way rather than twice.
    """
    return {
        RUN_ID: run_id,
        PRODUCER: {
            "modality": stamped_version(engine.modality),
            "profile": stamped_version(engine.profile),
        },
        POLICY: dict(sorted(engine.policy_digests.items())),
        ARTIFACTS: dict(sorted(artifacts.items())),
    }


def written_run(
    directory: Path, engine: Engine, run_id: str, records: Sequence[Record]
) -> dict[str, Any]:
    """One run's artifacts, written, and the manifest that records what they came to.

    The manifest is returned as well as written, because a route answers with it and a file it
    could disagree with would be two manifests (§ *Request and response models*).
    """
    write_jsonlines(
        directory / RECORDS, [record.model_dump(mode="json") for record in records]
    )
    write_json(directory / METRICS, corpus_counts(engine, records))
    manifest = run_manifest(
        engine,
        run_id,
        {name: artifact_digest(directory / name) for name in (RECORDS, METRICS)},
    )
    write_json(directory / MANIFEST, manifest)
    return manifest
