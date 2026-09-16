# Layout

Where each thing goes. `spec.md` says what must be true, `plan.md` schedules it, this says which
module each sentence lands in. No function bodies.

**This document is true until the tree is.** Once a module exists, the module is the answer.

---

## What each new package is for

**`modalities/text2text/dataset_management/`** — what a finished text2text review becomes once it
is kept: the shape of the stored row, how it is built, and what can be measured about a label. A
sample arrives having already passed every step of the flow, so nothing here decides whether to
keep it.

**`profile/tool_decision/dataset_management/`** — this task's answers to whatever the modality
declares, this task's label measurements, and this task's own two tables with the SQL over them.

**`edge/database.py`** — the DSN, the engine, the session, and the one declarative base every
task's tables hang off.

`R-3` says a module is never named `manager` or `management`, because that names a bucket rather
than a job. `dataset_management` is taken over that rule on purpose, not by oversight.

---

## The tree

```
src/dataforce/
├── modalities/text2text/
│   └── dataset_management/        NEW — the modality's fourth package
│       ├── __init__.py            facade
│       ├── schema.py              shape · StoredSample, DuplicateGroups
│       ├── sample_building.py     logic · left open, to be written against a real sample
│       ├── label_statistics.py    logic · what any text2text label can be measured by
│       └── duplicate_grouping.py  logic · the same input twice, over the whole corpus
├── profile/tool_decision/
│   └── dataset_management/        NEW
│       ├── __init__.py            facade
│       ├── schema.py              adapter · this task's two tables, and the SQL over them
│       ├── sample_building.py     logic   · answers whatever the modality declares
│       └── label_statistics.py    logic   · what THIS task's label can be measured by
├── services/tool_decision/
│   └── dataset_management.py      NEW    logic · one function per endpoint
├── edge/database.py               NEW    adapter · the DSN, the engine, the session, the base
├── edge/routers/text2text/tool_decision.py   CHANGED — the response shapes live here
└── ui/{index.html,app.js,style.css}          CHANGED

tests/
├── modalities/test_label_statistics.py       NEW
├── profile/test_dataset_management.py        NEW
├── store/                                    NEW
│   ├── __init__.py, conftest.py
│   └── test_schema.py, test_database.py
└── edge/test_endpoints.py                    CHANGED
```

---

## `modalities/text2text/dataset_management/schema.py` — `shape`

| Name | What it is |
|---|---|
| `StoredSample` | `input`, `label`, `facets` — the row that is kept. The profile's tables turn it into columns |
| `DuplicateGroups` | `duplicate_content_same_label`, `duplicate_content_diff_label` |

## `modalities/text2text/dataset_management/sample_building.py` — `logic`

**`pass`.** The steps a finished review goes through to become a stored row are not settled, and
drawing them before a real sample has gone through is how a shape gets invented rather than
observed. The module exists so the placement is fixed; what it declares is yours to add.

Everything downstream waits on this file: the profile answers whatever it declares, and until it
declares something the profile's `sample_building.py` has nothing to override.

## `modalities/text2text/dataset_management/duplicate_grouping.py` — `logic`

A duplicate is a fact about a *dataset*, so it is grouped here and not by the data-quality check of
the same word. That one compares a **posted batch** pairwise with an embedding call, its own note
says an index rather than a smaller batch is what a corpus of twenty thousand needs, and it returns
`None` with no shape declared. Sharing code between the two would be sharing a word.

| Function | What it does |
|---|---|
| `duplicate_groups(inputs, labels)` | the two groups: the same input under the same label, and the same input under a different one. Hashed in Python; the digest column is the change to make when that stops being instant |

## `modalities/text2text/dataset_management/label_statistics.py` — `logic`

**One function.** The only thing every text2text label has in common is that it may be absent;
anything past that says `tool`, and `H-10` refuses that word above the profile. If this one moves
down too, the file has no reason to exist and label statistics are entirely the profile's.

| Function | What it does |
|---|---|
| `labelled_share(labels)` | how many stored samples carry a label at all, out of how many. The empty label is a real answer, not a gap |

## `profile/tool_decision/dataset_management/schema.py` — `adapter`

The same thing `schema.py` means everywhere else in this repo — what the stored data looks like —
except that here it is SQLAlchemy, so the tag is `adapter` and not `shape`. It imports `Base` and
`Utc` from `edge/database.py`, so one `MetaData` holds every task's tables; `H-8` allows it, both
are `adapter`. There is no `task` column: the table name is the task.

