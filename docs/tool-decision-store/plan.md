# Build plan

Tasks for building what `spec.md` specifies. Read that first; this document schedules it and does
not restate it. Where the two disagree, the spec wins and this file is wrong.

**Source:** [`spec.md`](spec.md), and [`layout.md`](layout.md) for which module each task's change
lands in. `AGENTS.md` for `H-4`, `H-8`, `R-6`, `R-8`, `E-1`, `T-1` and `T-5`.
`docs/tool-decision-pipeline/spec.md` for the flow this sits under.

**State at the time of writing.** Nothing of the store exists, and two things already point at it:

- `pyproject.toml` declares `sqlalchemy>=2.0.52,<2.1`, unimported, with a comment saying the store
  is deferred. It also declares `alembic>=1.19.1`, and `alembic.ini` names a `migrations/` that
  does not exist. There are no migrations in this design, so both go.
- `.github/workflows/ci.yml` has an `integration` job, passes `DATAFORCE_TEST_DATABASE_URL`, and
  says in a comment that the slow half is "the store against a real Postgres". The job runs a suite
  that does not exist, and the workflow declares no Postgres service for it to reach.

`modalities/text2text/` holds three packages — `data_quality`, `ai_review`, `human_review` — and
this plan adds the fourth. `profile/tool_decision/` holds one module per part and gains a package.
`make check` is green: ruff, `mypy --strict`, one suite with no network in it.

The flow above the store was finished and ended nowhere: `ui/` walked a sample through eight steps,
assembled a record, and **approve** posted it nowhere. Phase 3 is where that ends.

**Scope.** The database plumbing, this task's two tables, the pure pieces every text2text task
shares, the statistics over the corpus, the route that takes a record, and the page reshaped into a
deck with a guide on its first card.

**Assumption.** No corpus is loaded and none is imported. Every fixture is hand-written, and the
first rows in either table are the ones a labeller approves.

---

## What was not schedulable, and what unblocked it

`modalities/text2text/dataset_management/sample_building.py` declared nothing, and everything that
turns a **posted document** into a row waited on it — Phase 3 in full. Everything that reads **rows
already in the table** did not, because a test inserts those directly, which is why the order here
is unusual: the counting was built before the writing, because the counting was the half that could
proceed.

**T12 has since been taken** and the block is gone. What the decision came to is written in T12
itself; what matters here is what it did *not* decide, because that is what § *Design*'s warning
was about. It declares the refusal and two abstract methods, and nothing else: how a task shapes
its `input` and which facets it reads are the task's, and neither of them is a step in a sequence
this file names. A shape invented too early is expensive because every task afterwards has to
implement it — so what was invented is as small as the obligation allows, and the obligation is
the law's rather than a flow's.

---

## How to read this

**One task is one commit.** Each is sized for one session with no prior context: read the task,
read what its *Source* points at, do it, run its *Verify*, commit.

**Every task has the same parts.**

| Part | Answers |
|---|---|
| **Goal** | What is true once this is done |
| **Context** | Why it is not true today, and what will bite |
| **Approach** | The shape of the change — present only where the task needs one of its own |
| **Acceptance criteria** | The outcome to check. Never the steps |
| **Source** | Where in `spec.md` the requirement it serves lives |
| **Verify** | A command that runs as written |
| **Out of scope** | What belongs to a different task |
| **Blocked by** | What must land first, when that is more than the task before it |

**Every short reference resolves somewhere.**

| Written | Lives in |
|---|---|
| § *The precondition* | a named section or a bold requirement heading in `spec.md`, always. Cited by its words, because a number is a second thing to keep in sync |
| `H-8`, `E-1`, `R-6` | a rule in `AGENTS.md`. The ID is stable and citable |
| `T7` | a task in this file. The number is its name, not its place in the order |
| step 5 | one of the flow's eight steps, numbered by the labelling page and only there |
| the record | the thirteen-key document § *`record`* names, which `ui/app.js` assembles. `record` in code font is the table |

---

## Decisions this plan takes once

Six shapes span several tasks. They are settled here so no task settles them differently.

**No default database.** A fallback to `sqlite+pysqlite:///dataforce.sqlite3` makes the state
§ *The page* requires — no database attached, the strip says so, all eight steps still work —
unreachable, and the first time anyone notices is when a corpus is in a file nobody meant to
create. Unset or empty means no store, and `store.open_session()` answers `None`.

**Logic is never handed a session.** What a facet holds and what a statistic is are pure functions
of a document or of a list of rows. The reading and the writing are the profile's `schema.py`,
which is an `adapter`; the router — also an `adapter`, which `H-8` permits to import logic — is
where the two meet. `services/` is `logic` and cannot import either.

**One suite, two databases.** `make check` runs the store's tests against a temporary SQLite file:
no server, no network, and the commit gate covers the adapter. `make integration` runs the same
tests against `DATAFORCE_TEST_DATABASE_URL`. *One code path, two DSNs* is a claim in the spec, and a
suite that only ever runs on one of them is not evidence for it. The two halves run across the two
targets, not twice inside one: `-m integration` deselects the file.

