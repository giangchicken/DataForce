"""adapter · this task's rows: what one sample becomes, where it lands, and what they come to.

The modality knows a sample has an input, a label and facets. It does not know that a tool call is
a call *against a catalog*, which is the first thing this file adds: the turns and the catalog
ship together under one key, because a label stored apart from the catalog it was written for is a
label nothing can check.

The rest of it is **everything in this task that is handed a `Session`**, which is what the tag
is: a function given one is not a noun and not a decision, it is the translation between the domain
and a database. `create_tool_decision_tables` makes the place, `build_sample` turns one `DatasetSample` into
a row, `store_tool_decision_sample` writes both tables or neither, `rebuild_tool_decision_dataset` does every row again, and the
four `GROUP BY`s answer what the corpus carries. `ToolDecisionSampleBuilding` is pure and would be
`logic` on its own, but a file is one tag and it is the thing the others are about.

**Every name here says `tool_decision`** (`R-8`), because a call is read where it lands and not
where it was defined: `create_tool_decision_tables` at a call site says which corpus is being made,
where `create_tables` says only that some tables are. None of them says `rows` or `data` either --
every module in this repository works on rows, so the word narrows nothing.

Which of the **two** tables each one touches is the docstring's to say, and the answer is usually
both: they hold the same samples and differ by what is in them.

Each read is a translation and nothing else: a `GROUP BY` answers in the dialect's own terms -- one
text per row here and a parsed value there, a list that cannot be a key, two spellings of one value
-- and each hands back what those rows *mean*. **Which values a person may tick is not here, and
not anywhere below the edge**: that is a list a tick box is drawn from, so it lives with the page.
A read here answers what the rows *carry*, never what they were allowed to carry.

The tag is also what keeps `services/` out of all of it (`H-8`). The arithmetic over these counts
is `logic` and may not open a database, which is why the router is where the two meet.

**Nothing declared is here.** `domain`, `call_trigger`, `direction` and `have_conversation_flow`
are ticked by a person and arrive under the record's `class` key, which the modality carries
through without naming any of them. Which of them end up as columns is the table's `FACETS`, and
everything else lands in `notes` -- so a facet ticked on the page reaches the row without a second
list here to keep in step with it.
"""

import json
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, String, delete, func, select
from sqlalchemy.orm import Session

from dataforce.edge.database import merge_rows
from dataforce.modalities.text2text.dataset_management import (
    DatasetSample,
    DatasetSampleBuilding,
    ShippedDatasetSample,
)
from dataforce.modalities.text2text.dataset_management.duplicate_data_checking import (
    canonical_json,
)
from dataforce.tables import Base

from .label_statistics import (
    list_called_tools,
    list_label_faults,
    list_offered_tools,
)
from .schema import (
    QueuedSampleRow,
    QueueState,
    StoredSample,
    StoredSampleRow,
    ToolDecisionDataStamp,
    ToolDecisionQueuedSample,
    ToolDecisionRecord,
    ToolDecisionSample,
    ToolDecisionSampleContent,
)

TOOL_DECISION_KEY_NAMESPACE = uuid.UUID("6f3f9e1a-0f6b-5c7e-9f2a-1d4b8c3e7a50")

# How much of the opening turn a list row carries. A cap and not a whole conversation: the list is
# a thing to pick from, and three hundred rows of full transcripts is a page nobody can read and a
# response nobody should send.
PREVIEW_CHARACTERS = 200

# How many keys go into one `IN (...)`. SQLite compiles a bound variable per element and refuses
# past its own limit, which a corpus of ten thousand lines would reach in one statement.
KEYS_PER_LOOKUP = 500


