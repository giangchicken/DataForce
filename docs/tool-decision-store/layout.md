# Layout

Where each thing goes, and what each file holds. `spec.md` says what must be true and `plan.md`
schedules it; this says which module every sentence of the two lands in. No function bodies.

**This document is true until the tree is.** Once a module exists, the module is the answer.

**`spec.md` has not been swept to this yet** — § *What now contradicts `spec.md`* lists what has to
go.

---

## What each new package is for

**`modalities/text2text/sample_release/`** — one question, asked of every text2text sample and
answered the same way for every task: *may this leave the protected table for the sellable one?*
That is a legal question about personal data in text, not a quality question about the task, which
is why it is declared once here and no task may write its own. Around it: the two shapes the answer
comes in, and three sockets through which a task says what its own input is made of without being
able to touch the condition. **Nothing that counts, sums or renders belongs in this package.**

**`profile/tool_decision/sample_release/`** — this task's answers to those three sockets, and this
task's own two tables with the SQL over them.

**`edge/database.py`** — the DSN, the engine, the session, and the one declarative base every
task's tables hang off.

---

## The tree

```
src/dataforce/
├── modalities/text2text/
│   └── sample_release/            NEW — the modality's fourth package
│       ├── __init__.py            facade
│       ├── schema.py              shape · five names, and no more
│       └── release_checking.py    logic · the gate, and the text2text rules under it
├── profile/tool_decision/
│   └── sample_release/            NEW — the first profile part that needs two files
│       ├── __init__.py            facade
│       ├── release_checking.py    logic   · answers the three sockets
│       └── tables.py              adapter · this task's two tables, and the SQL over them
├── services/tool_decision/
│   └── sample_release.py          NEW    logic · one function per endpoint
├── edge/database.py               NEW    adapter · the DSN, the engine, the session, the base
├── edge/routers/text2text/tool_decision.py   CHANGED — the response shapes live here
└── ui/{index.html,app.js,style.css}          CHANGED

tests/
├── modalities/test_release_checking.py       NEW
├── profile/test_release_checking.py          NEW
├── store/                                    NEW
│   ├── __init__.py, conftest.py
│   └── test_tables.py, test_database.py
└── edge/test_endpoints.py                    CHANGED
```

---

## `modalities/text2text/sample_release/schema.py` — `shape`

Five names. Each one exists because the gate cannot be written without it.

| Name | What it is |
|---|---|
| `DerivedSampleFacets` | `NewType` over `Mapping[str, Any]` — what is computed from the sample, so nobody may type it |
| `DeclaredSampleFacets` | `NewType` over `Mapping[str, Any]` — what a reviewer ticks, so nothing may compute it |
| `ReleasedSample` | `input`, `label`, `facets` — a sample the gate let through. The profile's table turns it into columns |
| `WithheldSample` | `reason` — a sample it did not, and which of the three conditions stopped it |
| `CheckedRelease` | `ReleasedSample \| WithheldSample` — what the gate returns, before anyone knows which |

## `modalities/text2text/sample_release/release_checking.py` — `logic`

| Function | What it does |
|---|---|
| `class ReleaseChecking(ABC)` | what the task subclasses, beside `PersonalDataChecking` |
| ├ `checked_release(document)` | **concrete, not abstract.** The gate: asks `withheld_reason`, builds a `ReleasedSample` where there is none |
| ├ `shipped_input(document)` | **abstract** · what the task's `input` column holds |
| ├ `derived_facets(document)` | **abstract** · the task's half of the derived facets |
| └ `declared_facets()` | **abstract** · which ticks the page must draw |
| `withheld_reason(document)` | `str \| None` — `withheld`, `personal_data: null`, or a leaked value. The decision, kept apart from the building (`C-6`) |
| `leaked_values(document)` | confirmed span values still present in the three `new_` keys. Only the redacted copies are read; the originals hold raw content on purpose |
| `redacted_personal_data(document)` | the modality's derived facet: the `personal_data_class` values, `[]` where the sample had none |
| `accepted_declaration(posted, required)` | the declared half read off the posted `class`; refuses a derived facet, refuses a missing `language` |
| `shipped_label(document)` | `new_label` — a `new_` key is text2text's, so reading it is this layer's |
| `merged_facets(derived, declared)` | the two halves as one map, **raising on an overlapping key** |

## `profile/tool_decision/sample_release/release_checking.py` — `logic`