**A facet added later starts in `notes`.** No task adds a column for a facet. Any facet not in the
column list § *`dataset`* names is a key in `notes`, and promoting one to a column is its own
decision with its own task, taken when something is measurably slow.

**There are no migrations.** `Base.metadata.create_all` is the only thing that makes a table. It
creates and never alters, which is a property the tests state rather than a limitation they work
around.

**A function is named by `R-6`, and the check is reading it aloud.** A verb phrase, verb first —
`open_engine`, not `engine`; `count_total_samples`, not `row_counts`. One stem per step, inflected, so the
grammatical form says which side of the call the name sits on: the verb phrase is the act, the noun
is what came back and belongs to the variable. And `C-6`: the function that decides and the function
that writes are two functions.

---

## Phases

| # | Phase | Goal — the outcome that ends it |
|---|---|---|
| 0 | A database can be reached, and this task's tables exist | `create_tables` makes both tables on an empty SQLite file and on Postgres, and `make check` exercises the adapter with no server running |
| 1 | What every text2text sample has in common | The shapes, the duplicate check and this task's label measurements, all pure, with no word of `tool_decision` anywhere in `modalities/` |
| 2 | The corpus can be counted | `GET .../records/stats` answers every statistic in § *The statistics* over rows a test put there, each with its denominator, none of them stored |
| 3 | A reviewed sample lands | **approve** posts the record, both tables take it in one transaction, and a sample whose steps did not run is a `422` |
| 4 | The page is a deck | `ui/` shows one card at a time, the first card is the labelling guide, and the statistics are under it |

Phase 0 is groundwork and is not a vertical slice: nothing above it can be tested without a database
to open. Phase 1 needs no database at all. Phase 2 ends in something a person can see — a stats
endpoint answering over hand-inserted rows. Phase 3 was blocked until `sample_building.py` declared
an interface, and everything else was finished around it first. Phase 4 needs Phase 2, because a
deck whose first card holds statistics needs statistics.

---

## The tasks

**Needs** is what must land before this task can start; blank means *as soon as the phase opens*.
**Size** is a shape, not an estimate — **S** one module or one file · **M** several modules, or one
algorithm to get right · **L** more than one sitting, so split it if it grows while you work.

| # | Task | Phase | Needs | Size |
|---|---|---|---|---|
| T1 | The DSN is read once, and *no database* is a state | 0 | | S |
| T2 | This task's two tables, and what makes them | 0 | T1 | M |
| T3 | The store's suite runs on a file and on a server | 0 | T2 | M |
| T4 | Alembic is removed from a repository that has no migrations | 0 | T2 | S |
| T5 | What a stored text2text sample is | 1 | | S |
| T6 | The same input twice, over a whole corpus | 1 | T5 | M |
| T7 | What any text2text label can be measured by | 1 | T5 | — not built |
| T8 | What this task's label can be measured by | 1 | T5 | M |
| T9 | Counts per facet, and per pair of facets | 2 | T2, T8 | M |
| T10 | The empty cells, put back | 2 | T9 | M |
| T11 | The statistics route, and what it says with no database | 2 | T6, T10 | M |
| T12 | `sample_building.py` declares what a task must answer | 3 | | M |
| T13 | The profile answers it | 3 | T12 | M |
| T14 | The record's envelope, declared at the boundary | 3 | T12 | S |
| T15 | Two writes, one transaction | 3 | T13, T14 | M |
| T16 | The route that takes a record, and the step that did not run | 3 | T15 | M |
| T17 | **approve** posts the record | 3 | T16 | M |
| T18 | Step 7 draws a tick for every declared facet | 3 | T17 | M |
| T19 | `dataset` can be dropped and rebuilt | 3 | T15 | S |
| T20 | One card at a time, and a bar that moves between them | 4 | | L |
| T21 | The first card is the guide, and the header is a title | 4 | T20 | M |
| T22 | The strip, and the statistics under the guide | 4 | T11, T21 | M |

---

## Phase 0 · A database can be reached, and this task's tables exist

**Phase goal.** `create_tables` makes both tables on an empty SQLite file and on Postgres, and
`make check` exercises the adapter with no server running.

### T1 · The DSN is read once, and *no database* is a state

**Goal.** `edge/database.py` answers a session or `None`, from `DATAFORCE_DATABASE_URL` alone.

**Context.** Nothing in the repository opens a database. `sqlalchemy` is declared and unimported.
The state that matters most is the one where the variable is unset: § *The page* requires the whole
flow to work with no store attached, so `None` is an answer and not a failure.

**Approach.** `edge/database.py`, tagged `adapter`: one `Database` class holding the variable
name, the lock and the engine cache, with `open_engine()` and `open_session()` on it, plus `Base`
beside it and one instance named `store`. The DSN read, the lock and the cache are one object's
state; as three module globals and three functions they were three things a reader has to hold at
once, and the read of the variable was a function whose whole body was a `return`.

The engine cache is shared: FastAPI runs a sync handler in the anyio worker threadpool, so two
requests can enter a cold cache at once. A lock around the build, or two engines exist and one leaks
its pool.

