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

**`profile/tool_decision/`** — this task's answers to whatever the modality declares, this task's
label measurements, and this task's own two tables with the SQL over them. One file per thing it
answers, next to `ai_review.py` and `data_quality.py`: a package here would nest two files that
nothing imports together, and the door already resolves to everything under it, so nesting hides no
tag.

**`edge/database.py`** — the DSN, the engine, the session, and the one declarative base every
task's tables hang off.

`dataset_management` names two things and only two: the modality's package, and the service module
answering its endpoints. The profile does not repeat it — there the files are named for what each
one holds, because the task's half is not a stage of anything.

---

## The tree

```
src/dataforce/
├── modalities/text2text/
│   └── dataset_management/        NEW — the modality's fourth package
│       ├── __init__.py            facade
│       ├── schema.py              shape · DatasetSample, DatasetDuplicateGroups
│       ├── sample_building.py     logic · the precondition, and the socket a task answers
│       └── duplicate_data_checking.py  logic · the same input twice, over the whole corpus
├── profile/tool_decision/        (ai_review.py, data_quality.py, utils.py already here)
│   ├── schema.py                  NEW    shape   · this task's two tables. Columns, nothing else
│   ├── sample_building.py         NEW    logic   · answers whatever the modality declares
│   └── label_statistics.py        NEW    logic   · what THIS task's label can be measured by
├── services/tool_decision/
│   └── dataset_management.py      NEW    logic · one function per endpoint
├── tables.py                      NEW    shape   · the one Base every task's tables hang off
├── edge/database.py               NEW    adapter · the DSN, the engine, the session
├── edge/routers/text2text/tool_decision.py   CHANGED — the response shapes live here
└── ui/{index.html,app.js,style.css}          CHANGED

tests/
├── modalities/test_schema.py                 NEW
├── modalities/test_duplicate_data_checking.py  NEW
├── modalities/test_sample_building.py        NEW
├── profile/test_sample_building.py           NEW
├── profile/test_label_statistics.py          NEW
├── services/test_dataset_management.py       NEW
├── store/                                    NEW
│   ├── __init__.py, conftest.py
│   └── test_schema.py, test_database.py, test_write.py
└── edge/test_endpoints.py                    CHANGED
```

---

## `modalities/text2text/dataset_management/schema.py` — `shape`

| Name | What it is |
|---|---|
| `StepNotRun` | the refusal, and the whole of it is the name — which step and what about it are the message the raise writes, so nothing here splits one into arguments. The **second** exception in this codebase, and the one case `errors.py`'s rule does not cover: not something that went wrong about a record — which is a value on that record — but a record that may not become one. Raising is what makes it unbypassable, because no `DatasetSample` exists for a document that failed |
| `ScannedPersonalData` | what the record's `personal_data` key holds: the detect answer and the replace answer as one object, declared by **inheriting both** rather than restating their fields, so a span here and a span a reviewer edited cannot come to mean different things |
| `ShippedDatasetSample` | `messages`, `tools`, `label` as they ship — the `new_` copy, or what arrived where no new version was made. Never what arrived: that lives on in `record.document`, which is what makes a corpus built out of these exportable |
| `DatasetSample` | `input`, `label`, `facets` — the row that is kept. The profile's tables turn it into columns |
| `DatasetDuplicateGroups` | `duplicate_content_same_label`, `duplicate_content_diff_label`. Each entry is one group's **row keys**: dropping all but one of a group and opening a group to inspect both need to know which rows are one another's duplicate |
| `DatasetLabelSummary` | `total`, `number_not_null_label`, `number_diff_label` — what a corpus's labels come to, every figure beside the total it came out of. Counts and never a share, which is also what makes a corpus of no rows an answer rather than a division. **The shape is the modality's and the filling is the profile's**, **a label here is a sequence that may be absent and nothing more** — what its entries *are* is the task's, so the tool figures live a layer down rather than being two fields a summarisation task would inherit with nothing to put in |

## `modalities/text2text/dataset_management/sample_building.py` — `logic`

**The refusal is why this file is the modality's.** What it reads is a text2text shape and the
obligation behind it is the law's rather than one task's, so a second text2text task inherits it
and a per-task copy must not exist: a copy that drifts is a corpus sold in breach.

