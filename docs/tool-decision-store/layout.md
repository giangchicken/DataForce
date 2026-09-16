# Layout

Where each thing goes, and what each file holds. `spec.md` says what must be true and `plan.md`
schedules it; this says which module every sentence of the two lands in. No function bodies.

**This document is true until the tree is.** Once a module exists, the module is the answer.

**`spec.md` has not been swept to this yet** — § *What now contradicts `spec.md`* lists what has to
go.

---

## What each new package is for

**`modalities/text2text/stored_sample/`** — what a finished text2text review becomes once it is
kept: the shape of the stored row, how it is built out of the review's redacted halves, and what
can be measured about a label. A sample arrives here having already passed every step of the flow,
so nothing here decides whether to keep it. It only refuses a sample whose steps did not actually
run, and that refusal is an HTTP error, not a second thing to store.

**`profile/tool_decision/stored_sample/`** — this task's answers to the modality's sockets, this
task's label measurements, and this task's own two tables with the SQL over them.

**`edge/database.py`** — the DSN, the engine, the session, and the one declarative base every
task's tables hang off.

---

## The tree

```
src/dataforce/
├── modalities/text2text/
│   └── stored_sample/             NEW — the modality's fourth package
│       ├── __init__.py            facade
│       ├── schema.py              shape · three names, and no more
│       ├── sample_building.py     logic · a finished review -> the row that is kept
│       └── label_statistics.py    logic · what any text2text label can be measured by
├── profile/tool_decision/
│   └── stored_sample/             NEW — the first profile part that needs three files
│       ├── __init__.py            facade
│       ├── sample_building.py     logic   · answers the three sockets
│       ├── label_statistics.py    logic   · what THIS task's label can be measured by
│       └── tables.py              adapter · this task's two tables, and the SQL over them
├── services/tool_decision/
│   └── stored_sample.py           NEW    logic · one function per endpoint
├── edge/database.py               NEW    adapter · the DSN, the engine, the session, the base
├── edge/routers/text2text/tool_decision.py   CHANGED — the response shapes live here
└── ui/{index.html,app.js,style.css}          CHANGED

tests/
├── modalities/
│   ├── test_sample_building.py    NEW
│   └── test_label_statistics.py   NEW
├── profile/test_stored_sample.py  NEW
├── store/                         NEW
│   ├── __init__.py, conftest.py
│   └── test_tables.py, test_database.py
└── edge/test_endpoints.py         CHANGED
```

---

## `modalities/text2text/stored_sample/schema.py` — `shape`

| Name | What it is |
|---|---|
| `DerivedSampleFacets` | `NewType` over `Mapping[str, Any]` — what is computed from the sample, so nobody may type it |
| `DeclaredSampleFacets` | `NewType` over `Mapping[str, Any]` — what a reviewer ticks, so nothing may compute it |
| `StoredSample` | `input`, `label`, `facets` — the row that is kept. The profile's table turns it into columns |

## `modalities/text2text/stored_sample/sample_building.py` — `logic`

There is one outcome, so there is one shape. A sample that should not be kept is not posted, and a
sample whose steps did not run is a `422` the router raises — never a second row somewhere.

| Function | What it does |
|---|---|
| `class SampleBuilding(ABC)` | what the task subclasses, beside `PersonalDataChecking` |
| ├ `stored_sample(document)` | **concrete, not abstract.** Assembles `StoredSample` from the three sockets and the modality's own facets |
| ├ `shipped_input(document)` | **abstract** · what the task's `input` column holds |
| ├ `derived_facets(document)` | **abstract** · the task's half of the derived facets |
| └ `declared_facets()` | **abstract** · which ticks the page must draw |
| `unfinished_reason(document)` | `str \| None` — the precondition, and the only refusal left: `personal_data` was never scanned, or a confirmed span's value is still present in a `new_` key. Both mean *a step did not run*, not *a person said no* |
| `leaked_values(document)` | confirmed span values still present in the three `new_` keys. Only the redacted copies are read; the originals hold raw content on purpose |
| `redacted_personal_data(document)` | the modality's derived facet: the `personal_data_class` values, `[]` where the sample had none |
| `accepted_declaration(posted, required)` | the declared half read off the posted `class`; refuses a derived facet, refuses a missing `language` |
| `shipped_label(document)` | `new_label` — a `new_` key is text2text's, so reading it is this layer's |
| `merged_facets(derived, declared)` | the two halves as one map, **raising on an overlapping key** |

