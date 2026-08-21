"""STEP · load (stage 0) · every source item as a canonical record, provenance and all.

The only stage that sees the source's own shape, and it sees it through the two
contracts: the modality reads the content parts, the profile builds the record. What
this module adds is what neither of them can know -- which file, which element of it,
when -- and the rule that an item nobody can read is carried rather than dropped.

Pure. Raw items in, records out, and one gate over two digests. It opens nothing and
names no path, so reading the source and writing `loaded.jsonl` is `api/`'s job.

**The ingest timestamp is not a clock reading, and that is a deliberate deviation.**
Requirement 14 asks for one per record. Invariant 14 asks for two runs over one source to
produce byte-identical artifacts, which is also T11's own criterion, and a per-record wall
clock makes it impossible. So `ingested_at` is a required parameter, this module holds no
clock at all, and `api/` supplies the source file's own last-modified time. What is given
up is *when this run happened*, which the run's log records; what is kept is two artifacts
that can be compared byte for byte.

**`offset` is the element's index in the source array, not a byte offset.** Requirement
14 says byte offset. `iter_json_array_file` yields values and not positions, so a byte
offset would cost a second pass over 126 MiB to recover what the index already answers
-- which element of the array this record is. `measure_corpus` has stamped the index
since T10, and `Source.offset` says so where it is declared.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from agent_toolkit.logging import get_logger

from dataforce.core.errors import ConfigError
from dataforce.core.gates import GateResult
from dataforce.core.record import (
    PROVENANCE_KEY,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
    stamp,
)
from dataforce.modalities.base import Modality
from dataforce.profiles.base import Profile

__all__ = ["UNPARSED_ROLE", "loaded_records", "source_identity"]

log = get_logger(__name__)

# The role on the one part an unreadable item becomes. Not a name out of the source's own
# vocabulary -- reading its roles is what failed -- so it says what the part is instead of
# claiming to be a turn.
UNPARSED_ROLE = "raw"

# What reading one item raises when the item, and not this code, is the problem: a key the
# item does not have, a turn of the wrong type, a role pydantic refuses -- its
# `ValidationError` is a `ValueError`. Narrow on purpose, and not `Exception`: a bug in a
# modality would otherwise quarantine every record in the corpus and leave the gate
# passing, because `parsed + unparsed == source count` holds perfectly when nothing
# parsed.
UNREADABLE = (ConfigError, KeyError, TypeError, ValueError)


def source_identity(*, digest: str, declared: str) -> GateResult:
    """The file this run read is the file the policy pinned.

    A changed source is a new dataset version, decided by a person, so this is a gate
    and not a warning. Checked before anything is parsed: there is nothing to be
    learned from ingesting the wrong file first.
    """
    return GateResult(
        name="source_identity",
        assertion="the source file's SHA-256 is the digest the policy declares",
        ok=digest == declared,
        observed=digest,
        expected=declared,
    )


def _unreadable_record(
    raw: Any, *, source: Source, producer: Producer, reason: str
) -> Record:
    """One item that defeated the reader, kept whole so a person can see why.

    Requirement 14 drops nothing, and `loaded.jsonl` is where these live -- so the item
    becomes its own single content part rather than a row of a second shape. That part
    is also what gives the record an `rid`, which keeps identity one rule: a digest over
    the content, whatever the content turned out to be.
    """
    part = TextPart(role=UNPARSED_ROLE, text=json.dumps(raw, ensure_ascii=False))
    return Record(
        rid=compute_rid([part]),
        source=source,
        producer=producer,
        content=[part],
        parse_status="unparsed",
        meta={"parse_error": reason},
    )


def _with_provenance(
    raw: Any, *, source: Source, producer: Producer
) -> Mapping[str, Any]:
    """The item, plus the one key a profile lifts its provenance out of.

    A copy rather than a mutation: the caller streams the source and may hold the item
    for its own counting, and a stage that wrote into what it was handed would make that
    a different item afterwards.
    """
    if not isinstance(raw, Mapping):
        raise TypeError(
            f"a source element is {type(raw).__name__}, not an object; one element is "
            "one record, and there is nothing to read a record out of"
        )
    return {
        **raw,
        PROVENANCE_KEY: {
            "source": source.model_dump(),
            "producer": producer.model_dump(),
        },
    }


def loaded_records(
    raw_items: Iterable[Any],
    modality: Modality,
    profile: Profile,
    *,
    digest: str,
    ingested_at: str,
) -> Iterator[Record]:
    """Every item of one source as a record, in source order, dropping none.

    One item in, one record out, always -- which is what the conservation gate over this
    stage is asserting, and why the two counts it compares are taken at two independent
    points rather than from one loop variable.

    The provenance goes in under `PROVENANCE_KEY` rather than through a parameter of
    `build_record`, because a profile builds the record and only the stage knows where
    the item came from. `core/record.py` owns that key: this module may not import a
    concrete profile, and before stage 0 existed the key lived beside one.
    """
    producer = stamp(modality, profile)
    for offset, raw in enumerate(raw_items):
        source = Source(file_sha256=digest, offset=offset, ingested_at=ingested_at)
        try:
            parts = modality.content_parts(raw)
            yield profile.build_record(
                _with_provenance(raw, source=source, producer=producer), parts
            )
        except UNREADABLE as unreadable:
            log.warning("item %d is unreadable and is carried: %s", offset, unreadable)
            yield _unreadable_record(
                raw, source=source, producer=producer, reason=str(unreadable)
            )
