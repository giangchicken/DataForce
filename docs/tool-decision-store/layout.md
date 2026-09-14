# Layout

Where each thing goes, and what each file holds. `spec.md` says what must be true and `plan.md`
schedules it; this says which module every sentence of the two lands in, so a task never has to
invent a placement. It carries no function bodies.

**This document is true until the tree is.** Once a module exists, the module is the answer and a
row here that disagrees with it is this file being wrong. Delete a row when the code it describes
lands and the code says it better.

**`spec.md` has not been swept to this yet.** The tables moved into the profile after it was
written, and § *What now contradicts `spec.md`* at the bottom lists every passage that has to go.

---

## The tree

```
src/dataforce/
├── modalities/text2text/
│   └── corpus/                    NEW — the modality's fourth package
│       ├── __init__.py            facade
│       ├── schema.py              shape
│       ├── sample_projection.py   logic  · one document -> what ships, or a refusal
│       └── sample_statistics.py   logic  · counts in -> the numbers a person reads
├── profile/tool_decision/
│   ├── corpus.py                  NEW    logic   · answers the three sockets
│   └── store.py                   NEW    adapter · THIS task's two tables, and the SQL over them
├── services/tool_decision/
│   └── corpus.py                  NEW    logic · one function per endpoint
├── edge/store.py                  NEW    adapter · the DSN, the engine, the session, the base
├── edge/routers/text2text/tool_decision.py   CHANGED
└── ui/{index.html,app.js,style.css}          CHANGED

migrations/                        NEW — outside the package: ruff reads it, mypy --strict does not
├── env.py                         imports every profile, so Base.metadata knows what to migrate
├── script.py.mako
└── versions/<rev>_tool_decision_tables.py

tests/
├── modalities/                    NEW
│   ├── test_sample_projection.py
│   └── test_sample_statistics.py
├── profile/test_corpus.py         NEW
├── store/                         NEW
│   ├── __init__.py, conftest.py
│   └── test_store.py, test_migration.py
└── edge/test_endpoints.py         CHANGED
```

---

## `modalities/text2text/corpus/schema.py` — `shape`

Imports nothing from this package. Nothing here decides anything; these are the nouns. They fall
into three groups, and knowing which group a name is in is most of knowing what it means.

**One sample.** What the door is handed, and what it hands back.

| Name | What it is |
|---|---|
| `DerivedSampleFacets` | `NewType` over `Mapping[str, Any]` — what is computed from the sample, so nobody may type it |
| `DeclaredSampleFacets` | `NewType` over `Mapping[str, Any]` — what a reviewer ticks, so nothing may compute it |
| `ReleasedSample` | `input`, `label`, `facets` — a sample the door let through. The profile's table is what turns it into columns |
| `WithheldSample` | `reason`, `outcome` — a sample it did not, and which of the three conditions stopped it |
| `ProjectedSample` | `ReleasedSample \| WithheldSample` — what the door returns, before anyone knows which |

**One number.**

| Name | What it is |
|---|---|
| `CountWithTotal` | `count`, `out_of` — 12 out of 40. It says nothing about what was counted; the field holding it does |

**The whole corpus.**

| Name | What it is |
|---|---|
| `SampleTotals` | how many rows in each table, and the gap split by why |
| `FacetSampleCounts` | `Mapping[facet name, Mapping[value, samples]]` — what the profile's `GROUP BY` comes back as |
| `PairedSampleCount` | `row`, `column`, `count` — how many samples carry two given values at once |
| `FacetCoverageMatrix` | `rows`, `columns`, `cells`, `empty_cells` — every pair of two facets' values, the pairs nothing carries included |
| `DuplicateSamples` | the two groups, under the names `DuplicateGroups` already uses |
| `CorpusStatistics` | the four above, composed — what one `GET .../records/stats` answers |

## `modalities/text2text/corpus/sample_projection.py` — `logic`

The one piece that stays the modality's, because the condition it holds is a law and a law that
exists per task drifts.