| Name | What it does |
|---|---|
| `read_shipped_part(document, part)` | the `new_` copy, or what arrived where there is none. `null` under a `new_` key is *no new version was made*, never *it ships as nothing* — the page writes it for every clean catalog |
| `read_shipped_sample(document)` | the three as they ship, as a `ShippedDatasetSample` |
| `read_scanned_personal_data(document)` | the `personal_data` key, or `StepNotRun`. **Two arrivals, one refusal**: `null`, which is nobody having run step 2, and something that will not read as a scan, which is evidence nothing can check |
| `list_text(node)` | every string under a node, values only — the same reach the replacement has, walked the same way |
| `find_surviving_spans(scanned, shipped)` | every confirmed span whose value is still readable in what **ships**, string by string and never over the sample serialised: JSON escapes a quote, a backslash and a newline, so a serialised search would clear a record still holding one. **The spans and never the values**, because a refusal naming the value puts personal data in an HTTP body |
| `read_redacted_classes(scanned)` | the classes a confirmed span stood over, sorted and each named once. The one modality-derived facet |
| `DatasetSampleBuilding.build_sample(document)` | both refusals, then the row. **Raising rather than answering** is the point: a precondition returned as a value is one a caller can forget to read, and the one that gets forgotten is the one whose cost is a fine |
| — `build_input(shipped)` | abstract. What one sample of this task ships as |
| — `compute_facets(shipped)` | abstract. The facets reading this task's own sample answers |

Both abstract methods are handed what **ships** and never the document, so a task cannot reach past
the redaction to read what arrived: a facet computed off the raw transcript would describe a sample
the corpus does not hold.

## `modalities/text2text/dataset_management/duplicate_data_checking.py` — `logic`

A duplicate is a fact about a *dataset*, so it is counted here and not against one posted batch.
There was a second module of this name under `data_quality/`: an abstract class over an embedding
call, whose `duplicate_groups` returned `None`, whose only subclass implemented no socket and so
could not be constructed, behind a route that answers `null` without reaching it. It is deleted,
and this file carries its name and its `DatasetDuplicateGroups`. One duplicate check in the modality,
not two.

| Function | What it does |
|---|---|
| `calculate_duplicates(keys, inputs, labels)` | the two groups, each as the **row keys** that share an input — a digest opens nothing, and `duplicate_content_diff_label` is a queue somebody opens. Hashed in Python to group; the digest column is the change to make when that stops being instant |

## `modalities/text2text/dataset_management/label_statistics.py` — does not exist

**One measurement, and it moved down.** The only thing every text2text label has in common is that
it may be absent, and anything past that says `tool` — which is the profile's to measure.
That one measurement is a single expression with a single caller, so `C-4`, `C-5` and `T-5` all say
the same thing: it belongs at the call site — `summarise_labels` below — and not in a module of its
own. Every label *measurement* is the profile's; the shape they come back in is `DatasetLabelSummary`
above, on the same terms as every other shape here.

## `profile/tool_decision/schema.py` — `shape`

The same thing `schema.py` means everywhere else in this repo — what the stored data looks like —
and the same tag, because a table class is a noun: it names columns and their types and answers no
question. It imports `Base` from `dataforce/tables.py`, also a `shape`, so one `MetaData` holds
every task's tables and this file imports nothing that opens anything. There is no `task` column:
the table name is the task.

**Everything handed a `Session` is somewhere else** — `label_statistics.py` reads, and
`sample_building.py` writes — because a session is not a noun. Both are `adapter`, which is also
what keeps `services/` out of them.