## `modalities/text2text/stored_sample/label_statistics.py` — `logic`

**Thin on purpose.** What every text2text label has in common is that it may be absent and it has a
size; anything past that is the task's vocabulary and `H-10` refuses it here. No metric is invented
beyond what `spec.md` already names.

| Function | What it does |
|---|---|
| `labelled_share(labels)` | how many stored samples carry a label at all, out of how many. The empty label is a real answer, not a gap, so this is a figure and not a warning |
| `label_sizes(labels)` | the size of each label as the modality can see it — a list's length, a string's characters — for the spread the page draws |
| `measured_labels(labels, measuring)` | the two above plus whatever the caller passes as `measuring`. The task's own measurements arrive as an argument, not as a fourth socket (`H-4`) |

## `profile/tool_decision/stored_sample/sample_building.py` — `logic`

| Function | What it does |
|---|---|
| `class ToolDecisionSampleBuilding(SampleBuilding)` | named as `ToolDecisionPersonalChecking` already is |
| ├ `shipped_input(document)` | `{messages, tools}` — from the `new_` keys, or the originals where a `new_` key is `null` |
| ├ `derived_facets(document)` | `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid` |
| └ `declared_facets()` | `("direction", "domain", "have_conversation_flow", "call_shape")` |
| `shipped_turns(document)` | the messages that ship |
| `shipped_catalog(document)` | the catalog that ships — the count is of what ships, not of what arrived |
| `MATRIX_AXES`, `DOMAINS`, `CALL_SHAPES` | the axes the page crosses and the values it offers |

## `profile/tool_decision/stored_sample/label_statistics.py` — `logic`

Where the real label measurements are, because every one of them says `tool` and only this layer
may.

| Function | What it does |
|---|---|
| `called_tools(label)` | the tool names the label calls |
| `required_parameters(tool)` | `function.parameters.required` |
| `schema_valid_label(label, catalog)` | BFCL's AST check: every call names a tool in the catalog and supplies its required parameters |
| `call_counts(labels)` | how many labels make 0, 1, or more calls — `0` is the no-call sample, and it is counted here rather than treated as missing |
| `tool_coverage(labels, catalogs)` | which offered tools are ever called, and the tail: a corpus where two tools carry 90% of the calls |

## `profile/tool_decision/stored_sample/tables.py` — `adapter`

Imports `Base`, `Utc` and `KEY_LENGTH` from `edge/database.py`, so one `MetaData` holds every
task's tables. `H-8` allows it: both are `adapter`. No `task` column — the table name is the task.

| Name | What it is |
|---|---|
| `ToolDecisionRecord(Base)` | `id`, the thirteen keys of the review, the two times. The raw side: may hold personal data, never exported |
| `ToolDecisionDataset(Base)` | `id`, `input`, `label`, then **each facet as its own column** — `language`, `ambiguous`, `personal_data`, `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid`, `direction`, `domain`, `have_conversation_flow`, `call_shape` — and the two times |
| `created_tables(engine)` | `Base.metadata.create_all`. With no migration folder, this is the only thing that makes a table |
| `stored_rows(session, document, sample)` | one `session.begin()`, a `merge` into each table. **Both always**, now that a kept sample is kept in both: the tables differ by what they hold, not by which rows they hold |
| `carried_created_time(session, id)` | read before merging — `merge` replaces the whole row, so the column that never changes has to be carried forward |
| `row_counts(session)` | how many rows each table holds. They agree, and a run where they do not is a bug rather than a figure |
| `counted_by_facet(session)` | one `GROUP BY` per facet column. The column names are this task's, and this is the layer allowed to say them |
| `counted_by_pair(session, row_facet, column_facet)` | `GROUP BY` two columns — only the pairs that exist |
| `stored_labels(session)` | the `label` column alone, for `label_statistics` |
| `shipped_inputs(session)` | the `input` column alone, for the duplicate scan |
| `rebuilt_dataset(session, building)` | delete every row and recompute from the record table |

