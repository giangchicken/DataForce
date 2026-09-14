# Layout

Where each thing goes, and what each file holds. `spec.md` says what must be true and `plan.md`
schedules it; this says which module every sentence of the two lands in, so a task never has to
invent a placement. It carries no function bodies and takes no decision either of the other two
documents has not already taken.

**This document is true until the tree is.** Once a module exists, the module is the answer and a
row here that disagrees with it is this file being wrong. Delete a row when the code it describes
lands and the code says it better.

---

## The tree

```
src/dataforce/
├── modalities/text2text/
│   └── corpus/                    NEW — the modality's fourth package
│       ├── __init__.py            facade
│       ├── schema.py              shape
│       ├── sample_projection.py   logic  · one document -> one row, or a refusal
│       └── sample_statistics.py   logic  · many samples -> the numbers
├── profile/tool_decision/
│   └── corpus.py                  NEW    logic · answers the three sockets
├── services/tool_decision/
│   └── corpus.py                  NEW    logic · one function per endpoint
├── edge/store.py                  NEW    adapter · one file: the DSN, the engine, the
│                                         tables, and the two writes in one transaction
├── edge/routers/text2text/tool_decision.py   CHANGED
└── ui/{index.html,app.js,style.css}          CHANGED

migrations/                        NEW — outside the package: ruff reads it, mypy --strict does not
├── env.py
├── script.py.mako
└── versions/<rev>_record_and_dataset.py

tests/
├── modalities/                    NEW — the suite's fourth directory
│   ├── __init__.py
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
| `ReleasedSample` | `input`, `label`, `facets` — a sample the door let through, in the shape `dataset` stores |
| `WithheldSample` | `reason`, `outcome` — a sample it did not, and which of the three conditions stopped it |
| `ProjectedSample` | `ReleasedSample \| WithheldSample` — what the door returns, before anyone knows which |

**One number.** Every number the page shows is one of these, never a bare percentage.

| Name | What it is |
|---|---|
| `CountWithTotal` | `count`, `out_of` — 12 out of 40. It says nothing about what was counted; the field holding it does |

**The whole corpus.** Every one of these is many samples reduced to something a person can read.

| Name | What it is |
|---|---|
| `SampleTotals` | how many rows in `record`, how many in `dataset`, and the gap split by why |
| `FacetSampleCounts` | `Mapping[facet name, Mapping[value, samples]]` — how many samples carry each value of each facet |
| `PairedSampleCount` | `row`, `column`, `count` — how many samples carry two given values at once |
| `FacetCoverageMatrix` | `rows`, `columns`, `cells`, `empty_cells` — every pair of two facets' values, the pairs nothing carries included |
| `DuplicateSamples` | the two groups, under the names `DuplicateGroups` already uses |
| `CorpusStatistics` | the four above, composed — what one `GET .../records/stats` answers |

## `modalities/text2text/corpus/sample_projection.py` — `logic`

| Function | What it does |
|---|---|
| `class SampleProjection(ABC)` | what the task subclasses |
| ├ `projected_sample(document)` | **concrete, not abstract.** The door: asks `withheld_reason`, and builds a `ReleasedSample` where there is none. No task writes its own |
| ├ `shipped_input(document)` | **abstract** · what `dataset.input` holds |
| ├ `derived_facets(document)` | **abstract** · the task's half of the derived facets |
| └ `declared_facets()` | **abstract** · which ticks the page must draw |
| `withheld_reason(document)` | `str \| None` — `withheld`, `personal_data: null`, or a leaked value. The decision, kept apart from the building (`C-6`) |
| `leaked_values(document)` | confirmed span values still present in the three `new_` keys. Only the redacted copies are read; the originals hold raw content on purpose |
| `redacted_personal_data(document)` | the modality's derived facet: the `personal_data_class` values, `[]` where the sample had none |
| `accepted_declaration(posted, required)` | the declared half read off the posted `class`; refuses a derived facet, refuses a missing `language` |
| `shipped_label(document)` | `new_label` — a `new_` key is text2text's, so reading it is this layer's |
| `merged_facets(derived, declared)` | the two halves as one map, **raising on an overlapping key** — the one place *no facet is in both halves* is held |

## `modalities/text2text/corpus/sample_statistics.py` — `logic`

Takes the rows of the two tables, returns the numbers. No function here names a facet.

| Function | What it does |
|---|---|
| `sample_totals(record_count, dataset_rows)` | how much, and the gap split by `withheld` against never scanned |
| `facet_sample_counts(dataset_rows)` | a count per value of **every key** `class` holds — it reads the keys of a JSON column, so no facet's name is written here |
| `facet_coverage_matrix(dataset_rows, row_facet, column_facet)` | the product of the two axes' values, **every empty cell present and zero** |
| `duplicate_samples(dataset_rows)` | grouped by the same input, hashed in Python; the digest is the change to make when that stops being instant |
| `aggregated_statistics(dataset_rows, axes)` | the above, composed into `CorpusStatistics`. **`record` is not read**: with the evidence numbers gone, every statistic comes off `dataset` |

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
| `tool_coverage(dataset_rows)` | the statistic that reads inside `input` and `label`. The service passes it; it is not a fourth socket |
| `MATRIX_AXES` | `("domain", "call_shape")` |
| `DOMAINS`, `CALL_SHAPES` | the values the page offers. The store validates no string — § *Open* |

## `services/tool_decision/corpus.py` — `logic`

Two functions, and **neither may call the store**: `services/` is `logic`, `edge/store.py` is
`adapter`, and `H-8` sends that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `checked_sample(document)` | builds `ToolDecisionCorpus`, asks the door, answers a `ProjectedSample`. Pure |
| `described_corpus(record_count, dataset_rows)` | `aggregated_statistics(...)` plus `tool_coverage(...)` plus `MATRIX_AXES`. Pure |

## `edge/store.py` — `adapter`

One file. The DSN, the engine, the two declarative classes and the writes are one job — talking to
a database — and splitting them made three modules that only ever call each other.

| Name | What it is |
|---|---|
| `KEY_LENGTH = 64` | long enough for a digest-shaped id, short enough for a dialect with an index-length limit |
| `Utc` | `TypeDecorator` — SQLite hands back naive, Postgres hands back the connection's offset; both come out UTC |
| `Base`, `Record`, `Dataset` | the two tables, keyed `(task, id)`, with the `class` column name pinned and the attribute named `facets` |
| `database_url()` | `str \| None` — unset or empty is *no store*, never a default file |
| `database_engine()` | one engine for the process, **under a lock**; a changed DSN releases the old pool |
| `open_session()` | `Session \| None` — `None` is an answer every caller has to handle, not a failure |
| `stored_rows(session, task, document, projection)` | `merge` into `record`, `merge`-or-`delete` on `dataset`, one `session.begin()`. It takes the door's answer rather than calling the door (`C-6`) |
| `carried_created_time(session, task, id)` | read before merging — `merge` replaces the whole row, so the column that never changes has to be carried forward |
| `record_count(session, task)` | how many rows `record` holds. Only the count, now that nothing reads the documents |
| `dataset_rows(session, task)` | the rows every statistic is taken over |
| `rebuilt_dataset(session, task, project)` | delete every row and recompute from `record`; takes the projection as an argument |

## `edge/routers/text2text/tool_decision.py` — `adapter` (changed)

| Added | What it does |
|---|---|
| `class ReviewedSample(Sample)` | the thirteen-key envelope, `extra="allow"`. Not `Record`: `R-2` refuses a name that already names a table |
| `class StoredWhere` | which table took the row, and why the other did not |
| `POST /records` → `stored_record(request)` | body → `checked_sample` → `stored_rows`. 503 naming the variable where no database is attached |
| `GET /records/stats` → `corpus_stats()` | `dataset_rows` and `record_count` → `described_corpus` |
| `GET /records/declared-facets` → `declared_facets()` | the page asks the profile which ticks to draw instead of holding a second copy of the list |

---

## Four things to read closely

**`language` has no route in yet.** § *`class`* says it is declared at step 1 and carried rather
than asked twice — but the record's thirteen keys do not include it, so it has to arrive inside the
declared half of `class` that the page posts, filled by `app.js` from step 1 rather than by a tick.
That is why `accepted_declaration` refuses a missing `language` instead of computing one. The spec
is one sentence short of saying this, and the sentence is about the page, so it is not taken here.

**The door is `projected_sample`, and it is not abstract.** A task overrides `shipped_input` to say
what the input holds, and cannot override the `khử nhận dạng` condition. That is deliberate:
§ *The door* says no task writes its own, because a legal condition that exists per task drifts.

**`described_corpus` is where *three sockets, and everything else is an argument* gets tested.** If
it reads badly — the service having to know too much about the profile — the answer is a fourth
socket and the plan's decision was wrong. `plan.md` T17 says so, so whoever writes it knows what
they are checking.

**Where `Record` and `Dataset` are declared is not settled.** They sit in `edge/store.py` here
because there are two tables for every task and a new task adds none: `task` is a key column, and
what differs between tasks lives inside two JSON columns, which is what the three sockets fill. The
open question is whether a task should instead declare its own tables in `profile/<task>/`. It
would put SQLAlchemy in `profile/`, which `H-8` reaches through its import table — `logic` may
import `shape` and nothing else — and it would make `migrations/env.py` import every profile in
order to see what to migrate. That is a decision, not an oversight, and it is the user's.