**No `TypeDecorator`, and no UTC.** A time goes to the column as it was given and comes back the
same, on either dialect. The cost is stated rather than designed around: a row's instant is only
placeable by someone who knows where the deployment runs, and UTC is the change to make the day a
second region reads the same corpus. Not before — this is a corpus with one writer in one place.

**Acceptance criteria.**
- With the variable unset, empty, or whitespace, `store.open_session()` is `None` and nothing raises.
- With it set to a temporary SQLite file, a session opens and a round-tripped datetime comes back
  equal to what went in, on either dialect.
- Eight threads entering a cold cache get one engine.
- `Base` is declarative and importable by a profile.

**Source.** § *Context* — the DSN is read once and there is no default. § *The page* — no database
attached is a supported state.

**Verify.** `uv run pytest tests/store/test_database.py -q` and `make check`.

**Out of scope.** Any table (T2). Any route (T16).

### T2 · This task's two tables, and what makes them

**Goal.** `profile/tool_decision/schema.py` declares `ToolDecisionRecord` and
`ToolDecisionSample`, and `create_tables(engine)` makes both.

**Context.** § *`record`* and § *`dataset`* fix the columns. The key is `id` alone, as a `Uuid`:
the table name carries the task, so nothing needs qualifying, and a UUID column needs no length
chosen for it.

**Approach.** `Uuid` for the key. `JSON` for `document`, `input`, `label` and `notes`. The nine
facet columns § *`dataset`* names, each typed for what it holds — a string for `language` and
`domain`, a boolean for `ambiguous` and `schema_valid`, an integer for the three counts, `JSON` for
`personal_data` and `call_trigger`, which are both sets. Plain `DateTime` for the two times.

The tag is `shape`, the same as every other `schema.py` in the repository: a table class names
columns and their types and answers no question. It imports `Base` from `dataforce/tables.py`,
which is a `shape` too, so one `MetaData` holds every task's tables and this file imports nothing
that opens anything.

**Decided since.** The tag was `adapter` while this file also held the SQL over the tables, and a
lone `schema.py` that meant something different from the other four was a trap for a reader. The
functions moved instead: reads to `label_statistics.py`, writes to `sample_building.py`, both
`adapter` because both are handed a `Session`. `Base` moved out of `edge/database.py` for the same
reason — a base is a noun, and a `shape` may not import an `adapter`.

**Acceptance criteria.**
- `create_tables` on an empty database makes exactly two tables with exactly the declared columns.
- Running it twice is a no-op and raises nothing.
- Running it against a database whose table is missing a column **does not add the column** — the
  test states this, because it is the property that makes a new facet a `notes` key.
- `notes` defaults to an empty object rather than to `NULL`, so a missing key and an absent row are
  different readings.
- The declared column list and § *`dataset`*'s list are asserted equal, so a column added in code
  and not in the spec fails here.

**Source.** § *`record`*; § *`dataset`*; § *Context* — there are no migrations.

**Verify.** `uv run pytest tests/store/test_schema.py -q`.

**Out of scope.** Writing a row (T15). Any query (T9).

### T3 · The store's suite runs on a file and on a server

**Goal.** One set of store tests runs against a temporary SQLite file under `make check` and
against `DATAFORCE_TEST_DATABASE_URL` under `make integration`.

**Context.** *One code path, two DSNs* is a claim in the spec and unevidenced until a test proves
it on both. `ci.yml` already passes the variable to a job whose suite does not exist, and declares
no Postgres service for it to reach.

**Approach.** A fixture parameterised over the two, the server half marked `integration`. The file
half makes a temporary path per test; the server half skips loudly where the variable is unset.
Both call `create_tables` and drop everything afterwards — which is why the variable names a
throwaway server and the docstring says so.

**Acceptance criteria.**
- `make check` runs the store tests with no server and no network.
- `make integration` runs the same tests against Postgres and reports them as run, not skipped.
- The suite leaves no table behind on either target.
- `tests/conftest.py`'s `no_endpoints` fixture clears `DATAFORCE_DATABASE_URL` too, so no test
  reaches a developer's own database by accident. `DATAFORCE_TEST_DATABASE_URL` is not cleared,
  because it is read on purpose.

**Source.** § *Context* — SQLite and Postgres are one code path with two DSNs.

**Verify.** `make check`, then `make integration` with a disposable Postgres.

**Out of scope.** CI gaining a Postgres service container — its own decision, and named in this
file's last table.

### T4 · Alembic is removed from a repository that has no migrations

**Goal.** No `alembic` dependency, no `alembic.ini`, and no comment claiming either.

**Context.** `alembic.ini` names a `migrations/` that does not exist, and `pyproject.toml` declares
alembic with a comment saying the store is deferred. Both describe a design this one is not.

**Acceptance criteria.**
- `alembic` appears nowhere in `pyproject.toml`, `uv.lock`, the Makefile or the workflow.
- `alembic.ini` is deleted.
- `tests/guards/` has no test asserting the ini names modules that exist, because there is no ini.
- `make check` is green.

**Source.** § *Context* — there are no migrations.

**Verify.** `grep -ri alembic . --exclude-dir=.git` returns nothing, then `make check`.

---

## Phase 1 · What every text2text sample has in common

