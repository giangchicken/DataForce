# Build plan

Tasks for building what `spec.md` specifies. Read that first; this document schedules it and does
not restate it. Where the two disagree, the spec wins and this file is wrong.

**Source:** [`spec.md`](spec.md), and [`layout.md`](layout.md) for which module each task's change
lands in. `AGENTS.md` for `H-4`, `H-8`, `H-10`, `R-2`, `R-6`, `E-1`, `T-1` and `T-5`.
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

The flow above the store is finished. `ui/` walks a sample through eight steps and assembles a
record, and **approve** posts it nowhere.

**Scope.** The database plumbing, this task's two tables, the pure pieces every text2text task
shares, the statistics over the corpus, the route that takes a record, and the page reshaped into a
deck with a guide on its first card.

**Assumption.** No corpus is loaded and none is imported. Every fixture is hand-written, and the
first rows in either table are the ones a labeller approves.

---

## What is not schedulable yet

`modalities/text2text/dataset_management/sample_building.py` declares nothing. § *Design* says why:
the steps a finished review goes through to become a stored row have not been watched happening to
a real sample, and the shape that gets invented first is the one every task afterwards has to
implement.

Everything that turns a **posted document** into a row waits on it — Phase 3 in full. Everything
that reads **rows already in the table** does not, because a test inserts those directly. So the
order here is unusual on purpose: the counting is built before the writing, because the counting is
the half that can proceed.

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

**A function is named by `R-6`, and the check is reading it aloud.** A noun phrase of at least two
words, never a bare noun — `cached_engine`, not `engine`; `open_session`, not `session`. One stem per
step, inflected, so the grammatical form says which side of the call the name sits on: a verb
phrase is the act, a past participle is the thing after the act. And `C-6`: the function that
decides and the function that writes are two functions.

---

## Phases

| # | Phase | Goal — the outcome that ends it |
|---|---|---|
| 0 | A database can be reached, and this task's tables exist | `created_tables` makes both tables on an empty SQLite file and on Postgres, and `make check` exercises the adapter with no server running |
| 1 | What every text2text sample has in common | The shapes, the duplicate check and this task's label measurements, all pure, with no word of `tool_decision` anywhere in `modalities/` |
| 2 | The corpus can be counted | `GET .../records/stats` answers every statistic in § *The statistics* over rows a test put there, each with its denominator, none of them stored |
| 3 | A reviewed sample lands | **approve** posts the record, both tables take it in one transaction, and a sample whose steps did not run is a `422` |
| 4 | The page is a deck | `ui/` shows one card at a time, the first card is the labelling guide, and the statistics are under it |

Phase 0 is groundwork and is not a vertical slice: nothing above it can be tested without a database
to open. Phase 1 needs no database at all. Phase 2 ends in something a person can see — a stats
endpoint answering over hand-inserted rows. **Phase 3 is blocked** until `sample_building.py`
declares an interface; everything else can be finished around it. Phase 4 needs Phase 2, because a
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
| T18 | Step 7 asks the profile which ticks to draw | 3 | T17 | M |
| T19 | `dataset` can be dropped and rebuilt | 3 | T15 | S |
| T20 | One card at a time, and a bar that moves between them | 4 | | L |
| T21 | The first card is the guide, and the header is a title | 4 | T20 | M |
| T22 | The strip, and the statistics under the guide | 4 | T11, T21 | M |

---

## Phase 0 · A database can be reached, and this task's tables exist

**Phase goal.** `created_tables` makes both tables on an empty SQLite file and on Postgres, and
`make check` exercises the adapter with no server running.

### T1 · The DSN is read once, and *no database* is a state

**Goal.** `edge/database.py` answers a session or `None`, from `DATAFORCE_DATABASE_URL` alone.

**Context.** Nothing in the repository opens a database. `sqlalchemy` is declared and unimported.
The state that matters most is the one where the variable is unset: § *The page* requires the whole
flow to work with no store attached, so `None` is an answer and not a failure.