| Function | What it does |
|---|---|
| `class SampleProjection(ABC)` | what the task subclasses |
| ├ `projected_sample(document)` | **concrete, not abstract.** The door: asks `withheld_reason`, and builds a `ReleasedSample` where there is none. No task writes its own |
| ├ `shipped_input(document)` | **abstract** · what the task's `input` column holds |
| ├ `derived_facets(document)` | **abstract** · the task's half of the derived facets |
| └ `declared_facets()` | **abstract** · which ticks the page must draw |
| `withheld_reason(document)` | `str \| None` — `withheld`, `personal_data: null`, or a leaked value. The decision, kept apart from the building (`C-6`) |
| `leaked_values(document)` | confirmed span values still present in the three `new_` keys. Only the redacted copies are read; the originals hold raw content on purpose |
| `redacted_personal_data(document)` | the modality's derived facet: the `personal_data_class` values, `[]` where the sample had none |
| `accepted_declaration(posted, required)` | the declared half read off the posted `class`; refuses a derived facet, refuses a missing `language` |
| `shipped_label(document)` | `new_label` — a `new_` key is text2text's, so reading it is this layer's |
| `merged_facets(derived, declared)` | the two halves as one map, **raising on an overlapping key** — the one place *no facet is in both halves* is held |

## `modalities/text2text/corpus/sample_statistics.py` — `logic`

**Smaller than it was.** With the facets as real columns, the counting is `GROUP BY` and belongs in
the profile's adapter. What is left here is the arithmetic that SQL does not do: filling in the
pairs no row carries, and composing. No function here names a facet.

| Function | What it does |
|---|---|
| `sample_totals(record_count, dataset_count, withheld_count)` | how much, and the gap split by `withheld` against never scanned |
| `facet_coverage_matrix(pair_counts, row_values, column_values)` | the product of the two axes, **every empty cell present and zero**. SQL returns only the pairs that exist; the empty ones are the finding, so they are put back here |
| `duplicate_samples(inputs)` | grouped by the same input, hashed in Python; the digest is the change to make when that stops being instant |
| `aggregated_statistics(totals, facet_counts, matrix, duplicates)` | the four, composed into `CorpusStatistics` |

## `profile/tool_decision/corpus.py` — `logic`

| Function | What it does |
|---|---|
| `class ToolDecisionCorpus(SampleProjection)` | sits beside `ToolDecisionPersonalChecking` and the two prediction classes |
| ├ `shipped_input(document)` | `{messages, tools}` — from the `new_` keys, or from the originals where a `new_` key is `null` |
| ├ `derived_facets(document)` | `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid` |
| └ `declared_facets()` | `("direction", "domain", "have_conversation_flow", "call_shape")` |
| `shipped_turns(document)` | the messages that ship |
| `shipped_catalog(document)` | the catalog that ships — the count is of what ships, not of what arrived |
| `called_tools(label)` | the tool names the label calls |
| `required_parameters(tool)` | `function.parameters.required` |
| `schema_valid_label(label, catalog)` | BFCL's AST check: every call names a tool in the catalog and supplies its required parameters |
| `MATRIX_AXES` | `("domain", "call_shape")` |
| `DOMAINS`, `CALL_SHAPES` | the values the page offers |

## `profile/tool_decision/store.py` — `adapter`

**This task's own two tables.** It imports `Base`, `Utc` and `KEY_LENGTH` from `edge/store.py` so
that one `MetaData` holds every task's tables and Alembic sees them all. `H-8` allows it: both are
`adapter`. There is no `task` column any more — the table name is the task.

| Name | What it is |
|---|---|
| `ToolDecisionRecord(Base)` | `id`, the thirteen keys of the review, `created_time`, `modified_time`. The raw side: may hold personal data, never exported |
| `ToolDecisionDataset(Base)` | `id`, `input`, `label`, then **each facet as its own column** — `language`, `ambiguous`, `personal_data`, `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid`, `direction`, `domain`, `have_conversation_flow`, `call_shape` — and the two times |
| `stored_rows(session, document, projection)` | `merge` into the record table, `merge`-or-`delete` on the dataset table, one `session.begin()`. It takes the door's answer rather than calling the door (`C-6`) |
| `carried_created_time(session, id)` | read before merging — `merge` replaces the whole row, so the column that never changes has to be carried forward |
| `row_counts(session)` | how many rows each table holds, and how many were withheld |
| `counted_by_facet(session)` | one `GROUP BY` per facet column, back as `FacetSampleCounts`. The column names are this task's, and this is the layer allowed to say them |
| `counted_by_pair(session, row_facet, column_facet)` | `GROUP BY` two columns — only the pairs that exist |
| `shipped_inputs(session)` | the `input` column alone, for the duplicate scan |
| `covered_tools(session)` | the tool-coverage tail, read out of `input` and `label` |
| `rebuilt_dataset(session, projection)` | delete every row and recompute from the record table |