**Phase goal.** The shapes, the duplicate check and this task's label measurements, all pure,
with no word of `tool_decision` anywhere in `modalities/`.

### T5 · What a stored text2text sample is

**Goal.** `modalities/text2text/dataset_management/schema.py` declares `DatasetSample` and
`DatasetDuplicateGroups`.

**Context.** Two names, and the package's whole `shape` file. `DatasetSample` is `input`, `label`
and the facets as a map — the row a profile's tables turn into columns. `DatasetDuplicateGroups` is the
two groups § *The statistics* names.

**Acceptance criteria.**
- Both are importable and neither imports anything from this package.
- No name in it carries `tool` or `decision`. **Review only**: the guard that checked this was
  `H-10`'s and was deleted with the rule, so this is a finding in a diff and not a failing test.
- The module docstring's first word is `shape`.

**Source.** § *`dataset`*; § *The statistics* — the same input twice.

**Verify.** `uv run pytest tests/guards -q` and `make check`.

### T6 · The same input twice, over a whole corpus

**Goal.** `duplicate_data_checking.py` answers `DatasetDuplicateGroups` -- the row keys of each group
-- over every stored input.

**Context.** § *Design* — *grouping by input* — takes the Python scan over a stored digest, and
names the digest as the change to make when the scan stops being instant. `data_quality/` held a
module of the same name: an abstract class over an embedding call whose `duplicate_groups` returned
`None`, with a subclass that implemented no socket and could not be constructed. It is deleted, and
this file takes its name and its `DatasetDuplicateGroups` — one duplicate check in the modality, not two.

**Approach.** Canonicalise each input under one key ordering, hash it, group by the hash, then split
each group by whether the labels agree. Two JSON columns are not comparable for equality across
dialects, which is why the grouping is in Python and not in SQL.

**Acceptance criteria.**
- Two rows with the same input and the same label land in `duplicate_content_same_label`, as
  their keys, so the caller can drop all but one of them.
- Two rows with the same input and different labels land in `duplicate_content_diff_label`, as
  their keys, so a person can open them.
- Two separate groups stay two entries rather than one flat list of keys.
- Key order inside a JSON input does not change the grouping.
- A corpus with no repeats answers two empty groups, not `None`.
- No name in the module carries `tool` or `decision`.

**Source.** § *The statistics* — the same input twice; § *Design* — grouping by input.

**Verify.** `uv run pytest tests/modalities/test_duplicate_data_checking.py -q`.

**Out of scope.** Reading the rows out of the table (T9).

### T7 · What any text2text label can be measured by — not built

**Decision.** There is no `modalities/text2text/dataset_management/label_statistics.py`. The share
of rows carrying a label at all is one expression over the rows and their count, and a module whose
whole content is a one-line function with no caller is what `C-4` — *"Otherwise a named variable is
enough to put the rule on screen"* — `C-5` and `T-5` each refuse. It is computed where its one
caller is: `summarise_labels` in `services/tool_decision/dataset_management.py`, T10.

**Cost, stated.** A second text2text task writes that line again rather
than inheriting it. One line written twice is cheaper than a file nothing imports, and `layout.md`
said as much before this was built: *"if this one moves down too, the file has no reason to exist
and label statistics are entirely the profile's."*

**`Share` went with it.** Every statistic is a count and the denominator it came out of
(§ *The statistics*), and the shape carrying that belongs with the rest of the response in the
router (T11), not in a modality with no user for it.

**What T10 still has to answer**, since nothing here answers it any more: an empty label counts as
*not labelled* and is a real answer rather than a gap — `[]` and `null` both — and the share over
zero rows divides nothing.

### T8 · What this task's label can be measured by

**Goal.** `profile/tool_decision/label_statistics.py` answers everything about a
label that says `tool`.

**Context.** `list_called_tools`, `list_required_parameters`, `validate_label_calls` and `count_tool_calls` all
read inside a label and a catalog. This is the layer allowed to name them.

**Approach.** `validate_label_calls` is BFCL's AST check against **this row's own catalog**: every
call names a tool the sample was offered and supplies that tool's required parameters. A label
calling a tool the sample never offered is a broken row, not a hard example.

**Acceptance criteria.**
- A call naming a tool absent from the catalog is invalid.
- A call missing a required parameter is invalid; a call missing an optional one is valid.
- An empty label is valid and counts as `0` calls.
- `count_tool_calls` answers a count per offered tool, a tool never called included as `0`, and a
  tool called without being offered counted rather than dropped.
- Counting calls per label is **not** here — see T10.

**Source.** § *The facets* — `schema_valid`; § *The statistics* — schema validity, tools offered
and tools called.

**Verify.** `uv run pytest tests/profile/test_label_statistics.py -q`.

---

## Phase 2 · The corpus can be counted

**Phase goal.** `GET .../records/stats` answers every statistic in § *The statistics* over rows a
test put there, each with its denominator, none of them stored.

### T9 · Counts per facet, and per pair of facets

**Goal.** The profile's `schema.py` answers a count per value of every facet column, and a count per
pair of two named ones.