## `services/tool_decision/stored_sample.py` — `logic`

**It may not call the store**: `services/` is `logic`, `tables.py` is `adapter`, and `H-8` sends
that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `built_sample(document)` | builds `ToolDecisionSampleBuilding`, answers a `StoredSample`, or the reason a step did not run. Pure |
| `covered_pairs(pair_counts)` | SQL returns only the pairs that exist; **the empty ones are the finding**, so they are put back here from `DOMAINS × CALL_SHAPES`. Pure |
| `described_labels(labels, catalogs)` | `measured_labels(...)` with this task's `call_counts` and `tool_coverage` passed in. Pure |
| `duplicate_groups(inputs)` | calls `data_quality/duplicate_data_checking.py`, which already does this. Nothing new is written |

## `edge/database.py` — `adapter`

| Name | What it is |
|---|---|
| `KEY_LENGTH = 64` | long enough for a digest-shaped id, short enough for a dialect with an index-length limit |
| `Utc` | `TypeDecorator` — SQLite hands back naive, Postgres hands back the connection's offset; both come out UTC |
| `Base` | the one declarative base every task's tables hang off |
| `database_url()` | `str \| None` — unset or empty is *no store*, never a default file |
| `database_engine()` | one engine for the process, **under a lock**; a changed DSN releases the old pool |
| `open_session()` | `Session \| None` — `None` is an answer every caller has to handle, not a failure |

## `edge/routers/text2text/tool_decision.py` — `adapter` (changed)

**The statistics shapes live here**, because they are the shape of one HTTP answer and nothing
below the edge has a use for them.

| Added | What it does |
|---|---|
| `class ReviewedSample(Sample)` | the thirteen-key envelope, `extra="allow"` |
| `class CorpusStats` | the response body: the totals, the per-facet counts, the filled matrix, the label measurements, the duplicates |
| `POST /records` → `stored_record(request)` | body → `built_sample` → `stored_rows`. **422 naming the step that did not run**; 503 naming the variable where no database is attached |
| `GET /records/stats` → `corpus_stats()` | the profile's SQL, `covered_pairs`, `described_labels`, `duplicate_groups` → `CorpusStats` |
| `GET /records/declared-facets` → `declared_facets()` | the page asks the profile which ticks to draw instead of holding a second copy of the list |

---

## What now contradicts `spec.md`

| Passage | Why it has to go |
|---|---|
| § *The door* | there is no door. A finished sample is kept; an unfinished one is a `422` |
| § *`dataset`* — *the difference, split by why* | the two tables hold the same rows, so there is no difference to split |
| § *What* — *the table that is protected and the table that is sold* | still two tables, but they differ by **what they hold**, not by which rows reach them |
| § *Where each piece is declared*, reqs 1 and 4 | the modality no longer declares the tables, and SQLAlchemy is named in two places |
| § *`record`*, § *`dataset`*, the `(task, id)` key | the table name is the task, so the key is `id` |
| § *`class`*, req 25 | *the modality counts without ever naming a facet* was true of a JSON column, not of eleven columns |
| § *Context* — *the first schema is a migration* | there is no migration |
| § *Invariants*, the `sqlalchemy` line | `tables.py` names it |
| § *Open*, `(task, id)` or `id` alone | answered |
| `plan.md` T3, T6 | were *the migration* and *the door* |

---

## Two things to read closely

**The `withheld` key still exists and no longer does anything here.** A reviewer marking a sample
as not-to-be-used means the page does not post it. If one is posted anyway it is stored like any
other, because nothing below the page reads that key now. Whether the router should refuse it is a
decision about the page and is not taken here.

**The leak check survived the door.** `leaked_values` is not a second opinion about whether a
sample is good — it is the answer to *did the redaction step actually run*, which is exactly the
precondition that replaced the door. If it goes too, a redaction that silently failed puts personal
data in the table that is sold, and nothing in the code would know.
