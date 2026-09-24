"""adapter · this task's rows: what one sample becomes, where it lands, and what they come to."""

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

PREVIEW_CHARACTERS = 200
KEYS_PER_LOOKUP = 500
NOTHING_ANSWERED = "none"


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
            "schema_valid": not list_label_faults(shipped.label, shipped.tools),
        }


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(
        engine,
        tables=[
            Base.metadata.tables[name]
            for name in (
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


def delete_tool_decision_samples(session: Session, keys: Sequence[uuid.UUID]) -> None:

    for model in (ToolDecisionRecord, ToolDecisionSample):
        session.execute(delete(model).where(model.id.in_(keys)))
    session.commit()


def rebuild_tool_decision_dataset(
    session: Session, building: DatasetSampleBuilding
) -> int:

    number_written = 0
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
        number_written += 1
    session.commit()
    return number_written


def name_queued_sample(document: Mapping[str, Any]) -> tuple[uuid.UUID, dict[str, Any]]:

    key = uuid.uuid5(TOOL_DECISION_KEY_NAMESPACE, canonical_json(document))
    return key, {"id": str(key), **document}


def queue_tool_decision_samples(
    session: Session, samples: Sequence[tuple[uuid.UUID, Mapping[str, Any]]]
) -> tuple[int, int]:

    keys = [key for key, _ in samples]
    queued_keys: set[uuid.UUID] = set()
    for at in range(0, len(keys), KEYS_PER_LOOKUP):
        queued_keys.update(
            session.scalars(
                select(ToolDecisionQueuedSample.id).where(
                    ToolDecisionQueuedSample.id.in_(keys[at : at + KEYS_PER_LOOKUP])
                )
            )
        )
    number_imported = 0
    now = datetime.now()

    walk_position = (
        session.scalar(select(func.max(ToolDecisionQueuedSample.walk_position))) or 0
    )
    for key, document in samples:
        if key in queued_keys:
            continue
        queued_keys.add(key)
        walk_position += 1
        session.add(
            ToolDecisionQueuedSample(
                id=key,
                document=document,
                imported_time=now,
                walk_position=walk_position,
                state=QueueState.WAITING,
            )
        )
        number_imported += 1
    session.commit()
    return number_imported, len(samples) - number_imported


def select_next_queued_sample(
    session: Session,
) -> tuple[uuid.UUID, Mapping[str, Any]] | None:

    waiting_row = session.execute(
        select(ToolDecisionQueuedSample.id, ToolDecisionQueuedSample.document)
        .where(ToolDecisionQueuedSample.state == QueueState.WAITING)
        .order_by(ToolDecisionQueuedSample.walk_position)
        .limit(1)
    ).first()
    if waiting_row is None:
        return None
    return waiting_row[0], waiting_row[1]


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
    rows = session.execute(
        select(
            ToolDecisionQueuedSample.id,
            ToolDecisionQueuedSample.state,
            ToolDecisionQueuedSample.walk_position,
            ToolDecisionQueuedSample.document,
        )
        .order_by(ToolDecisionQueuedSample.walk_position)
        .limit(limit)
        .offset(offset)
    )
    return tuple(
        QueuedSampleRow(
            key=str(key),
            state=state,
            walk_position=walk_position,
            said=read_opening_turn(document),
        )
        for key, state, walk_position, document in rows
    )


def select_queued_sample(session: Session, key: uuid.UUID) -> Mapping[str, Any] | None:
    """One queued sample by key, whatever state it is in, or `None` where the queue has no such row.

    Whatever state: a reviewer who picks a row they already labelled is asking to look at it again,
    and refusing them because it is marked done would be the page enforcing a rule the store does
    not have -- a second record under the same key replaces the first, which is the write's own
    answer to being labelled twice.
    """
    queued_sample = session.get(ToolDecisionQueuedSample, key)
    if queued_sample is None:
        return None
    return dict(queued_sample.document)


def count_queued_states(session: Session) -> Mapping[str, int]:

    number_by_state = {state.value: 0 for state in QueueState}
    for state, number in session.execute(
        select(ToolDecisionQueuedSample.state, func.count()).group_by(
            ToolDecisionQueuedSample.state
        )
    ):
        number_by_state[state] = number
    return number_by_state


def mark_queued_sample(session: Session, key: uuid.UUID, state: QueueState) -> bool:
    """That row moved to that state, and whether there was a row to move.

    No commit: the caller owns the transaction, because the one state change that matters -- a
    sample marked done -- has to land with the two rows the record wrote or not at all.
    """
    queued_sample = session.get(ToolDecisionQueuedSample, key)
    if queued_sample is None:
        return False
    queued_sample.state = state
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
    rows = session.execute(
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
        for key, one_input, modified_time, *facets in rows
    )


def select_stored_sample(session: Session, key: uuid.UUID) -> StoredSample | None:
    """One stored row whole, or `None` where the corpus holds no such row.

    The facets come back as one map keyed by the column's own name rather than as fields of their
    own, because which facets exist is this profile's and a reader that named them would have to
    be edited every time one is added.

    **`notes` comes back in that same map**, which is the other half of the same sentence: a facet
    that is a key rather than a column is still something a person ticked, and a row that answers
    nine of the eleven is a row whose other two were written and can never be read. The columns are
    merged last, so a column always wins a name -- nothing can write both, and the order says so
    rather than trusting that.
    """
    stored_sample = session.get(ToolDecisionSample, key)
    if stored_sample is None:
        return None
    return StoredSample(
        key=str(stored_sample.id),
        input=dict(stored_sample.input),
        label=tuple(stored_sample.label) if stored_sample.label is not None else None,
        facets={
            **stored_sample.notes,
            **{
                facet: getattr(stored_sample, facet)
                for facet in ToolDecisionSample.FACETS
            },
        },
        created_time=stored_sample.created_time,
        modified_time=stored_sample.modified_time,
    )


def count_total_samples(session: Session) -> Mapping[str, int]:
    number_by_table: dict[str, int] = {}
    for model in (ToolDecisionRecord, ToolDecisionSample):
        number_by_table[model.__tablename__] = (
            session.scalar(select(func.count()).select_from(model)) or 0
        )
    return number_by_table


def name_facet_values(value: Any, written_as_text: bool) -> tuple[str, ...]:

    if written_as_text:
        return (value,)
    if isinstance(value, list):
        return tuple(str(one) for one in value) or (NOTHING_ANSWERED,)
    return (json.dumps(value, ensure_ascii=False),)


def count_by_note(session: Session) -> Mapping[str, Mapping[str, int]]:

    notes = [one or {} for (one,) in session.execute(select(ToolDecisionSample.notes))]
    distribution_by_name: dict[str, Mapping[str, int]] = {}
    for name in sorted({name for one in notes for name in one}):
        number_by_value: dict[str, int] = {}
        for one in notes:
            answered = (
                name_facet_values(one[name], isinstance(one[name], str))
                if name in one
                else (NOTHING_ANSWERED,)
            )
            for key in answered:
                number_by_value[key] = number_by_value.get(key, 0) + 1
        distribution_by_name[name] = dict(sorted(number_by_value.items()))
    return distribution_by_name


def count_by_facet(
    session: Session,
) -> Mapping[str, Mapping[str, int]]:
    distribution_by_facet: dict[str, Mapping[str, int]] = {}
    for facet in ToolDecisionSample.FACETS:
        column = getattr(ToolDecisionSample, facet)
        written_as_text = isinstance(column.type, String)
        number_by_value: dict[str, int] = {}
        for value, number in session.execute(
            select(column, func.count()).group_by(column).order_by(column)
        ):
            for key in name_facet_values(value, written_as_text):
                number_by_value[key] = number_by_value.get(key, 0) + number
        distribution_by_facet[facet] = number_by_value
    return {**distribution_by_facet, **count_by_note(session)}


def count_by_pair(
    session: Session, row_facet: str, column_facet: str
) -> Mapping[tuple[Any, Any], int]:
    rows = getattr(ToolDecisionSample, row_facet)
    columns = getattr(ToolDecisionSample, column_facet)
    number_by_pair: Counter[tuple[Any, Any]] = Counter()
    for row, column, number in session.execute(
        select(rows, columns, func.count()).group_by(rows, columns)
    ):
        keyed_row = tuple(row) if isinstance(row, list) else row
        keyed_column = tuple(column) if isinstance(column, list) else column
        number_by_pair[(keyed_row, keyed_column)] += number
    return dict(number_by_pair)


def select_sample_contents(
    session: Session,
) -> tuple[ToolDecisionSampleContent, ...]:

    rows = session.execute(
        select(
            ToolDecisionSample.id, ToolDecisionSample.input, ToolDecisionSample.label
        )
    )
    return tuple(
        ToolDecisionSampleContent(str(key), one_input, label)
        for key, one_input, label in rows
    )