| Function | What it does |
|---|---|
| `class ToolDecisionReleaseChecking(ReleaseChecking)` | named as `ToolDecisionPersonalChecking` already is |
| ├ `shipped_input(document)` | `{messages, tools}` — from the `new_` keys, or the originals where a `new_` key is `null` |
| ├ `derived_facets(document)` | `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid` |
| └ `declared_facets()` | `("direction", "domain", "have_conversation_flow", "call_shape")` |
| `shipped_turns(document)` | the messages that ship |
| `shipped_catalog(document)` | the catalog that ships — the count is of what ships, not of what arrived |
| `called_tools(label)` | the tool names the label calls |
| `required_parameters(tool)` | `function.parameters.required` |
| `schema_valid_label(label, catalog)` | BFCL's AST check: every call names a tool in the catalog and supplies its required parameters |
| `MATRIX_AXES`, `DOMAINS`, `CALL_SHAPES` | the axes the page crosses and the values it offers |

## `profile/tool_decision/sample_release/tables.py` — `adapter`

Imports `Base`, `Utc` and `KEY_LENGTH` from `edge/database.py`, so one `MetaData` holds every
task's tables. `H-8` allows it: both are `adapter`. No `task` column — the table name is the task.

| Name | What it is |
|---|---|
| `ToolDecisionRecord(Base)` | `id`, the thirteen keys of the review, the two times. The raw side: may hold personal data, never exported |
| `ToolDecisionDataset(Base)` | `id`, `input`, `label`, then **each facet as its own column** — `language`, `ambiguous`, `personal_data`, `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid`, `direction`, `domain`, `have_conversation_flow`, `call_shape` — and the two times |
| `created_tables(engine)` | `Base.metadata.create_all`. With no migration folder, this is the only thing that makes a table |
| `stored_rows(session, document, release)` | `merge` into the record table, `merge`-or-`delete` on the dataset table, one `session.begin()`. It takes the gate's answer rather than calling the gate (`C-6`) |
| `carried_created_time(session, id)` | read before merging — `merge` replaces the whole row, so the column that never changes has to be carried forward |
| `row_counts(session)` | how many rows each table holds, and how many were withheld |
| `counted_by_facet(session)` | one `GROUP BY` per facet column. The column names are this task's, and this is the layer allowed to say them |
| `counted_by_pair(session, row_facet, column_facet)` | `GROUP BY` two columns — only the pairs that exist |
| `shipped_inputs(session)` | the `input` column alone, for the duplicate scan |
| `covered_tools(session)` | the tool-coverage tail, read out of `input` and `label` |
| `rebuilt_dataset(session, release)` | delete every row and recompute from the record table |

## `services/tool_decision/sample_release.py` — `logic`

**It may not call the store**: `services/` is `logic`, `tables.py` is `adapter`, and `H-8` sends
that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `checked_sample(document)` | builds `ToolDecisionReleaseChecking`, asks the gate, answers a `CheckedRelease`. Pure |
| `covered_pairs(pair_counts)` | SQL returns only the pairs that exist; **the empty ones are the finding**, so they are put back here from `DOMAINS × CALL_SHAPES`. Pure |
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
| `class StoredWhere` | which table took the row, and why the other did not |
| `class CorpusStats` | the response body: the totals, the per-facet counts, the filled matrix, the duplicates |
| `POST /records` → `stored_record(request)` | body → `checked_sample` → `stored_rows`. 503 naming the variable where no database is attached |
| `GET /records/stats` → `corpus_stats()` | the profile's SQL, `covered_pairs`, `duplicate_groups` → `CorpusStats` |
| `GET /records/declared-facets` → `declared_facets()` | the page asks the profile which ticks to draw instead of holding a second copy of the list |

---

## What now contradicts `spec.md`

| Passage | Why it has to go |
|---|---|
| § *Where each piece is declared*, reqs 1 and 4 | the modality no longer declares the tables, and SQLAlchemy is named in two places |
| § *`record`*, § *`dataset`*, the `(task, id)` key | the table name is the task, so the key is `id` |
| § *`class`*, req 25 | *the modality counts without ever naming a facet* was true of a JSON column, not of eleven columns |
| § *Context* — *the first schema is a migration* | there is no migration |
| § *Invariants*, the `sqlalchemy` line | `tables.py` names it |
| § *Design*, *Why the corpus is the modality's* | most of it moved |
| § *Open*, `(task, id)` or `id` alone | answered |
| `plan.md` T3 | was *the first schema is a migration* |

---

## Two things to read closely

**A facet is a column, so adding one is an `ALTER TABLE` a person writes.** With no migration
folder, `created_tables` only ever *creates*: it does not alter a table that already exists. On a
database that holds rows, a new tick is a hand-written statement.

**`H-5` is bent on purpose.** *Translate framework types at the outermost layer* is why the tables
were at the edge. They are one layer in now, so `tables.py` is the only file in a profile tagged
`adapter` — and the import-direction guard allows it, while `services/` still cannot reach it.