## `services/tool_decision/corpus.py` — `logic`

Two functions, and **neither may call the store**: `services/` is `logic`, both stores are
`adapter`, and `H-8` sends that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `checked_sample(document)` | builds `ToolDecisionCorpus`, asks the door, answers a `ProjectedSample`. Pure |
| `described_corpus(counts, facet_counts, pair_counts, inputs, coverage)` | the profile's SQL answers in, `aggregated_statistics(...)` plus `MATRIX_AXES` out. Pure |

## `edge/store.py` — `adapter`

One file, and now only the plumbing: no table is declared here.

| Name | What it is |
|---|---|
| `KEY_LENGTH = 64` | long enough for a digest-shaped id, short enough for a dialect with an index-length limit |
| `Utc` | `TypeDecorator` — SQLite hands back naive, Postgres hands back the connection's offset; both come out UTC |
| `Base` | the one declarative base every profile's tables hang off, so Alembic has one `MetaData` to read |
| `database_url()` | `str \| None` — unset or empty is *no store*, never a default file |
| `database_engine()` | one engine for the process, **under a lock**; a changed DSN releases the old pool |
| `open_session()` | `Session \| None` — `None` is an answer every caller has to handle, not a failure |

## `edge/routers/text2text/tool_decision.py` — `adapter` (changed)

| Added | What it does |
|---|---|
| `class ReviewedSample(Sample)` | the thirteen-key envelope, `extra="allow"` |
| `class StoredWhere` | which table took the row, and why the other did not |
| `POST /records` → `stored_record(request)` | body → `checked_sample` → `stored_rows`. 503 naming the variable where no database is attached |
| `GET /records/stats` → `corpus_stats()` | the profile's SQL → `described_corpus` |
| `GET /records/declared-facets` → `declared_facets()` | the page asks the profile which ticks to draw instead of holding a second copy of the list |

---

## What now contradicts `spec.md`

| Passage | Why it has to go |
|---|---|
| § *Where each piece is declared*, req 1 | says the modality declares the two tables |
| § *Where each piece is declared*, req 4 | says `edge/store/` is the only place SQLAlchemy is named |
| § *`record`* and § *`dataset`*, the `(task, id)` key | the table name is the task now, so the key is `id` |
| § *`class`*, req 25 | *the modality counts without ever naming a facet* was true of a JSON column and is not true of eleven columns |
| § *Invariants*, the `sqlalchemy` line | `profile/tool_decision/store.py` names it |
| § *Design*, *Why the corpus is the modality's* | half of it moved |
| § *Open*, `(task, id)` or `id` alone | answered |

---

## Three things to read closely

**A facet is now a migration.** Ticking a new box used to be a new key in a JSON column and no
schema change at all. With eleven real columns it is `ALTER TABLE` and a revision file. What is
bought for that: an index on `domain`, a `GROUP BY` instead of a Python scan over every row, and a
misspelled facet name failing at write instead of quietly becoming a twelfth facet nobody counts.

**`H-5` is bent on purpose.** *Translate framework types at the outermost layer* is why the tables
were at the edge. They are one layer in now, so `profile/<task>/store.py` is the only file in a
profile tagged `adapter`, and the guard that checks import direction allows it — `adapter` may
import `shape`, `logic` and `adapter`, and `services/` still cannot reach any of it.

**`language` has no route in yet.** § *`class`* says it is declared at step 1 and carried rather
than asked twice — but the record's thirteen keys do not include it, so it has to arrive inside the
declared half of `class` that the page posts, filled by `app.js` from step 1 rather than by a tick.
That is why `accepted_declaration` refuses a missing `language` instead of computing one.