| Name | What it is |
|---|---|
| `ToolDecisionRecord(Base)` | `id` as `Uuid` — native on Postgres, 32 characters on SQLite, and nothing to pick a length for — the thirteen keys of the review, the two times. The raw side: may hold personal data, never exported |
| `ToolDecisionSample(Base)` | `id`, `input`, `label`, the two times, **the columns below**, and `notes` |
| `ToolDecisionDataStamp` | the three columns both tables carry in common: which sample, and its two times. **Not a row and not a state** — a row is sixteen columns wide, and this is decided before either merge, so it is handed to `build_tool_decision_sample` before anything is stored |
| `ToolDecisionSampleContent` | one sample's key, input and label — the two columns a buyer is sold, without the facets that describe them. Declared rather than answered as a bare triple, because `services/` reads it two layers from the query and would otherwise take it apart **by position**, four times, with a `SELECT`'s column order as the only thing holding it together |
| `ToolDecisionDatasetStatistics` | the body `GET .../records/stats` answers with. Here with the other nouns of this task, because it says this task's words out loud — `domain`, `call_trigger`, tools. What fills it in is `services/`, which is `logic` and holds decisions rather than nouns, so it reads the shape from here the way the router does. **No percentage in it**: every figure travels with the total it came out of |
| — its `FACETS` | the nine facet column names, as a `ClassVar` on the class whose facets they are, so a table cannot drift from a list hanging off it. **What a person may *tick* is not here and nowhere below the edge**: a tickable list belongs with the page that draws the tick boxes |
| — its columns | `language`, `personal_data`, `ambiguous`, `domain`, `call_trigger`, `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid` — each one true of every sample in the table, and expected to stay true |
| — its `notes` | JSON. `have_conversation_flow` and `direction` start here, because each is true of a *group* of label sets rather than of the table. **A facet added later starts here too**, always, and becomes a column only when someone is grouping by it often enough for the scan to hurt |
| `create_tables(engine)` | `Base.metadata.create_all`. With no migration folder, this is the only thing that makes a table |
| `TOOL_DECISION_KEY_NAMESPACE` | the namespace the row key is derived in. A corpus names its samples `s4471` and the column is a `Uuid`, so `merge_tool_decision_db` hashes the name into this: **derived and never minted**, because *a second post replaces the row* is only true while one name keeps one key. The cost: a sold row joins back to its corpus through `record.document`, not through its own key |
| `RowStamp` | what one write came to — the key both tables took and the two times standing on it |
| `build_sample(key, sample, times)` | a column per facet the table has one for, the rest into `notes`. `FACETS` is the whole of what splits them |
| `merge_tool_decision_db(session, document, sample)` | the key, the first `created_time` read **before** either merge — `merge` replaces the whole row — then a `merge` into each table and one commit. **Both always**: the tables differ by what they hold, not by which rows reach them. The transaction is the session's own — hand it a session of its own, which is the trade for a function `rebuild_tool_decision_dataset` can reach with one it has already read on |
| `count_total_samples(session)` | how many rows each table holds. They agree, and a run where they do not is a bug rather than a figure |
| `count_by_facet(session)` | one `GROUP BY` per facet column. The column names are this task's, and this is the layer allowed to say them. Keyed by the **column's** way of writing a value, not the value's Python type, and **added** rather than assigned: SQLite groups a JSON column by text while Postgres groups `jsonb` by value, so two groups can be one key. Ordered by `ORDER BY`, because a JSON column can hold two values Python cannot compare |
| `count_by_pair(session, row_facet, column_facet)` | `GROUP BY` two columns — only the pairs that exist. A list-valued facet comes back as a **tuple**, not as text: the caller reaches the values inside it, and splitting a set in SQL would be `json_each` and `jsonb_array_elements`, which is two statements for one question |
| `select_sample_contents(session)` | every row of `dataset` as the statistics read it: the `id`, the `input` and the `label`. **One read, three questions**: the duplicate grouping is given all three and the label measurements read two, so a second query would fetch the same rows again. That is why there is no `stored_labels` |
| `rebuild_tool_decision_dataset(session, building)` | delete every row and recompute from the record table, in one transaction, and answer how many it wrote. Handed the builder rather than importing one, so the module holding the SQL does not also decide whose samples it holds. A record that no longer passes the precondition stops the rebuild: finishing around it would leave a table nothing can call a function of the other |

## `profile/tool_decision/sample_building.py` — `logic`

`ToolDecisionSampleBuilding`, which answers the two abstract methods above and nothing else.

| | |
|---|---|
| `build_input(shipped)` | `{messages, tools}` — the turns and the catalog together, because a tool call is a call *against a catalog* and a label stored apart from one is a label nothing can check |
| `compute_facets(shipped)` | `number_turns`, `number_label_tools`, `number_provided_tools`, `schema_valid`, each counted off what **ships**. `number_provided_tools` counts what the catalog *shows* — an entry nothing can read is not a tool the model was offered, and counting it would put a figure in the column that no other reading of the same row agrees with |
| nothing declared | `domain`, `call_trigger`, `direction` and `have_conversation_flow` arrive under the record's `class` key and the modality carries them through without naming one. A second list of those names here is a list to keep in step with the page's for nothing |

## `profile/tool_decision/label_statistics.py` — `logic`

Where the real label measurements are, because every one of them says `tool` and only this layer
may.

**Counting the calls is not here.** How many rows make 0, 1 or more calls is one expression over
the labels with one caller, so it lives in `summarise_labels` below — and it counts **entries**,
not tools it could read: an entry naming no tool is still an attempt at a call, and letting it fall
to `0` would pad the no-call share, which is the statistic irrelevance detection is measured from.
`schema_valid` is what marks that row broken.