**Context.** The facets are columns, so these are `GROUP BY`. This is the only layer allowed to say
`domain` out loud, which is why the grouping lives here and not in the modality.

**Decided here.** The nine facet names hang off `ToolDecisionSample` as a `ClassVar`, so the list
cannot drift from the table it describes. **The values a person may tick are not here and nowhere
below the edge**: a tickable list is a thing the page draws tick boxes from, and the store has no
use for a value until a sample carries it. Nothing refuses a value the store has not seen.

**Decided here.** A list-valued facet is grouped **as a set**. Splitting one in SQL is `json_each`
on SQLite and `jsonb_array_elements` on Postgres — two statements for one question, against a store
whose whole claim is *one code path, two DSNs*. So `count_by_pair` hands the set back as a tuple
and the service splits it, which is also where the empty cells are put back.

**Acceptance criteria.**
- `count_by_facet` returns a count per value for each of the nine facet columns, over rows a test
  inserted directly.
- `count_by_pair` groups by two named columns and returns only the pairs that exist.
- `count_total_samples` answers how many rows each table holds.
- Both dialects return the same answers for the same fixture.

**Source.** § *The statistics* — the joint distribution matrix.

**Verify.** `uv run pytest tests/store/test_schema.py -q`, then `make integration`.

**Out of scope.** Filling in the pairs that do not exist (T10).

### T10 · The empty cells, put back

**Goal.** `services/tool_decision/dataset_management.py` answers a matrix in which every pair of
declared values appears, the pairs with no rows included and zero.

**Context.** **The finding is the zeros.** A `GROUP BY` returns only what exists, so the empty cells
— the whole point of the matrix — are exactly what SQL cannot hand back. They are put back from the
product of `DOMAINS` and `CALL_TRIGGERS`.

**Acceptance criteria.**
- How many rows make each number of calls is **not** counted here. `number_label_tools` is a facet
  column, so the per-facet distribution already answers it at `0`, `1` and more — and a second
  count off the labels would be a second definition of what a call is, free to disagree with the
  column the corpus is sold by.
- How many rows carry a label at all, out of how many — `[]` and `null` both count as *not
  labelled*, and the share over zero rows divides nothing.
- Over a fixture whose rows make three pairs across three domains and three triggers, the answer
  has nine cells and six zeros.
- A value only one sample carries has an axis entry of its own the moment that sample lands.
- A sample that triggers nothing names a row and no column, rather than vanishing.
- The function is pure and takes no session.

**Decided here.** The matrix is the **rectangle the rows make**: every value either axis carries
crossed with every value the other does. A pair no sample makes still reads `0`, so the zeros are
there for everything the corpus has seen — what is *not* there is a cell for a value nobody has
ticked yet, because that list lives with the page. Crossing this grid against it, and counting what
is still empty, is the page's arithmetic.

**Decided here.** `empty_cells` is a field of the route's answer, counted off the matrix as it is
built. It is one expression with one caller, so `C-4` — *"a named variable is enough to put the rule
on screen"* — refuses a function for it, and the criterion *answered on its own* is met by its being
its own figure in the answer rather than something the strip recomputes.

**Source.** § *The statistics* — the joint distribution matrix, the finding is the zeros.

**Verify.** `uv run pytest tests/services/test_dataset_management.py -q`.

### T11 · The statistics route, and what it says with no database

**Goal.** `GET /text2text/tool-decision/records/stats` answers § *The statistics* in full, and says
so plainly where no database is attached.

**Context.** The router is where the profile's SQL and the service's arithmetic meet.

**Decided since.** `ToolDecisionDatasetStatistics` is declared in the profile's `schema.py`, with
this task's other nouns, and not in the router: a response shape is a noun, and `services/` is
`logic`. The handler now reads the four things only a session can read and hands them to
`build_dataset_statistics`. The handler named nine things outside the edge before
that and one of them reached inside a stored `input` to find `tools`, which is the profile's
declaration and not the edge's to know.

**Approach.** The handler opens a session, asks the profile's `schema.py` for the counts and the
rows the duplicate grouping needs, passes them to the service, and answers `CorpusStats`. Where
`store.open_session()` is `None` it answers `503` naming `DATAFORCE_DATABASE_URL` — the variable, so the
message says what to set.

**Decided here.** There is no `stored_labels`. `select_sample_contents` already answers the key, the
input and the label, which is every column the duplicate grouping and the label measurements read between
them, so a second query would be the same rows fetched twice — `T-5` refuses the module nothing
gets harder without.

**Acceptance criteria.**
- Over a fixture of known rows, every statistic § *The statistics* names is in the answer, each with
  its denominator.
- With no rows in either table, the route answers zeros and an empty matrix rather than failing.
- With no database attached, the route answers `503` naming the variable, and no other route is
  affected.
- Nothing is cached: two calls with a write between them differ.

**Source.** § *The statistics*; § *The page* — no database attached is a supported state.

**Verify.** `uv run pytest tests/edge/test_endpoints.py -q` and `make check`.

---

## Phase 3 · A reviewed sample lands

**Phase goal.** **approve** posts the record, both tables take it in one transaction, and a sample
whose steps did not run is a `422`.