class ToolDecisionSampleBuilding(DatasetSampleBuilding):
    """A reviewed tool-calling sample, as the row `tool_decision`'s two tables take."""

    def build_input(self, shipped: ShippedDatasetSample) -> Mapping[str, Any]:
        """`{messages, tools}` -- the turns and the catalog together, as they ship."""
        return {"messages": list(shipped.messages), "tools": list(shipped.tools)}

    def compute_facets(self, shipped: ShippedDatasetSample) -> Mapping[str, Any]:

        return {
            "number_turns": len(shipped.messages),
            "number_label_tools": len(list_called_tools(shipped.label)),
            "number_provided_tools": len(list_offered_tools([shipped.tools])),
            # Whether the check found nothing to say, and never a second reading of the rule:
            # the page shows the same sentences before the reviewer ticks *correct*, so a row
            # marked invalid here is a row they were warned about there.
            "schema_valid": not list_label_faults(shipped.label, shipped.tools),
        }


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(
        engine,
        tables=[
            Base.metadata.tables[named]
            for named in (
                ToolDecisionRecord.__tablename__,
                ToolDecisionSample.__tablename__,
                ToolDecisionQueuedSample.__tablename__,
            )
        ],
    )


def build_tool_decision_sample(
    key: uuid.UUID, sample: DatasetSample, times: ToolDecisionDataStamp
) -> ToolDecisionSample:

    return ToolDecisionSample(
        id=key,
        input=dict(sample.input),
        label=None if sample.label is None else list(sample.label),
        created_time=times.created_time,
        modified_time=times.modified_time,
        notes={
            name: value
            for name, value in sample.facets.items()
            if name not in ToolDecisionSample.FACETS
        },
        **{facet: sample.facets.get(facet) for facet in ToolDecisionSample.FACETS},
    )


def merge_tool_decision_db(
    session: Session, document: Mapping[str, Any], sample: DatasetSample
) -> ToolDecisionDataStamp:

    key = uuid.uuid5(TOOL_DECISION_KEY_NAMESPACE, str(document["id"]))
    modified = datetime.now()
    first = session.scalar(
        select(ToolDecisionRecord.created_time).where(ToolDecisionRecord.id == key)
    )
    stamp = ToolDecisionDataStamp(key, modified if first is None else first, modified)
    merge_rows(
        session,
        ToolDecisionRecord(
            id=stamp.key,
            document=dict(document),
            created_time=stamp.created_time,
            modified_time=stamp.modified_time,
        ),
        build_tool_decision_sample(key, sample, stamp),
    )
    return stamp


def rebuild_tool_decision_dataset(
    session: Session, building: DatasetSampleBuilding
) -> int:

    written = 0
    reviews = session.execute(
        select(
            ToolDecisionRecord.id,
            ToolDecisionRecord.document,
            ToolDecisionRecord.created_time,
            ToolDecisionRecord.modified_time,
        )
    ).all()
    session.execute(delete(ToolDecisionSample))
    for key, document, created, modified in reviews:
        session.add(
            build_tool_decision_sample(
                key,
                building.build_sample(document),
                ToolDecisionDataStamp(key, created, modified),
            )
        )
        written += 1
    session.commit()
    return written


def build_queue_key(document: Mapping[str, Any]) -> uuid.UUID:
    """The key one raw line takes, derived from what the line says and nothing else.

    Content and not a counter, so importing the same file twice imports nothing the second time --
    which is the whole of what makes an import safe to re-run after it failed half way.
    """
    return uuid.uuid5(TOOL_DECISION_KEY_NAMESPACE, canonical_json(document))


def name_queued_sample(document: Mapping[str, Any]) -> tuple[uuid.UUID, dict[str, Any]]:
    """The key a raw line takes, and the line carrying that key as its own name.

    **One place, because two ways in have to arrive at the same name.** A sample imported from a
    file and the same sample pasted into the page are the same content, so they are the same key
    and the same row -- pasting one the corpus already holds updates it rather than writing a
    second copy of it. Two expressions of this rule would drift, and nothing would notice until a
    corpus held the same sample twice under different names.

    A line that named itself keeps its name. The key is still the content's, so the row is the
    same row either way, and what a corpus calls its own samples is not this service's to
    overwrite.
    """
    key = build_queue_key(document)
    return key, {"id": str(key), **document}