| Function | What it does |
|---|---|
| `list_called_tools(label)` | the tool names the label calls |
| `validate_label_calls(label, catalog)` | BFCL's AST check: every call names a tool in the catalog and supplies its required parameters |
| `list_offered_tools(catalogs)` | every distinct tool the catalogs put in front of the model, sorted. Counted apart from `count_tool_calls`' keys, because those also hold a tool a broken row invented and an invention is not an offer |
| `count_tool_calls(labels, catalogs)` | a count per tool the corpus offers, a tool never called included as `0` — **the zeros are the finding**, as in the joint distribution matrix. One mapping rather than a shape: offered is the keys, ever called is the non-zero keys, and the tail is the values |

**`list_required_parameters` is not here.** It reads `parameters.required` less any param declaring a
`default`, and `utils.py` already wrote that rule twice — for the `require:` line of the rendered
catalog and for a nested object's subfields. A third copy is two definitions of what a call must
supply, so the check and the catalog a model was shown could disagree with nothing to say so. It
lives in `profile/tool_decision/utils.py` beside them, and takes the `parameters` object rather
than the tool. `read_named_function`, the read of an entry that may be wrapped or bare, moved there on
the same terms.

## `services/tool_decision/dataset_management.py` — `logic`

**It may not call the store**: `services/` is `logic`, the profile's `schema.py` is `adapter`, and
`H-8` sends that import the other way. The router is where the two meet.

| Function | What it does |
|---|---|
| `list_categories(stored)` | which categories of one variable a stored value is counted under: a set counts under each of its values, distinct, and an empty set counts under none |
| `create_joint_distribution_matrix(pair_counts)` | the **rectangle** those pairs make: every value either variable carries crossed with every value the other does, so a pair no sample makes reads `0` and **the zeros are the finding**. Two variables, whichever two the caller crossed — a second cross is another call, not another function. The axes are what the corpus *carries*: a value nobody has ticked yet has no cell, because crossing this against the tickable list is the page's. A set-valued facet counts in every cell its values cover, so a sample triggered two ways is in two cells. Pure |
| `build_dataset_statistics(sample_totals, counted_by_facet, counted_by_domain_and_call_trigger, sample_contents)` | § *The statistics* in full, out of what one read of the store came back with. Handed the reads rather than taking them, because `logic` may not open a database. **The pair is named by the caller and the field is named for the pair**, so the parameter carries the pair in its own name: cross a different two and the keyword stops matching the field. A catalog is read out of `input` here and not at the edge, because what a stored `input` holds is the profile's declaration |
| `summarise_labels(labels)` | a `DatasetLabelSummary`: how many rows answered at all out of how many — `()` and `None` are both *no answer was needed* — and how many **distinct** answers they hold between them, counted over `canonical_json`, the same text the duplicate grouping compares by, so nothing can disagree about which labels are one label. No catalog reaches it: what a tool is belongs a layer down. Pure |

**No function here turns a posted document into a `DatasetSample`.** It was scheduled here and
turned out to be a constructor call: once `sample_building.py` declared its socket, composing it is
`ToolDecisionSampleBuilding().build_sample(document)` and nothing more, and a service function whose
whole body is that `return` is the one-line wrapper `C-5` refuses. The router names the profile
directly, the way it already names `count_by_facet` and `list_offered_tools`.

## `edge/database.py` — `adapter`

| Name | What it is |
|---|---|
| `Base` | the one declarative base every task's tables hang off |
| `Database` | the DSN, the lock and the engine cache are one object's state, not three module globals |
| `Database.open_engine()` | `Engine \| None` — one engine for the process, **under a lock**; unset, empty or whitespace is *no store* and never a default file; a changed DSN releases the old pool |
| `Database.open_session()` | `Session \| None` — `None` is an answer every caller has to handle, not a failure |
| `store` | the one instance, built from `DSN_VARIABLE`. Callers write `store.open_session()` |

**No `TypeDecorator`, and no UTC.** A time is written and read exactly as it was given, so both
dialects hand back the same value and nothing converts. The cost, stated: a row's instant is only
placeable by someone who knows where the deployment runs. UTC is the change to make the day a
second region reads the same corpus, and not before.

## `edge/routers/text2text/tool_decision.py` — `adapter` (changed)