### T12 · `sample_building.py` declares what a task must answer

**Goal.** `modalities/text2text/dataset_management/sample_building.py` declares an interface, and
the precondition § *The precondition* requires.

**Context.** The module was empty by decision, not by oversight: § *Design* says the steps had not
been watched happening to a real sample, and the shape invented first is the one every task
afterwards has to implement.

**Decision taken.** The interface is the refusal plus **two abstract methods**, and the whole of
what was invented is those two names.

- `DatasetSampleBuilding.build_sample(document)` is concrete and is the only way to a `DatasetSample`. It
  takes both refusals first, so a document that fails one produces no sample at all and there is
  nothing for a caller to write by mistake.
- `build_input(shipped)` and `compute_facets(shipped)` are what a task answers. Both are handed
  what **ships** and never the document, so a task cannot reach past the redaction to compute a
  facet off the raw transcript.
- The refusal **raises**. A precondition returned as a value is one a caller can forget to read,
  and the one that gets forgotten is the one whose cost is a fine. `StepNotRun` is the second
  exception in this codebase and the reason `errors.py`'s rule does not cover it: this is not
  something that went wrong *about* a record, it is a record that may not become one.
- Three module functions carry the reading — `read_shipped_sample`, `read_scanned_personal_data`,
  `find_surviving_values` — plus `read_redacted_classes`, the one facet the modality derives.
- No sequence of steps is named. § *Design*'s warning was about inventing the steps a review goes
  through; what is declared here is an obligation and a socket, and neither is a flowchart.

**Two readings this fixes, which the wording it was written against left open.** The survival check
reads **what ships** and not the three `new_` keys literally, because a `new_` key that is `null`
ships what arrived. And `personal_data` that will not *read* as a scan is the same refusal as
`personal_data: null` — evidence nothing can check proves nothing. Both are now in the spec.

**Acceptance criteria.**
- A document whose `personal_data` is `null`, or which will not read as a scan, raises `StepNotRun`
  naming the personal-data scan, and the message says which of the two it was.
- A confirmed span's value readable in what ships raises `StepNotRun` naming the redaction — in the
  turns, in the label, and in a field whose `new_` key is `null`. The refusal names the **span** and
  not the value, and the value carries a quote and a backslash in one of the cases, because a search
  over the sample serialised would escape both and let the record through.
- A finished review is refused by neither and answers a `DatasetSample`.
- A `new_` key that is `null` ships what arrived; `()` and `None` stay apart.
- The declared facets arrive from `class` without this layer naming any of them, and a tick under
  the name of a derived facet loses to the computed value.
- No name in it carries `tool` or `decision`. **Review only** — the guard that used to check this
  was `H-10`'s and went with the rule.

**Verify.** `uv run pytest tests/modalities/test_sample_building.py -q`.

**Source.** § *The precondition*; § *Where each piece is declared*; § *Design* — why
`sample_building` was left open.

### T13 · The profile answers it

**Goal.** `profile/tool_decision/sample_building.py` says what a `tool_decision`
sample ships as and which facets it computes and declares.

**Context.** `{messages, tools}` from the `new_` keys, or the originals where a `new_` key is
`null`. **`number_label_tools` is now load-bearing**: the no-call share and the calls-per-row
distribution are both read off that column, so a test here has to hold it to the label it was
computed from — nothing downstream recounts it. `number_turns`, `number_label_tools`, `number_provided_tools` and `schema_valid` computed.
`domain`, `call_trigger`, `direction` and `have_conversation_flow` declared — the last two into
`notes`.

**Acceptance criteria.**
- The shipped input holds the turns and the catalog together, and the counts are of what **ships**,
  not of what arrived.
- A document with every `new_` key `null` ships the originals.
- `schema_valid` is computed from this row's own catalog by T8's check.
- A facet the profile declares is a column, and the value a person ticked lands in it.
  **Which values may be ticked is not answered here**: that list lives with the page (T18).

**Decided since.** `ToolDecisionSampleBuilding` answers the two abstract methods and **declares
nothing**. `domain`, `call_trigger`, `direction` and `have_conversation_flow` arrive under the
record's `class` key and the modality carries them through without naming one, so the only list of
declared facet names below the edge is `FACETS` — the columns — and everything else lands in
`notes`. A second list here would be one to keep in step with the page's for nothing.

`number_provided_tools` counts what the catalog **shows**, through `list_offered_tools`: an entry
nothing can read is not a tool the model was offered, the rendered catalog leaves it out, and
`schema_valid` leaves it out, so counting raw entries would put a figure in the column that no
other reading of the same row agrees with.

**Verify.** `uv run pytest tests/profile/test_sample_building.py -q`.

**Source.** § *Where each piece is declared*; § *The facets*.

### T14 · The record's envelope, declared at the boundary

**Goal.** The router declares the thirteen keys it accepts, and nothing below it does.

**Context.** § *`record`* — `document` is one JSON column and no query reads inside it, so the
envelope stays declared where it is built. `extra="allow"`, because a key the page adds is not a
reason to reject a record.