**Approach.** `edge/database.py`, tagged `adapter`: one `Database` class holding the variable
name, the lock and the engine cache, with `cached_engine()` and `open_session()` on it, plus `Base`
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

**Goal.** `profile/tool_decision/dataset_management/schema.py` declares `ToolDecisionRecord` and
`ToolDecisionDataset`, and `created_tables(engine)` makes both.

**Context.** § *`record`* and § *`dataset`* fix the columns. The key is `id` alone, as a `Uuid`:
the table name carries the task, so nothing needs qualifying, and a UUID column needs no length
chosen for it.

**Approach.** `Uuid` for the key. `JSON` for `document`, `input`, `label` and `notes`. The nine
facet columns § *`dataset`* names, each typed for what it holds — a string for `language` and
`domain`, a boolean for `ambiguous` and `schema_valid`, an integer for the three counts, `JSON` for
`personal_data` and `call_shape`, which are both sets. Plain `DateTime` for the two times.

The tag is `adapter`, not `shape`: the file holds SQLAlchemy, and `H-8`'s table is what lets the
router import it while `services/` cannot. It imports `Base` from `edge/database.py`, so
one `MetaData` holds every task's tables.

**Acceptance criteria.**
- `created_tables` on an empty database makes exactly two tables with exactly the declared columns.
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
Both call `created_tables` and drop everything afterwards — which is why the variable names a
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

**Goal.** `modalities/text2text/dataset_management/schema.py` declares `StoredSample` and
`DuplicateGroups`.

**Context.** Two names, and the package's whole `shape` file. `StoredSample` is `input`, `label`
and the facets as a map — the row a profile's tables turn into columns. `DuplicateGroups` is the
two groups § *The statistics* names.

**Acceptance criteria.**
- Both are importable and neither imports anything from this package.
- `tests/guards/test_modality_names_no_profile.py` passes over the new module with no exemption —
  no name in it carries `tool` or `decision`.
- The module docstring's first word is `shape`.

**Source.** § *`dataset`*; § *The statistics* — the same input twice.

**Verify.** `uv run pytest tests/guards -q` and `make check`.

### T6 · The same input twice, over a whole corpus

**Goal.** `duplicate_data_checking.py` answers `DuplicateGroups` -- the row keys of each group
-- over every stored input.

**Context.** § *Design* — *grouping by input* — takes the Python scan over a stored digest, and
names the digest as the change to make when the scan stops being instant. `data_quality/` held a
module of the same name: an abstract class over an embedding call whose `duplicate_groups` returned
`None`, with a subclass that implemented no socket and could not be constructed. It is deleted, and
this file takes its name and its two names — one duplicate check in the modality, not two.

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
caller is: `described_labels` in `services/tool_decision/dataset_management.py`, T10.

**Cost, stated.** `H-10`'s argument stands — a second text2text task writes that line again rather
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

**Goal.** `profile/tool_decision/dataset_management/label_statistics.py` answers everything about a
label that says `tool`.

**Context.** `called_tools`, `required_parameters`, `schema_valid_label` and `tool_coverage` all
read inside a label and a catalog. This is the layer allowed to name them.

**Approach.** `schema_valid_label` is BFCL's AST check against **this row's own catalog**: every
call names a tool the sample was offered and supplies that tool's required parameters. A label
calling a tool the sample never offered is a broken row, not a hard example.

**Acceptance criteria.**
- A call naming a tool absent from the catalog is invalid.
- A call missing a required parameter is invalid; a call missing an optional one is valid.
- An empty label is valid and counts as `0` calls.
- `tool_coverage` answers a count per offered tool, a tool never called included as `0`, and a
  tool called without being offered counted rather than dropped.
- Counting calls per label is **not** here — see T10.

**Source.** § *The facets* — `schema_valid`; § *The statistics* — schema validity, tool coverage.

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

**Acceptance criteria.**
- `counted_by_facet` returns a count per value for each of the nine facet columns, over rows a test
  inserted directly.
- `counted_by_pair` groups by two named columns and returns only the pairs that exist.
- `row_counts` answers how many rows each table holds.
- Both dialects return the same answers for the same fixture.