**A handler here reads what only it can read, and hands it to one function.** Only the router
holds a session, so the four reads are its; every figure taken over them is
`services/tool_decision/dataset_management.py`'s, and `ToolDecisionDatasetStatistics` is declared there with
them. `ReviewedSample` goes the other way — an envelope is declared where it arrives.

| Added | What it does |
|---|---|
| `class ReviewedSample(Sample)` | the thirteen-key envelope, `extra="allow"` — a key the page adds is news about the page, not a reason to refuse a review. `label` and `new_label` are **narrowed to a list**, which is where the page's `{unparsed: …}` carrier stops: a column the corpus is counted by does not take one. `class` arrives under an alias, because Python cannot spell it |
| `class RecordStored` | the key both tables took and the two times on it. Equal times are a first post and apart ones a replacement, which is the one thing a reviewer wants to know |
| `class ToolDecisionDatasetStatistics` — in the profile's `schema.py` | the response body: `sample_totals`, `counted_distribution_by_facet`, `counted_distribution_by_domain_and_call_trigger` (the field name is what says which two variables the grid is over, so nothing else in the answer has to), `label_summary`, `number_tools_offered`, `tool_call_counts`, `duplicate_groups` — each name saying what the figure *is*. No percentage in it: the denominators travel, so the no-call share reads off `label_summary` and the schema-validity share off `counted_distribution_by_facet`. **How many matrix cells are still empty is not in it**: that needs the tickable lists, which the page holds |
| `POST /records` → `post_record(review)` | envelope → `build_sample` → `merge_tool_decision_db`. **Three refusals, in the order their costs are**: `503` naming the variable where no database is attached, `422` where `StepNotRun` names a step and nothing is written, `422` naming a declared facet the review left unanswered — by name, so a reviewer reads a facet to go and tick rather than a column that refused a value |
| `GET /records/stats` → `get_dataset_statistics()` | four reads the session makes, handed to `build_dataset_statistics` → `ToolDecisionDatasetStatistics`. **503 naming the variable** where nothing is attached: zeros would read as *a corpus with nothing in it*, which is a different claim from *nothing was asked* |
| — no `declared-facets` route | the page holds the tickable values itself. A list of what a person may choose is not a fact about the store, and the store has no use for a value until a sample carries it |

---

## Adding a facet later

The question a column has to survive is *what happens to the rows that are already there*, and the
answer splits on who fills the facet — which is why the derived/declared line outlives the two
types that held it.

| | A **derived** facet — `number_turns`, `schema_valid`, `personal_data` | A **declared** facet — `domain`, `ambiguous`, `have_conversation_flow` |
|---|---|---|
| Where it comes from | computed from `record`, which keeps the whole review | a person ticked it, once, on a page that has since moved on |
| Old rows after it is added | `rebuild_tool_decision_dataset` recomputes every one of them. Nothing is lost | **nothing can fill them.** They are unknown, and stay unknown unless somebody re-reviews every old sample by hand |
| So it may be | a column, added when wanted — the cost is one rebuild | `notes`, until you are sure. A declared column added late is a column that is `NULL` for the whole corpus that existed before it |

That is why `have_conversation_flow` belongs in `notes`: it is declared, so the day it becomes a
column every sample already in the table is permanently blank on it, and a statistic over it would
measure when the facet was introduced rather than what the corpus holds.

With no migrations, a column is also an `ALTER TABLE` somebody writes by hand against a live
database. A key in `notes` is nothing at all — old rows simply do not have it, which is the same
*unknown* as a `NULL` without a schema change to perform.

---

## One thing to read closely

**A computed facet and a ticked one are kept apart by one line, and it is worth knowing which.**
The rule is real — a derived facet is never typed, a declared one is never computed — and the two
sets of names now live a long way apart: the derived ones are `compute_facets` in
`profile/tool_decision/sample_building.py`, the declared ones are `DECLARED_FACETS` in `ui/app.js`.
Nothing holds them apart by name. What holds the rule is the **merge order** in `build_sample`: the
ticks go in first and the computed facets are written over them, so a page that grew the wrong tick
loses rather than quietly describing a corpus that is not there. A test states that. A column still
does not say who filled it, so the table cannot tell the difference and nothing reads for it either.

**A facet the profile declares and `ui/` never draws is a column that is always `null`.** The two
lists are held apart on purpose — a tickable value is a thing a person chooses, and the store has no
use for one until a sample carries it — so adding a facet is a change in both places, and review is
what catches a change made in only one.
