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
from collections.abc import Mapping
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
from dataforce.tables import Base

from .label_statistics import (
    list_called_tools,
    list_offered_tools,
    validate_label_calls,
)
from .schema import (
    ToolDecisionDataStamp,
    ToolDecisionRecord,
    ToolDecisionSample,
    ToolDecisionSampleContent,
)

# The namespace a row key is derived in -- fixed, so one posted name keeps one key for the life of
# the corpus. `store_tool_decision_sample` says why it is derived rather than minted.
TOOL_DECISION_KEY_NAMESPACE = uuid.UUID("6f3f9e1a-0f6b-5c7e-9f2a-1d4b8c3e7a50")


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
            "schema_valid": validate_label_calls(shipped.label, shipped.tools),
        }


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(
        engine,
        tables=[
            Base.metadata.tables[named]
            for named in (
                ToolDecisionRecord.__tablename__,
                ToolDecisionSample.__tablename__,
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
    """The key and the two times this write stamps on both of this task's rows.

    The key is derived from the posted name and never minted: a fresh one would make a sample
    reviewed twice into two rows holding one review. The name stays readable in `record.document`.

    `created_time` is read **before** the merge, because `merge` replaces the whole row: the column
    that never moves is carried forward by hand here, or it moves on every repost. `None` back from
    that read is no row yet, and then now is what both times take.

    Both rows go to `merge_rows`, which is `edge/database.py`'s and not this task's: one
    transaction over the two is a rule about rows that belong to one another, not about tools.
    """
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
    """Every sample row dropped and recomputed from `record`. How many it wrote.

    The invariant made runnable: this table is a function of the other, so a row edited by hand is
    corrected by this and a rebuild over an empty `record` empties it. The two times are carried
    from the record rather than taken now, because when a review landed is a fact about the review.

    Read whole before anything is written, rather than added to while the cursor is open. One
    transaction, so a rebuild that fails leaves the table it was rebuilding intact rather than
    empty. A record that no longer passes the precondition raises here and stops the rebuild:
    finishing around it would leave a table nothing can call a function of the other.
    """
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
    """Every stored sample's key, input and label -- the three columns the statistics read.

    **One read, three questions**: the duplicate grouping is given all three and the label
    measurements read two, so a second query would fetch the same rows again.
    """
    found = session.execute(
        select(
            ToolDecisionSample.id, ToolDecisionSample.input, ToolDecisionSample.label
        )
    )
    return tuple(
        ToolDecisionSampleContent(str(key), one_input, label)
        for key, one_input, label in found
    )
