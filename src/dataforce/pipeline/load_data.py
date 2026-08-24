"""STEP · load_data · every source item becomes one record with identity, content and provenance.

Two calls per item and no third: ``content_parts`` on the modality turns its turns into ordered
parts, ``build_record`` on the profile turns the rest of it into a record. Everything this module
holds of its own is what neither axis can know -- which file, which position in it, which run, and
what to do with an item that cannot be read at all.

**This is the one stage whose input is not the bus.** § *Shared decisions* gives every service the
signature ``(engine, records) -> ServiceResult``; a source item is not a record and there is no
record to hand this one, so the rule is broken here (§8) and ``flow.FROM_SOURCE`` is where
``run_phase`` reads that. The three keyword arguments are the things only the edge can know: the
digest of the file the items came out of, the clock, and the run they belong to (Decision 4 --
*``run_id`` is generated at the edge, because the engine has no clock*). Handing them in rather than
taking them is what makes ``POST /load-data`` and an in-process caller produce the same record
(Requirement 46, I15).

**The offset is the item's position in what this call was handed**, which is the whole source for
both shells as they are built. A caller that chunks a source would need a starting offset, and it
would be that caller's task to add it -- an argument nothing passes is flexibility nobody asked for
(§2), and the record's ``offset`` is only useful if it means what the reader thinks.

**An item that cannot be read is counted, not raised -- and that decision is T14's.** Three things
below this module raise ``ConfigError`` while records are being read, which Requirement 43 permits
only before: an item whose ``messages`` is not a list, a turn declaring no ``role``, and an item
whose ``meta`` lacks the declared label key. Neither axis signature has a value channel for *this
item is unreadable* and neither knows the offset, so both recorded the break and left it here. This
is what *here* decided: the raise is caught per item, the offset and the message go to the edge as
side output for the quarantine tier, and the run completes (Requirement 43). What is given up is the
case where the *declaration* is wrong rather than the item -- a manifest naming a label key no item
carries makes every item unreadable, and P23 would call that configuration scope and stop. This
module cannot tell the two apart at item 1 and refuses to guess: what it can know is per item, so
per item is the scope it reports, and twenty thousand entries against zero records says the rest
loudly enough.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.modalities import Modality
from dataforce.profiles import Profile
from dataforce.record import Provenance, Record

from .params import declared_digest

# Where `params.yaml` declares the source this run is allowed to read.
SOURCE_DIGEST = ("source", "sha256")

# What the edge writes to the quarantine tier: one entry per item that could not be read.
UNREADABLE = "unreadable"
OFFSET = "offset"
REASON = "reason"
STAGE = "load_data"


def stamped_version(axis: Modality | Profile) -> str:
    """One axis as its provenance names it -- `text2text@1` -- so a bump is visible per record."""
    return f"{axis.name}@{axis.version}"


def refuse_an_undeclared_source(engine: Engine, digest: str) -> None:
    """The one place a run refuses to start: this is not the file `params.yaml` declares.

    A `ConfigError` before any record is read, which is the scope Requirement 43 permits. An empty
    declaration is not a mismatch: `params.source.sha256` is empty until a corpus is declared, and
    a run over an undeclared source is what every test fixture and the Smoke rung do.
    """
    declared = declared_digest(engine, *SOURCE_DIGEST)
    if declared and declared != digest:
        raise ConfigError(
            f"the source hashes to {digest!r} and params.yaml declares {declared!r}; "
            "a run over a file nobody declared is not identifiable afterwards"
        )


def load_data(
    engine: Engine,
    items: Iterable[Mapping[str, Any]],
    *,
    source_file_sha256: str,
    ingested_at: datetime,
    run_id: str,
) -> ServiceResult:
    """Every source item as one record, and the offset of every item that could not be read.

    The catalog is **not** copied onto the record as an answer space (I10): `answer_schema`
    materialises one from the record when asked, and a stored space is the copy that goes stale.
    Nothing here reads the label either -- which key holds it is the manifest's to declare and
    `build_record`'s to read (Requirement 14), so a conversation carrying a completed `tool_call`
    from an earlier turn cannot become the answer by being easier to find.
    """
    refuse_an_undeclared_source(engine, source_file_sha256)
    records: list[Record] = []
    unreadable: list[dict[str, Any]] = []
    for offset, item in enumerate(items):
        provenance = Provenance(
            source_file_sha256=source_file_sha256,
            offset=offset,
            ingested_at=ingested_at,
            modality=stamped_version(engine.modality),
            profile=stamped_version(engine.profile),
            run_id=run_id,
        )
        try:
            parts = engine.modality.content_parts(item)
            records.append(engine.profile.build_record(item, parts, provenance))
        except ConfigError as unreadable_item:
            unreadable.append({OFFSET: offset, REASON: str(unreadable_item)})
    return ServiceResult(
        records=tuple(records),
        # Only where there is something to write: side output is what the edge must *persist*,
        # and an empty quarantine file is a file that says nothing.
        side_output={STAGE: {UNREADABLE: tuple(unreadable)}} if unreadable else {},
    )