| Name | What it is |
|---|---|
| `ToolDecisionRecord(Base)` | `id` as `Uuid` — native on Postgres, 32 characters on SQLite, and nothing to pick a length for — the thirteen keys of the review, the two times. The raw side: may hold personal data, never exported |
| `ToolDecisionDataset(Base)` | `id`, `input`, `label`, the two times, **the columns below**, and `notes` |
| — its columns | `language`, `personal_data`, `ambiguous`, `domain`, `call_shape`, `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid` — each one true of every sample in the table, and expected to stay true |
| — its `notes` | JSON. `have_conversation_flow` and `direction` start here, because each is true of a *group* of label sets rather than of the table. **A facet added later starts here too**, always, and becomes a column only when someone is grouping by it often enough for the scan to hurt |
| `created_tables(engine)` | `Base.metadata.create_all`. With no migration folder, this is the only thing that makes a table |
| `stored_rows(session, document, sample)` | one `session.begin()`, a `merge` into each table. **Both always**: the tables differ by what they hold, not by which rows reach them |
| `carried_created_time(session, id)` | read before merging — `merge` replaces the whole row, so the column that never changes has to be carried forward |
| `row_counts(session)` | how many rows each table holds. They agree, and a run where they do not is a bug rather than a figure |
| `counted_by_facet(session)` | one `GROUP BY` per facet column. The column names are this task's, and this is the layer allowed to say them |
| `counted_by_pair(session, row_facet, column_facet)` | `GROUP BY` two columns — only the pairs that exist |
| `stored_labels(session)` | the `label` column alone, for `label_statistics` |
| `shipped_inputs(session)` | the `input` and `label` columns, for the duplicate grouping — the two groups differ by whether the labels agree |
| `rebuilt_dataset(session, building)` | delete every row and recompute from the record table |

## `profile/tool_decision/dataset_management/sample_building.py` — `logic`

Waits on the modality file. What it will have to say, whatever shape the interface takes:

| | |
|---|---|
| the input that ships | `{messages, tools}` — from the `new_` keys, or the originals where a `new_` key is `null` |
| the facets it computes | `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid` |
| the facets it asks for | `direction`, `domain`, `have_conversation_flow`, `call_shape` |
| `MATRIX_AXES`, `DOMAINS`, `CALL_SHAPES` | the axes the page crosses and the values it offers |

## `profile/tool_decision/dataset_management/label_statistics.py` — `logic`

Where the real label measurements are, because every one of them says `tool` and only this layer
may.

| Function | What it does |
|---|---|
| `called_tools(label)` | the tool names the label calls |
| `required_parameters(tool)` | `function.parameters.required` |
| `schema_valid_label(label, catalog)` | BFCL's AST check: every call names a tool in the catalog and supplies its required parameters |
| `call_counts(labels)` | how many labels make 0, 1, or more calls — `0` is the no-call sample, counted rather than treated as missing |
| `tool_coverage(labels, catalogs)` | which offered tools are ever called, and the tail: a corpus where two tools carry 90% of the calls |

## `services/tool_decision/dataset_management.py` — `logic`

**It may not call the store**: `services/` is `logic`, the profile's `schema.py` is `adapter`, and
`H-8` sends that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `covered_pairs(pair_counts)` | SQL returns only the pairs that exist; **the empty ones are the finding**, so they are put back here from `DOMAINS × CALL_SHAPES`. Pure |
| `described_labels(labels, catalogs)` | `labelled_share(...)` with this task's `call_counts` and `tool_coverage` beside it. Pure |

The function that turns one posted document into a `StoredSample` belongs here too, and is not
named yet, because it composes whatever `sample_building.py` ends up declaring.

## `edge/database.py` — `adapter`

| Name | What it is |
|---|---|
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
| `POST /records` → `stored_record(request)` | body → the service → `stored_rows`. 503 naming the variable where no database is attached |
| `GET /records/stats` → `corpus_stats()` | the profile's SQL, `covered_pairs`, `described_labels`, `duplicate_groups` → `CorpusStats` |
| `GET /records/declared-facets` → `declared_facets()` | the page asks the profile which ticks to draw instead of holding a second copy of the list |

---

## Adding a facet later

The question a column has to survive is *what happens to the rows that are already there*, and the
answer splits on who fills the facet — which is why the derived/declared line outlives the two
types that held it.

| | A **derived** facet — `number_turns`, `schema_valid`, `personal_data` | A **declared** facet — `domain`, `ambiguous`, `have_conversation_flow` |
|---|---|---|
| Where it comes from | computed from `record`, which keeps the whole review | a person ticked it, once, on a page that has since moved on |
| Old rows after it is added | `rebuilt_dataset` recomputes every one of them. Nothing is lost | **nothing can fill them.** They are unknown, and stay unknown unless somebody re-reviews every old sample by hand |
| So it may be | a column, added when wanted — the cost is one rebuild | `notes`, until you are sure. A declared column added late is a column that is `NULL` for the whole corpus that existed before it |

That is why `have_conversation_flow` belongs in `notes`: it is declared, so the day it becomes a
column every sample already in the table is permanently blank on it, and a statistic over it would
measure when the facet was introduced rather than what the corpus holds.

With no migrations, a column is also an `ALTER TABLE` somebody writes by hand against a live
database. A key in `notes` is nothing at all — old rows simply do not have it, which is the same
*unknown* as a `NULL` without a schema change to perform.

---

## One thing to read closely

**Nothing checks that a computed facet and a ticked one stay apart.** The rule is real — a derived
facet is never typed, a declared one is never computed — and the only thing holding it is that the
two sets of names are written in two different places in `sample_building.py`. A column does not
say who filled it, so the table cannot tell the difference and no test reads for it either.
