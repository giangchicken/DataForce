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
├── edge/store/                    NEW
│   ├── __init__.py                facade
│   ├── session.py                 adapter · the DSN, the engine, the session
│   ├── schema.py                  shape   · the two declarative classes
│   └── corpus_rows.py             adapter · two writes in one transaction, and the reads
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
│   ├── test_session.py, test_schema.py, test_migration.py
│   └── test_corpus_rows.py
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
| `SellableSample` | `input`, `label`, `facets` — a sample the door let through, in the shape `dataset` stores |
| `WithheldSample` | `reason`, `outcome` — a sample it did not, and which of the three conditions stopped it |
| `ProjectedSample` | `SellableSample \| WithheldSample` — what the door returns, before anyone knows which |

**One number.** Every number the page shows is one of these, never a bare percentage.

| Name | What it is |
|---|---|
| `SampleRatio` | `count`, `out_of` — 12 samples out of 40, kept as two numbers so the denominator cannot go missing |
| `SampleAverage` | `mean`, `over` — a mean, and how many samples it is a mean of |
| `UnmeasuredStatistic` | `statistic`, `reason` — the slot a number would sit in, saying in words why there is none |
| `UNMEASURED_AGREEMENT` | the one that exists today: agreement, because Krippendorff's α needs two people on one sample |

**The whole corpus.** Every one of these is many samples reduced to something a person can read.

| Name | What it is |
|---|---|
| `SampleTotals` | how many rows in `record`, how many in `dataset`, and the gap split by why |
| `SampleFreshness` | how much arrived in the last 7 and 30 days, and the newest and oldest `modified_time` |
| `FacetSampleCounts` | `Mapping[facet name, Mapping[value, samples]]` — how many samples carry each value of each facet |
| `PairedSampleCount` | `row`, `column`, `count` — how many samples carry two given values at once |
| `FacetCoverageMatrix` | `rows`, `columns`, `cells`, `empty_cells` — every pair of two facets' values, the pairs nothing carries included |
| `HumanEvidence` | `human_edit_rate`, `panel_disagreement`, `redaction_outcomes` — the three that show a person was here |
| `DuplicateSamples` | the two groups, under the names `DuplicateGroups` already uses |
| `CorpusStatistics` | the six above, composed — what one `GET .../records/stats` answers |

## `modalities/text2text/corpus/sample_projection.py` — `logic`

| Function | What it does |
|---|---|
| `class SampleProjection(ABC)` | what the task subclasses |
| ├ `projected_sample(document)` | **concrete, not abstract.** The door: asks `withheld_reason`, and builds a `SellableSample` where there is none. No task writes its own |
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
| `sample_totals(record_rows, dataset_rows)` | how much, and the gap split by `withheld` against never scanned |
| `sample_freshness(dataset_rows)` | the 7- and 30-day counts, newest and oldest |
| `facet_sample_counts(dataset_rows)` | a count per value of **every key** `class` holds — it reads the keys of a JSON column, so no facet's name is written here |
| `facet_coverage_matrix(dataset_rows, row_facet, column_facet)` | the product of the two axes' values, **every empty cell present and zero** |
| `human_evidence(record_rows)` | the three that read `document`, in Python, never a path expression |
| `duplicate_samples(dataset_rows)` | grouped by the same input, hashed in Python; the digest is the change to make when that stops being instant |
| `aggregated_statistics(record_rows, dataset_rows, axes)` | the above, composed into `CorpusStatistics` |

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

Two functions, and **neither may call the store**: `services/` is `logic`, `edge/store/` is
`adapter`, and `H-8` sends that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `sellable_projection(document)` | builds `ToolDecisionCorpus`, asks the door, answers a `ProjectedSample`. Pure |
| `described_corpus(record_rows, dataset_rows)` | `aggregated_statistics(...)` plus `tool_coverage(...)` plus `MATRIX_AXES`. Pure |

## `edge/store/session.py` — `adapter`

| Function | What it does |
|---|---|
| `database_url()` | `str \| None` — unset or empty is *no store*, never a default file |
| `database_engine()` | one engine for the process, **under a lock**; a changed DSN releases the old pool |
| `open_session()` | `Session \| None` — `None` is an answer every caller has to handle, not a failure |

## `edge/store/schema.py` — `shape`

| Name | What it is |
|---|---|
| `KEY_LENGTH = 64` | long enough for a digest-shaped id, short enough for a dialect with an index-length limit |
| `Utc` | `TypeDecorator` — SQLite hands back naive, Postgres hands back the connection's offset; both come out UTC |
| `Base`, `Record`, `Dataset` | the two tables, keyed `(task, id)`, with the `class` column name pinned and the attribute named `facets` |

## `edge/store/corpus_rows.py` — `adapter`

| Function | What it does |
|---|---|
| `stored_rows(session, task, document, projection)` | `merge` into `record`, `merge`-or-`delete` on `dataset`, one `session.begin()`. It takes the door's answer rather than calling the door (`C-6`) |
| `carried_created_time(session, task, id)` | read before merging — `merge` replaces the whole row, so the column that never changes has to be carried forward |
| `record_documents(session, task)` | the rows the three evidence statistics read |
| `dataset_rows(session, task)` | the rows the counts read |
| `rebuilt_dataset(session, task, project)` | delete every row and recompute from `record`; takes the projection as an argument |

## `edge/routers/text2text/tool_decision.py` — `adapter` (changed)

| Added | What it does |
|---|---|
| `class ReviewedSample(Sample)` | the thirteen-key envelope, `extra="allow"`. Not `Record`: `R-2` refuses a name that already names a table |
| `class StoredWhere` | which table took the row, and why the other did not |
| `POST /records` → `stored_record(request)` | body → `sellable_projection` → `stored_rows`. 503 naming the variable where no database is attached |
| `GET /records/stats` → `corpus_stats()` | `dataset_rows` and `record_documents` → `described_corpus` |
| `GET /records/declared-facets` → `declared_facets()` | the page asks the profile which ticks to draw instead of holding a second copy of the list |

---

## Three things to read closely

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