**Source.** § *The statistics* — the coverage matrix.

**Verify.** `uv run pytest tests/store/test_schema.py -q`, then `make integration`.

**Out of scope.** Filling in the pairs that do not exist (T10).

### T10 · The empty cells, put back

**Goal.** `services/tool_decision/dataset_management.py` answers a matrix in which every pair of
declared values appears, the pairs with no rows included and zero.

**Context.** **The finding is the zeros.** A `GROUP BY` returns only what exists, so the empty cells
— the whole point of the matrix — are exactly what SQL cannot hand back. They are put back from the
product of `DOMAINS` and `CALL_SHAPES`.

**Acceptance criteria.**
- How many rows make each number of calls comes back, counting **entries** rather than tools that
  could be read: an entry naming no tool is still an attempt at a call, and letting it fall to `0`
  would pad the no-call share that irrelevance detection is measured from. `0`, `1` and more are
  all readable off the answer.
- How many rows carry a label at all, out of how many — `[]` and `null` both count as *not
  labelled*, and the share over zero rows divides nothing.
- Over a fixture whose rows cover three of twelve cells, the answer has twelve cells and nine zeros.
- The count of empty cells is answered on its own, because the strip reads it.
- A value present in the rows but absent from the declared list appears in the matrix rather than
  being dropped silently.
- The function is pure and takes no session.

**Source.** § *The statistics* — the coverage matrix, the finding is the zeros.

**Verify.** `uv run pytest tests/services/test_dataset_management.py -q`.

### T11 · The statistics route, and what it says with no database

**Goal.** `GET /text2text/tool-decision/records/stats` answers § *The statistics* in full, and says
so plainly where no database is attached.

**Context.** The router is where the profile's SQL and the service's arithmetic meet. The response
shapes live here, because they are the shape of one HTTP answer.

**Approach.** The handler opens a session, asks the profile's `schema.py` for the counts and the
rows the duplicate grouping needs, passes them to the service, and answers `CorpusStats`. Where
`store.open_session()` is `None` it answers `503` naming `DATAFORCE_DATABASE_URL` — the variable, so the
message says what to set.

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

**Blocked.** Every task here waits on T12, and T12 is a decision rather than an implementation.

### T12 · `sample_building.py` declares what a task must answer

**Goal.** `modalities/text2text/dataset_management/sample_building.py` declares an interface, and
the precondition § *The precondition* requires.

**Context.** The module is empty by decision, not by oversight: § *Design* says the steps have not
been watched happening to a real sample, and the shape invented first is the one every task
afterwards has to implement. **This task is where that decision gets taken**, and it should be taken
by whoever has watched a sample go through — not derived from this plan.

What the rest of the design already commits it to, whatever shape it takes:

- it produces a `StoredSample` — `input`, `label`, facets — out of the thirteen-key document;
- it refuses a document whose `personal_data` is `null`, or where a confirmed span's value survives
  into `new_messages`, `new_tools` or `new_label`, and the refusal names the step;
- what it refuses on is the modality's and no task overrides it (§ *The precondition*);
- what a task's `input` holds, which facets that task computes, and which it asks a person to tick
  are the task's, so they are whatever this file leaves open;
- no name in it carries `tool` or `decision`.

**Acceptance criteria.** Set by whoever takes the decision. The five commitments above are the
constraints, not the design.

**Source.** § *The precondition*; § *Where each piece is declared*; § *Design* — why
`sample_building` is left open.

### T13 · The profile answers it

**Goal.** `profile/tool_decision/dataset_management/sample_building.py` says what a `tool_decision`
sample ships as and which facets it computes and declares.

**Context.** `{messages, tools}` from the `new_` keys, or the originals where a `new_` key is
`null`. `number_turns`, `number_label_tools`, `number_provided_tools` and `schema_valid` computed.
`domain`, `call_shape`, `direction` and `have_conversation_flow` declared — the last two into
`notes`.

**Acceptance criteria.**
- The shipped input holds the turns and the catalog together, and the counts are of what **ships**,
  not of what arrived.