**Acceptance criteria.**
- A document with all thirteen keys validates; one missing `id` does not.
- An unknown extra key is kept, not dropped and not rejected.
- The model is not named `Record`: `record` already names a table here, so a shape spelled that
  way reads as the row it is not.

**Decided since.** It is `ReviewedSample(Sample)`, so the four keys that are the sample are
inherited rather than restated. `class` arrives under an alias, because Python cannot spell it as a
field name.

**`label` and `new_label` are narrowed to a list here**, which is the one thing this envelope
refuses that § *The precondition* does not: the page carries a label that will not parse as
`{unparsed: …}` rather than guessing at it, and this is where that carrier stops — a column the
corpus is counted by does not take one. Step 7 says so in red before anyone gets this far. The
spec's *nothing else is refused* now says which two things are, and why neither is a claim about
whether the sample was worth keeping.

**Source.** § *`record`*.

### T15 · Two writes, one transaction

**Goal.** One posted document becomes one row in each table, or neither.

**Context.** `Session.merge` for both, inside one `session.begin()`. A second post under one `id`
replaces both rows. `created_time` never moves, which means it is read before the merge, because
`merge` replaces the whole row.

**Acceptance criteria.**
- One post writes one row in each table under the same `id`.
- A second post under that `id` replaces both and leaves `created_time` where it was, while
  `modified_time` moves.
- A failure writing the second table leaves neither written.
- Both dialects behave identically.

**Decided here.** **The key is derived from the posted name, not minted.** A corpus names its
samples `s4471` and the column is a `Uuid`, so `merge_tool_decision_db` hashes the name into a fixed
namespace: *a second post under one `id` replaces both rows* is only true while one name answers to
one key, and a minted key would make a re-reviewed sample a second row holding the same review. The
cost, stated: a sold row joins back to its corpus through `record.document` rather than through its
own key, and two corpora reusing one sample name collide here exactly as they already collide in
the name. It is in the spec.

**Decided here.** The transaction is the session's own — opened by the first statement, ended by
the commit in `merge_tool_decision_db` — rather than an explicit `session.begin()`. The explicit form refuses a
session anything has already read on, which `rebuild_tool_decision_dataset` legitimately hands it. The trade,
stated in the docstring: anything else left uncommitted on that session commits with the write, so
it is handed a session of its own.

**Verify.** `uv run pytest tests/store/test_write.py -q`, then `make integration`.

**Source.** § *What* — written in one transaction; § *`record`*; § *Invariants*.

### T16 · The route that takes a record, and the step that did not run

**Goal.** `POST /text2text/tool-decision/records` writes a record, and answers `422` naming the step
where one did not run.

**Acceptance criteria.**
- A finished record is written and the response says so.
- A document whose `personal_data` is `null` is a `422` naming the scan, and **nothing is written**.
- A document where a confirmed span's value survives into what ships is a `422` naming the
  redaction, and nothing is written.
- With no database attached the route answers `503` naming `DATAFORCE_DATABASE_URL`.

**Decided here.** A **third** refusal, and it is not a claim about the corpus: a declared facet the
table has a column for and the review left unanswered is a `422` **naming the facet**. The columns
are `NOT NULL` and § *`dataset`* wants that write to fail — this is where it fails legibly, so a
reviewer reads a facet to go and tick rather than a constraint violation. The route reads `FACETS`,
which it can, being an adapter; the tickable *values* are still nowhere below the edge.

The three refusals are ordered by what each costs to find out: no database is a fact about the
deployment, a step that did not run is about the document, and an unanswered facet is about the
row it would have made.

**Verify.** `uv run pytest tests/edge/test_endpoints.py -q`.

**Source.** § *The precondition*; § *The page* — no database attached.

### T17 · **approve** posts the record

**Goal.** The last step of the flow posts what it assembled, and says what happened.

**Acceptance criteria.**
- **approve** posts the thirteen keys and shows that the record landed.
- A `422` shows which step did not run, in the service's own words, and the reviewer stays on the
  card.
- With no store attached, **approve** says so and the eight steps still work.

**Decided since.** The answer's two times are what the card reads: equal is a first post, apart is
a replacement, and the note says which. Nothing is retried — a second post is a person pressing the
button again, which is the rule every other call on this page already follows.

**Not covered by a test.** There is no JavaScript harness in this repository and adding one is not
this task. What the route does with the body the page sends is covered
(`tests/edge/test_endpoints.py` posts the same thirteen keys); what the page sends is read, not
run.

**Source.** § *The page*.

### T18 · Step 7 draws a tick for every declared facet

**Goal.** Step 7 draws a tick for every declared facet, from the page's own list of values.

**Decided since.** There is no `declared-facets` route and the store holds no list of tickable
values. What a person may choose is not a fact about a corpus, so it lives where the tick boxes are
drawn. The cost, stated: a facet the page never draws a tick for is a column that is always `null`,
and nothing but review catches it.

**Context.** A facet declared in the profile and not on the page is a column that is always `null`.
The page holding its own copy of the list is how that happens.

**Acceptance criteria.**
- The page holds its own value list per facet, and step 7 draws a tick for each.
- `language` arrives with the record without being asked twice.
- Adding a facet is a change in the profile **and** a change in `ui/`. The two lists are held
  apart on purpose; a facet the page never draws a tick for is a column that is always `null`,
  and review is what catches it.