def list_held_queue_keys(session: Session, keys: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these the queue already holds, asked in batches the dialect will take."""
    held: set[uuid.UUID] = set()
    for at in range(0, len(keys), KEYS_PER_LOOKUP):
        asked = keys[at : at + KEYS_PER_LOOKUP]
        held.update(
            session.scalars(
                select(ToolDecisionQueuedSample.id).where(
                    ToolDecisionQueuedSample.id.in_(asked)
                )
            )
        )
    return held


def queue_tool_decision_samples(
    session: Session, documents: Sequence[Mapping[str, Any]]
) -> tuple[int, int]:
    """Every document the queue does not hold, written as one waiting row. How many, and how many
    it already had.

    A document with no `id` is given the queue key as its name, by `name_queued_sample` and not
    here: a raw line pasted into the page is named by that same function, and the two have to
    agree or one sample arrives under two names.

    Duplicates *within* one file collapse to one row, which is the same rule as duplicates across
    two: the key is the content, so the second copy is a row that is already held.
    """
    keyed = [name_queued_sample(document) for document in documents]
    held = list_held_queue_keys(session, [key for key, _ in keyed])
    imported = 0
    now = datetime.now()
    # Counted on from what the table already holds, so a second import lands behind the first
    # rather than interleaved with it. Read once: the whole import is one transaction, and nothing
    # else writes this table.
    arrived = session.scalar(select(func.max(ToolDecisionQueuedSample.arrived))) or 0
    for key, document in keyed:
        if key in held:
            continue
        held.add(key)
        arrived += 1
        session.add(
            ToolDecisionQueuedSample(
                id=key,
                document=document,
                imported_time=now,
                arrived=arrived,
                state=QueueState.WAITING,
            )
        )
        imported += 1
    session.commit()
    return imported, len(keyed) - imported


def select_next_queued_sample(
    session: Session,
) -> tuple[uuid.UUID, Mapping[str, Any]] | None:
    """The first row nobody has labelled or skipped, or `None` where none is waiting.

    In the order the lines arrived, so a file curated in an order is walked in that order and a
    reviewer who comes back tomorrow carries on rather than starting again from whatever the
    database felt like returning.
    """
    found = session.execute(
        select(ToolDecisionQueuedSample.id, ToolDecisionQueuedSample.document)
        .where(ToolDecisionQueuedSample.state == QueueState.WAITING)
        .order_by(ToolDecisionQueuedSample.arrived)
        .limit(1)
    ).first()
    if found is None:
        return None
    return found[0], found[1]


def read_opening_turn(document: Mapping[str, Any]) -> str:
    """The first thing said in a sample, cut to a preview, or nothing where nothing was said."""
    turns = document.get("messages") or []
    if not turns:
        return ""
    said = turns[0].get("content")
    if not isinstance(said, str):
        said = json.dumps(said, ensure_ascii=False)
    return said[:PREVIEW_CHARACTERS]


def select_queued_samples(
    session: Session, limit: int, offset: int
) -> tuple[QueuedSampleRow, ...]:
    """A page of the queue in walk order, whatever state each row is in.

    Every state, because the list is what a reviewer picks from and *what has already been done* is
    half of what they are looking for -- a list of only the waiting ones cannot answer whether a
    sample was skipped or labelled by somebody else.
    """
    found = session.execute(
        select(
            ToolDecisionQueuedSample.id,
            ToolDecisionQueuedSample.state,
            ToolDecisionQueuedSample.arrived,
            ToolDecisionQueuedSample.document,
        )
        .order_by(ToolDecisionQueuedSample.arrived)
        .limit(limit)
        .offset(offset)
    )
    return tuple(
        QueuedSampleRow(
            key=str(key),
            state=state,
            arrived=arrived,
            said=read_opening_turn(document),
        )
        for key, state, arrived, document in found
    )


def select_queued_sample(session: Session, key: uuid.UUID) -> Mapping[str, Any] | None:
    """One queued sample by key, whatever state it is in, or `None` where the queue has no such row.

    Whatever state: a reviewer who picks a row they already labelled is asking to look at it again,
    and refusing them because it is marked done would be the page enforcing a rule the store does
    not have -- a second record under the same key replaces the first, which is the write's own
    answer to being labelled twice.
    """
    found = session.get(ToolDecisionQueuedSample, key)
    if found is None:
        return None
    return dict(found.document)


def count_queued_states(session: Session) -> Mapping[str, int]:
    """How many rows stand in each state, every state named even where it holds nothing.

    Named even at zero because these are read as *how much is left*: a state missing from the
    answer would be drawn as a blank rather than as a nought.
    """
    counted = {state.value: 0 for state in QueueState}
    for state, number in session.execute(
        select(ToolDecisionQueuedSample.state, func.count()).group_by(
            ToolDecisionQueuedSample.state
        )
    ):
        counted[state] = number
    return counted


def mark_queued_sample(session: Session, key: uuid.UUID, state: QueueState) -> bool:
    """That row moved to that state, and whether there was a row to move.

    No commit: the caller owns the transaction, because the one state change that matters -- a
    sample marked done -- has to land with the two rows the record wrote or not at all.
    """
    found = session.get(ToolDecisionQueuedSample, key)
    if found is None:
        return False
    found.state = state
    return True


def select_stored_samples(
    session: Session, limit: int, offset: int
) -> tuple[StoredSampleRow, ...]:
    """A page of the stored corpus, newest write first.

    Newest first because the reason to open this is usually the row somebody just wrote -- a
    corpus walked in arrival order is what the queue already is.

    The columns and the opening turn, never the whole sample: this is read to find rows worth
    going back to, and a page carrying three hundred conversations is a page nobody renders.
    """
    found = session.execute(
        select(
            ToolDecisionSample.id,
            ToolDecisionSample.input,
            ToolDecisionSample.modified_time,
            *(
                getattr(ToolDecisionSample, facet)
                for facet in ToolDecisionSample.FACETS
            ),
        )
        .order_by(ToolDecisionSample.modified_time.desc(), ToolDecisionSample.id)
        .limit(limit)
        .offset(offset)
    )
    return tuple(
        StoredSampleRow(
            key=str(key),
            said=read_opening_turn(one_input),
            modified_time=modified_time,
            **dict(zip(ToolDecisionSample.FACETS, facets, strict=True)),
        )
        for key, one_input, modified_time, *facets in found
    )


def select_stored_sample(session: Session, key: uuid.UUID) -> StoredSample | None:
    """One stored row whole, or `None` where the corpus holds no such row.

    The facets come back as one map keyed by the column's own name rather than as fields of their
    own, because which facets exist is this profile's and a reader that named them would have to
    be edited every time one is added.
    """
    found = session.get(ToolDecisionSample, key)
    if found is None:
        return None
    return StoredSample(
        key=str(found.id),
        input=dict(found.input),
        label=tuple(found.label) if found.label is not None else None,
        facets={facet: getattr(found, facet) for facet in ToolDecisionSample.FACETS},
        created_time=found.created_time,
        modified_time=found.modified_time,
    )


def count_total_samples(session: Session) -> Mapping[str, int]:
    counted: dict[str, int] = {}
    for model in (ToolDecisionRecord, ToolDecisionSample):
        counted[model.__tablename__] = (
            session.scalar(select(func.count()).select_from(model)) or 0
        )
    return counted


def count_by_facet(
    session: Session,
) -> Mapping[str, Mapping[str, int]]:
    counted: dict[str, Mapping[str, int]] = {}
    for facet in ToolDecisionSample.FACETS:
        column = getattr(ToolDecisionSample, facet)
        written_as_text = isinstance(column.type, String)
        found: dict[str, int] = {}
        for value, number in session.execute(
            select(column, func.count()).group_by(column).order_by(column)
        ):
            key = value if written_as_text else json.dumps(value, ensure_ascii=False)
            found[key] = found.get(key, 0) + number
        counted[facet] = found
    return counted


def count_by_pair(
    session: Session, row_facet: str, column_facet: str
) -> Mapping[tuple[Any, Any], int]:
    rows = getattr(ToolDecisionSample, row_facet)
    columns = getattr(ToolDecisionSample, column_facet)
    counted: Counter[tuple[Any, Any]] = Counter()
    for row, column, number in session.execute(
        select(rows, columns, func.count()).group_by(rows, columns)
    ):
        keyed_row = tuple(row) if isinstance(row, list) else row
        keyed_column = tuple(column) if isinstance(column, list) else column
        counted[(keyed_row, keyed_column)] += number
    return dict(counted)


def select_sample_contents(
    session: Session,
) -> tuple[ToolDecisionSampleContent, ...]:

    found = session.execute(
        select(
            ToolDecisionSample.id, ToolDecisionSample.input, ToolDecisionSample.label
        )
    )
    return tuple(
        ToolDecisionSampleContent(str(key), one_input, label)
        for key, one_input, label in found
    )