- A document with every `new_` key `null` ships the originals.
- `schema_valid` is computed from this row's own catalog by T8's check.
- The declared facets are answered as a list the page can ask for, not held twice.

**Blocked by.** T12, T8.

**Source.** § *Where each piece is declared*; § *The facets*.

### T14 · The record's envelope, declared at the boundary

**Goal.** The router declares the thirteen keys it accepts, and nothing below it does.

**Context.** § *`record`* — `document` is one JSON column and no query reads inside it, so the
envelope stays declared where it is built. `extra="allow"`, because a key the page adds is not a
reason to reject a record.

**Acceptance criteria.**
- A document with all thirteen keys validates; one missing `id` does not.
- An unknown extra key is kept, not dropped and not rejected.
- The model is not named `Record`: `R-2` refuses a name that already names a table.

**Blocked by.** T12.

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

**Blocked by.** T13, T14.

**Source.** § *What* — written in one transaction; § *`record`*; § *Invariants*.

### T16 · The route that takes a record, and the step that did not run

**Goal.** `POST /text2text/tool-decision/records` writes a record, and answers `422` naming the step
where one did not run.

**Acceptance criteria.**
- A finished record is written and the response says so.
- A document whose `personal_data` is `null` is a `422` naming the scan, and **nothing is written**.
- A document where a confirmed span's value survives into a `new_` key is a `422` naming the
  redaction, and nothing is written.
- With no database attached the route answers `503` naming `DATAFORCE_DATABASE_URL`.

**Blocked by.** T15.

**Source.** § *The precondition*; § *The page* — no database attached.

### T17 · **approve** posts the record

**Goal.** The last step of the flow posts what it assembled, and says what happened.

**Acceptance criteria.**
- **approve** posts the thirteen keys and shows that the record landed.
- A `422` shows which step did not run, in the service's own words, and the reviewer stays on the
  card.
- With no store attached, **approve** says so and the eight steps still work.

**Blocked by.** T16.

**Source.** § *The page*.

### T18 · Step 7 asks the profile which ticks to draw

**Goal.** `GET .../records/declared-facets` answers the list, and step 7 draws it.

**Context.** A facet declared in the profile and not on the page is a column that is always `null`.
The page holding its own copy of the list is how that happens.

**Acceptance criteria.**
- The route answers the profile's declared facets and their values.
- Step 7 draws a tick for each, and `language` arrives with the record without being asked twice.
- Adding a declared facet in the profile puts a tick on the page with no change to `ui/`.

**Blocked by.** T17.

**Source.** § *The page* — step 7 grows the ticks; § *The facets*.

### T19 · `dataset` can be dropped and rebuilt

**Goal.** `rebuilt_dataset` deletes every row and recomputes it from `record`.

**Acceptance criteria.**
- After a rebuild, every row is identical to what it was.
- A `dataset` row edited by hand is corrected by a rebuild.
- A rebuild over an empty `record` empties `dataset`.

**Blocked by.** T15.

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
- The strip shows how many rows are stored and how many matrix cells are still empty.
- The guide card shows the coverage matrix, with the empty cells visible next to the full ones.
- The statistics are asked for on load and again after a record is written — not on a timer, not on
  every flip.
- With no database attached the strip says so and the guide still renders.

**Blocked by.** T11, T21.

**Source.** § *The page* — the statistics sit on the guide card; a strip stays on every card.

---

## What this plan decides that the spec does not

| Decision | Where | Why it is the plan's |
|---|---|---|
| `503` where no database is attached, with the variable named | T11, T16 | The spec says the page must work without a store; which status says so is a wire detail |
| `422` for a step that did not run, naming the step | T16 | § *The precondition* says refused, not which code |
| CI runs the store against no Postgres | T3 | `ci.yml`'s integration job has no service container. Adding one is a workflow decision, and until it is taken the Postgres half runs locally |
| The counting is built before the writing | Phases 2 and 3 | Only because `sample_building.py` is undeclared. The natural order is the other way |