**Decided since.** The list is `DECLARED_FACETS` in `ui/app.js`, and each entry says how it is
picked: one of, any of, or yes. **Nothing is pre-ticked**, because a default on `domain` is a facet
filled in by the page and a declared facet is exactly the kind nothing may fill in — an unticked
`domain` is the `422` T16 names. A tick changed after the record was assembled drops step 8, on the
same terms as every other edit on the page.

`language` is not in the list. Step 1 declares it for the scan and the jury and it rides to the row
from there, which is what *without being asked twice* means.

**Not covered by a test**, on the same terms as T17.

**Source.** § *The page* — step 7 grows the ticks; § *The facets*.

### T19 · `dataset` can be dropped and rebuilt

**Goal.** `rebuild_tool_decision_dataset` deletes every row and recomputes it from `record`.

**Acceptance criteria.**
- After a rebuild, every row is identical to what it was.
- A `dataset` row edited by hand is corrected by a rebuild.
- A rebuild over an empty `record` empties `dataset`.

**Decided here.** It takes the builder as an argument rather than importing one, so the module
holding the SQL does not also decide whose samples it is holding. It answers how many rows it
wrote. **Nothing calls it yet**: it is the invariant made runnable, and a route for it is a
decision about who may drop a table, which is its own task.

A record that no longer passes the precondition stops the rebuild rather than being skipped:
finishing around it would leave a table nothing can call a function of the other.

**Verify.** `uv run pytest tests/store/test_write.py -q`.

**Source.** § *`dataset`* — computed from `record`; § *Invariants*.

---

## Phase 4 · The page is a deck

**Phase goal.** `ui/` shows one card at a time, the first card is the labelling guide, and the
statistics are under it.

### T20 · One card at a time, and a bar that moves between them

**Goal.** The eight steps become eight cards, with one navigation bar under them.

**Context.** § *The page* — one bar holds `<`, the rail and `>`; the rail carries eight states and
is a jump; `←` and `→` move a card only while focus is outside a field.

**Acceptance criteria.**
- One card is visible at a time and every card is reachable from every other, in any order.
- The rail shows each step's state and jumps to it.
- An arrow key inside a textarea moves the caret and not the card.
- The frame has a floor and no ceiling: a short card does not collapse it, a tall one scrolls inside
  it.
- Under `prefers-reduced-motion` the card changes with no slide.

**Source.** § *The page* — a deck, not a scroll.

### T21 · The first card is the guide, and the header is a title

**Goal.** A guide card in front of the eight, and a header that is a title and a strip.

**Acceptance criteria.**
- The guide says what a `tool_decision` sample is, what makes a label right including the empty
  label, what to tick at the two human steps, and what gets a sample refused.
- No route name, no file path, no sentence about wiring.
- The architecture prose that was in the header is gone from `ui/` and still on the flow page.

**Blocked by.** T20.

**Source.** § *The page* — the first card is the guide; the guide says what to do.

### T22 · The strip, and the statistics under the guide

**Goal.** Two numbers on every card, and the statistics under the guide.

**Acceptance criteria.**
- The strip shows how many rows are stored and how many matrix cells are still empty — the
  second counted on the page, by crossing its own tick lists against the grid the route answers.
- The guide card shows the joint distribution matrix, with the empty cells visible next to the
  full ones.
- The statistics are asked for on load and again after a record is written — not on a timer, not on
  every flip.
- With no database attached the strip says so and the guide still renders.

**Decided since.** The grid arrives as `counted_distribution_by_domain_and_call_trigger` and there
is no field naming the axes beside it: the field name is what says which two variables the grid is
over, rows first. A page that wants a different pair asks for a different field.

**Blocked by.** T11, T21.

**Source.** § *The page* — the statistics sit on the guide card; a strip stays on every card.

---

## What this plan decides that the spec does not

| Decision | Where | Why it is the plan's |
|---|---|---|
| `503` where no database is attached, with the variable named | T11, T16 | The spec says the page must work without a store; which status says so is a wire detail |
| `422` for a step that did not run, naming the step | T16 | § *The precondition* says refused, not which code |
| CI runs the store against no Postgres | T3 | `ci.yml`'s integration job has no service container. Adding one is a workflow decision, and until it is taken the Postgres half runs locally |
| The counting is built before the writing | Phases 2 and 3 | Only because `sample_building.py` was undeclared. The natural order is the other way |
| The row key is derived from the posted name | T15 | The spec says the key is a UUID and a corpus's names are not. Where one comes from is a wire detail; that one name keeps one key is not, and is now in the spec |
| A declared facet nobody ticked is a `422` naming it | T16 | The spec wants that write to fail. Which layer says so, and whether it reads as a facet or as a constraint, is the route's |
| The write commits rather than opening its own transaction | T15 | Both give *two rows or neither*. The explicit form refuses a session that has already been read on, which `rebuild_tool_decision_dataset` legitimately has |
| `rebuild_tool_decision_dataset` has no route | T19 | Who may drop a table is a decision, and nothing has asked for one |
