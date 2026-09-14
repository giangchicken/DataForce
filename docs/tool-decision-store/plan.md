# Build plan

Tasks for building what `spec.md` specifies. Read that first; this document schedules it and does
not restate it. Where the two disagree, the spec wins and this file is wrong.

**Source:** [`spec.md`](spec.md) @ `4bc7471`. `AGENTS.md` @ `7df1e0b` for `H-8`, `H-10`, `E-1`,
`R-2`, `T-1` and `T-5`. `docs/tool-decision-pipeline/spec.md` @ `4bc7471` for the flow this store
sits under, and that feature's `plan.md` T14 — *The record's round trip*, withdrawn with the store
because the decision this spec takes had not been taken. This plan is what picks it back up.

**State at the time of writing.** Nothing of the store exists, and three things already point at it:

- `pyproject.toml` declares `sqlalchemy>=2.0.52,<2.1` and `alembic>=1.19.1`, both unimported, each
  with a comment saying the store is deferred. Both comments become false in Phase 0.
- `alembic.ini` is three lines of configuration and names `migrations/`, which does not exist —
  `alembic upgrade head` fails today with `Path doesn't exist: …/migrations`. Its comments cite
  `edge/store/session.py`, which Phase 0 creates, and `edge/observability.py`, which does not exist
  and never did: the events handler is `edge/events.py`.
- `.github/workflows/ci.yml` already has the `integration` job, already passes
  `DATAFORCE_TEST_DATABASE_URL`, and already says in a comment that the slow half is "the store
  against a real Postgres". The job runs a suite that does not exist.

`src/dataforce/edge/store/` survives as a directory holding nothing but `__pycache__` from the
deleted `records.py`. `make check` is green: ruff, `mypy --strict` over 31 modules, 307 tests.

The flow above the store is finished. `ui/` walks a sample through eight steps and assembles a
twelve-key record, and **approve** posts it nowhere.

**Scope.** The two tables, the migration under them, the route that takes a record, the door that
decides which table it lands in, the `class` facets, the figures endpoint, and the page reshaped
into a deck with a guide on its first card.

**Assumption.** No corpus is loaded and none is imported. Every fixture is hand-written, and the
first rows in either table are the ones a labeller approves.

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
| § *The door* | a named section or a bold requirement heading in `spec.md`. Cited by its words, because a number is a second thing to keep in sync |
| `H-8`, `E-1`, `R-2` | a rule in `AGENTS.md`. The ID is stable and citable |
| `T7` | a task in this file. The number is its name, not its place in the order |
| step 5 | one of the flow's eight steps, numbered by the labelling page and only there |
| the record | the twelve-key document `ui/app.js` assembles. `record` in code font is the table |

---

## Decisions this plan takes once

Four shapes span several tasks. They are settled here so no task settles them differently.

**Logic is never handed a session, because it never needs one.** The spec's § *Context* asks that a
service not import the store and be handed it as an argument. This plan does better and says why:
the decisions — which table a record belongs in, what `class` holds, what each figure is — are pure
functions of a document, and the writing and reading are the adapter's. So
`services/tool_decision/` takes documents and returns documents, `edge/store/` takes those and
talks to SQLAlchemy, and the router — an adapter, which `H-8` permits to import logic — is where
the two meet. No socket, no protocol, no session parameter: the argument the spec offered to hand
down is one nothing below the edge asks for. The cost, stated: the three evidence figures read
every `record` row's document in Python, so the adapter hands rows up rather than aggregating them
down, and that is the one figure path where row count matters.

**No default database.** The deleted `edge/store/records.py` fell back to
`sqlite+pysqlite:///dataforce.sqlite3` when `DATAFORCE_DATABASE_URL` was unset. It cannot now:
§ *The page* requires a state in which no database is attached, the strip says so, and all eight
steps still work. A default file makes that state unreachable, and the first time anyone notices is
when a corpus is in a file nobody meant to create. Unset means no store.

**The posted body carries the declared half of `class`, and the derived half is never posted.**
§ *`class`* says no declared facet is ever computed and no derived facet is ever typed. The only
way to keep that at the boundary is for the two halves to arrive by different routes: the page
posts what the human ticked, the write computes the rest, and `dataset.class` is the two merged.
`record.document` keeps the declared half as posted, because it is part of what the review
answered. This makes the record thirteen keys rather than twelve — see § *What this plan asks of
the spec*.

**One suite, two databases.** `make check` runs the store's tests against a migrated temporary
SQLite file: no server, no network, and the commit gate covers the adapter. `make integration` runs
the same tests against `DATAFORCE_TEST_DATABASE_URL`. *One adapter, two DSNs* is a claim in the
spec, and a suite that only ever runs on one of them is not evidence for it.

---

## Phases

| # | Phase | Goal — the outcome that ends it |
|---|---|---|
| 0 | A database can be reached, and its schema is a migration | `alembic upgrade head` creates both tables on an empty SQLite file and on Postgres, and `make check` exercises the adapter with no server running |
| 1 | A reviewed sample lands, and only a de-identified one is sellable | **approve** posts the record, `record` takes every one of them, `dataset` takes only those through the door, and both writes are one transaction |
| 2 | The corpus describes itself | Every `dataset` row carries a full `class` — the derived half computed at write time, the declared half ticked at step 7 |
| 3 | The figures answer | `GET .../records/stats` answers every figure in § *The figures*, each with its denominator, none of them stored |
| 4 | The page is a deck | `ui/` shows one card at a time, the first card is the labelling guide, and the figures are under it |

Phase 0 is groundwork and is not a vertical slice: nothing above it can be written or tested
without a database to open. Phases 1 to 3 are each a slice that ends in something a person can see.
Phase 4 needs Phase 3, because a deck whose first card holds figures needs figures; the deck's own
navigation does not, and T15 could move earlier if the page becomes unpleasant to work in before
then.

---

## The tasks

**Needs** is what must land before this task can start; blank means *as soon as the phase opens*.
**Size** is a shape, not an estimate — **S** one module or one file · **M** several modules, or one
algorithm to get right · **L** more than one sitting, so split it if it grows while you work.

| # | Task | Phase | Needs | Size |
|---|---|---|---|---|
| T1 | The DSN is read once, and *no database* is a state | 0 | | S |
| T2 | Two tables, and the columns the queries need | 0 | T1 | M |
| T3 | The first schema is a migration | 0 | T2 | M |
| T4 | The store's suite runs on a file and on a server | 0 | T3 | M |
| T5 | The record's envelope, declared at the boundary | 1 | T2 | S |
| T6 | The door, and the values it will not let through | 1 | | M |
| T7 | Two writes, one transaction | 1 | T4, T5, T6 | M |
| T8 | The route, and what it answers when there is no database | 1 | T7 | S |
| T9 | **approve** posts the record | 1 | T8 | M |
| T10 | The derived half of `class` | 2 | T7 | M |
| T11 | The declared half, ticked where the human already is | 2 | T9 | M |
| T12 | `dataset` can be dropped and rebuilt | 2 | T10, T11 | S |
| T13 | The counts over `dataset`, and the empty cells | 3 | T12 | L |
| T14 | What the evidence buys, and what is not measured | 3 | T13 | M |
| T15 | One card at a time, and a bar that moves between them | 4 | T9 | L |
| T16 | The first card is the guide, and the header is a title | 4 | T15 | M |
| T17 | The strip, and the figures under the guide | 4 | T14, T16 | M |

---

## Phase 0 · A database can be reached, and its schema is a migration

**Goal.** `alembic upgrade head` creates both tables on an empty SQLite file and on Postgres, and
`make check` exercises the adapter with no server running.

### T1 · The DSN is read once, and *no database* is a state

**Goal.** `DATAFORCE_DATABASE_URL` is read in one module, an unset variable answers *no store*
rather than a file, and nothing below `edge/` can see either.

**Context.** No module reads the variable today. `alembic.ini` says in a comment that it is read
"through `edge/store/session.py`", which is a file that does not exist, and `.gitignore` carries an
entry for `dataforce.sqlite3` whose comment cites `§ *The question store*` — a section of a spec
that was deleted. The deleted `edge/store/records.py` built an engine inside every
`open_session()` call, which is a connection pool per session and the reason a pool exists thrown
away.

`tests/conftest.py` clears nine environment variables under `no_endpoints` so that a developer's
exported credentials cannot reach a real service from a unit test. `DATAFORCE_DATABASE_URL` is not
among them, and the moment T7 lands, an exported DSN would make the store suite write to whatever
it names.

**Approach.** `edge/store/session.py`, tagged `adapter`: `database_url() -> str | None` reading the
variable and returning `None` where it is unset or empty, one engine built lazily and kept for the
process, and a session factory over it. Nothing else in the package reads the variable.

Add `DATAFORCE_DATABASE_URL` to `conftest.py`'s list, with the reason the others carry. Rewrite the
`.gitignore` entry's comment: the pattern stays, because a developer will point the DSN at a file in
the tree, but it is no longer a default anything falls back to. Delete the orphaned
`src/dataforce/edge/store/__pycache__`.

**Acceptance criteria.** With the variable unset, asking for a session answers nothing and builds
no engine. With it set to a temporary SQLite path, a session opens and closes. A second call reuses
the first engine. `mypy --strict` is green, and `E-1` still passes: nothing in `services/`,
`profile/` or `modalities/` imports this module.

**Source.** § *Context* — the DSN read once, and the credential-shaped line that does not go in a
public repository; § *The page*, on a page that works with no database attached.

**Verify.** `make check`.

**Out of scope.** Any table, any write. `pyproject.toml`'s "nothing in `src/` imports it yet"
comments, which T2 and T3 make false.

### T2 · Two tables, and the columns the queries need

**Goal.** `record` and `dataset` exist as declarative classes, keyed the same way, and neither one
imports anything but the shapes it is made of.

**Context.** § *`record`* and § *`dataset`* name every column. Two of them are traps.

`created_time` and `modified_time` are both timezone-aware UTC. SQLite has no timezone type:
`DateTime(timezone=True)` is accepted and then hands back a naive `datetime`, so a value written as
aware reads back as naive and a comparison against `datetime.now(UTC)` raises. Postgres does not do
this, so a suite that only runs on Postgres never sees it — which is what the other half of *one
suite, two databases* is for. Either store UTC and re-attach `tzinfo` on load through a
`TypeDecorator`, or accept naive UTC everywhere and convert at the edge. Take one and say which in
the module docstring.

The primary key is `(task, id)` — composite, on both tables, and § *Open* records that `id` alone
was considered and why it was not taken. `ID_LENGTH = 64` in the deleted module was chosen so a
dialect with an index-length limit can index it; the same constraint applies to `task`.

**Approach.** `edge/store/schema.py`, tagged `shape`, holding `Base` and the two classes. It
imports nothing from this package: `shape` may import nothing, and that is what keeps `E-1`
meaningful for a store, whose coupling — `E-1`'s own stated known gap — does not show up in the
import graph at all.

`record.document`, `dataset.input`, `dataset.label` and `dataset.class` are JSON columns. `class` is
a Python keyword, so the attribute cannot be spelled that way; name the attribute for what it holds
and pin the column name to `class` with `mapped_column("class", ...)`, because the column name is
what a buyer's query and the spec both say.

**Acceptance criteria.** Both classes exist with every column § *`record`* and § *`dataset`* name,
composite primary keys, and no nullable column the spec does not make nullable. A `datetime` written
aware reads back aware on SQLite. `mypy --strict` is green. `E-1` passes.

**Source.** § *`record`*; § *`dataset`*; `H-8`'s `shape` row; `E-1`'s known gap.

**Verify.** `make check`.

**Out of scope.** Creating the tables — that is T3, and `create_all` is not how it happens.

**Blocked by.** T1.

### T3 · The first schema is a migration

**Goal.** `alembic upgrade head` against an empty database creates both tables, `downgrade base`
removes them, and `alembic check` reports no difference between the migration and `schema.py`.

**Context.** `alembic.ini` exists and `migrations/` does not, so `alembic` fails before it reads
anything. The ini deliberately declares no `sqlalchemy.url` and no logging configuration; `env.py`
must therefore get the DSN from `session.py` and configure no handler, which is the opposite of
what `alembic init` generates. Its comment naming `edge/observability.py` is wrong — the events
handler is `edge/events.py` — and this is the task that is in the file.

**Approach.** `migrations/env.py`, `migrations/script.py.mako`, and one revision creating both
tables. `env.py` imports `Base.metadata` from `edge/store/schema.py` for autogenerate, and the DSN
from `edge/store/session.py`; where the DSN is unset it refuses with a sentence naming the variable
rather than falling back. No `fileConfig(config.config_file_name)` call, because there is no logging
section to read.

**Acceptance criteria.** Against a temporary SQLite file: `upgrade head` creates `record` and
`dataset` with the composite keys, `downgrade base` leaves an empty database, and `alembic check`
is silent. With `DATAFORCE_DATABASE_URL` unset, every alembic command refuses by naming the
variable. `alembic.ini` cites a file that exists.

**Source.** § *Context* — the first schema is a migration and never a `create_all` side effect.

**Verify.**
`DATAFORCE_DATABASE_URL=sqlite+pysqlite:///$(mktemp -u).sqlite3 uv run alembic upgrade head` then
`alembic check` then `alembic downgrade base`, each exiting 0; `make check`.

**Out of scope.** A second revision. Autogenerate's behaviour against Postgres-only types, since
neither table has one.

**Blocked by.** T2.

### T4 · The store's suite runs on a file and on a server

**Goal.** `make check` exercises the store against a migrated temporary SQLite database, and
`make integration` runs the same tests against `DATAFORCE_TEST_DATABASE_URL` or skips saying so.

**Context.** `.github/workflows/ci.yml` already declares the variable and already says the
integration job is "the store against a real Postgres". Its comment is explicit that *not run* and
*passed* are different claims, and that a job running a suite which silently skips itself makes
them one — so the skip has to be visible.

`tests/` has no `store/` directory. `tests/conftest.py`'s two autouse fixtures apply everywhere and
stay.

**Approach.** `tests/store/conftest.py` with one fixture that yields a session against a migrated
database, parameterised over the DSNs available: always a temporary SQLite file, and
`DATAFORCE_TEST_DATABASE_URL` as well when it is set. Migrate by running alembic, not by
`create_all` — otherwise the suite proves the models and not the schema that ships. The
Postgres parameter carries the `integration` marker, so `make check` runs the SQLite half and
`make integration` runs both.

**Acceptance criteria.** `make check` runs at least one store test and makes no network call.
`make integration` with no test DSN set reports the Postgres parameter as skipped, with the
variable named in the skip reason. With one set, the same assertions run twice.

**Source.** § *Design* — one adapter, two DSNs.

**Verify.** `uv run pytest tests/store -q`; `make check`; `make integration` with the variable
unset, reading the skip reason.

**Out of scope.** What the tests assert, beyond the fixture proving itself — the assertions arrive
with T7.

**Blocked by.** T3.

---

## Phase 1 · A reviewed sample lands, and only a de-identified one is sellable

**Goal.** **approve** posts the record, `record` takes every one of them, `dataset` takes only
those through the door, and both writes are one transaction.

**What this phase is.** `docs/tool-decision-pipeline/plan.md` T14 — *The record's round trip* —
withdrawn at `1ecd94f` because the store had two refusals and no decision behind either. The spec
now takes it: nothing is refused, everything is written, and the question is which table.

### T5 · The record's envelope, declared at the boundary

**Goal.** The route's request model declares the record's shape, and nothing else in the package
does.

**Context.** The record is assembled in `ui/app.js` and has never been declared in Python. Its keys
are `id`, `messages`, `tools`, `label`, `new_messages`, `new_tools`, `new_label`, `personal_data`,
`duplicate`, `abnormal`, `llm`, `sft`, plus whatever extra keys the pasted sample carried —
`app.js` spreads `held.sample` first, and `Sample` is `extra="allow"` precisely so a corpus's own
keys are not dropped.

The class cannot be called `Record`: `R-2` refuses a name that already names a table, and `record`
is one. `ReviewedSample` says what it is and sits beside the `Sample` it was made from.

A sample with no `id` is a 422 from every route on this router already, and the labelling page does
not check for one before step 8 — so the first thing this route will refuse in practice is a record
the page was happy to assemble. That is a defect in the page, not in this route, and it is named
here so whoever hits it knows where it lives.

**Approach.** `ReviewedSample` in `edge/routers/text2text/tool_decision.py`, beside `Sample` and on
the same terms: `extra="allow"`, required `id`, every other key defaulted to what the page sends
when a step was not asked. The response shape names which tables took the row and why the other did
not.

**Acceptance criteria.** The exact body `ui/app.js` assembles validates, extra keys and all. A body
with no `id` is 422 naming `id`. A body whose `personal_data` is `null` validates — that is a
sample nobody scanned, and the door's business, not the schema's.

**Source.** § *`record`* — the document whole and unaltered; `R-2`.

**Verify.** `make check`.

**Out of scope.** The route itself (T8) and what the door does with the body (T6).

**Blocked by.** T2.

### T6 · The door, and the values it will not let through

**Goal.** One pure function says whether a document may become a `dataset` row, and says why not
when it may not.

**Context.** This is the decision the pipeline's T14 could not make. Its plan read the refusal off
`personal_data.outcome` and refused `reported` — which is the word for *no detector claimed
anything*, so the rule as written would have refused every clean sample. § *The door* settles it:
`redacted` and `reported` pass, `withheld` does not, and `personal_data: null` does not.

There is a second check, and it is not redundant with the first. `outcome` is decided over
`review_text`, while `new_messages`, `new_tools` and `new_label` are what the redaction route
answered over other strings entirely. A document can be `redacted` and still carry a confirmed
value in a field the offsets never indexed. § *Invariants* is the rule: no row in `dataset` holds a
value the redaction was asked to remove and did not.

`span_values` and `replaced_node` — the walk that finds those values — were written and deleted;
they are in the history at `1ecd94f:src/dataforce/services/tool_decision/human_review.py`. What is
needed here is the search, not the replacement: the document arrives already redacted, and a hit is
a row that does not ship.

The three originals — `messages`, `tools`, `label` — hold raw content on purpose. Checking them
would fail by design. Check the three `new_` keys and nothing else.

**Approach.** `services/tool_decision/records.py`, tagged `logic` and importing no adapter. One
function taking the document and answering the `dataset` row's `input` and `label`, or nothing plus
the reason. Its tests open `tests/services/`, which is new: a service has been exercised from
`tests/profile/test_personal_data.py` until now, and a store's logic is not a profile's. `input` is `{messages, tools}` built from `new_messages` and `new_tools` — or from
`messages` and `tools` where the corresponding `new_` key is `null`, which is the page's spelling
for *nobody made a new version* — and `label` is `new_label`.

**Acceptance criteria.** `redacted` passes; `reported` passes; `withheld` does not, naming the
outcome; `personal_data: null` does not, naming that nobody scanned it. A `redacted` document whose
`new_label` still contains a confirmed span's value does not pass, and the reason names the
placeholder that should have been there. A document with `new_tools: null` produces an `input`
holding the catalog that arrived.

**Source.** § *The door*; § *`dataset`*; § *Invariants*.

**Verify.** `uv run pytest tests/services -q`; `make check`.

**Out of scope.** `class` (T10, T11) and the write itself (T7).

### T7 · Two writes, one transaction

**Goal.** One call writes `record` always and `dataset` when the door allows, in one transaction,
and a second call under the same key leaves the two tables agreeing.

**Context.** Three things make this harder than one `merge`.

`Session.merge` replaces the whole row, so a naive second write moves `created_time` to now. It is
the column that never changes, so it has to be read before merging and carried forward.

A second post can make a row *less* sellable. A record posted `redacted` and re-posted `withheld`
has a `dataset` row that must not survive — § *Invariants* says `dataset` is a function of
`record`, and a stale row is that function lying. So the write is not two merges: it is a merge, a
merge-or-delete, and one commit.

The cost of replacing is the spec's and is stated there: the review the row used to hold is gone.
This task does not add a history table to soften it.

**Approach.** `edge/store/records.py`, tagged `adapter`. One function taking the document and the
door's answer, doing both writes in one `session.begin()`, and returning what landed where.
`Session.merge` for both, so no dialect-specific upsert is reached for.

**Acceptance criteria.** A document posted once appears in both tables where the door allows, and
in `record` only where it does not. Posted twice: `created_time` is unchanged, `modified_time` has
moved, and the document is the second one. Posted `redacted` then `withheld`: `record` has the
second document and `dataset` has no row under that key. A failure writing the second table leaves
neither — asserted by making `dataset` fail and reading `record` back empty. Every assertion runs on
SQLite under `make check` and on Postgres under `make integration`.

**Source.** § *`record`*; § *`dataset`*; § *Design* — one adapter, two DSNs.

**Verify.** `uv run pytest tests/store -q`; `make check`.

**Out of scope.** The route (T8). Deleting a row on request — § *Out of Scope* says a deletion
request is a process, not a column.

**Blocked by.** T4, T5, T6.

### T8 · The route, and what it answers when there is no database

**Goal.** `POST /text2text/tool-decision/records` takes a record and answers which tables took it.

**Context.** The router's module docstring currently states that there is no route that stores
anything. That sentence is this task's to rewrite, not to work around.

There is no status code in the spec for *no database is attached*. It is not a refusal of the
request — the body is fine and would be stored anywhere else — so 422, which this router uses for a
declaration it cannot act on, is the wrong word. This plan takes **503 with the variable named in
the detail**, on the grounds that the condition is about this deployment and is fixed by attaching
a database rather than by changing the request. If the user prefers otherwise, this is the one line
that changes.

**Approach.** The handler reads the body as `ReviewedSample`, calls the door, calls the store, and
maps the two failures: no database attached, and a `ConfigError` if the door ever raises one. The
response says which tables took the row and, where `dataset` did not, why.

**Acceptance criteria.** A record posts and comes back naming both tables. A `withheld` record
posts and comes back naming `record` only, with the outcome as the reason. With
`DATAFORCE_DATABASE_URL` unset the route answers 503 naming the variable, and every other route on
the router still answers. The router's docstring says what is true.

**Source.** § *The door* — the response says which of the two tables took the row and why the other
did not.

**Verify.** `uv run pytest tests/edge -q`; `make check`.

**Out of scope.** Auth on the write route — § *Out of Scope*, and one guarded door in an unguarded
building is theatre.

**Blocked by.** T7.

### T9 · **approve** posts the record

**Goal.** Pressing **approve** stores the record, and the last step says which tables took it.

**Context.** Four places in the tree assert that nothing stores a record, and all four become false
together. Missing one leaves the repository arguing with itself:

- `ui/app.js` — the approved note reads "approved, and posted nowhere … take it off the screen".
- `ui/index.html` — step 8's note, which also carries "deferred until this flow is finished", a
  promise that went stale when the flow finished.
- `edge/routers/text2text/tool_decision.py` — the module docstring's second paragraph.
- `README.md` — "Nothing stores a record yet".

`docs/tool-decision-pipeline/spec.md` is the fifth: its requirement that **approve** posts nowhere,
and its § *Out of Scope* store bullet, are what this feature has now answered. Rewrite them to what
is true rather than annotating them — a spec states current truth.

**Approach.** `approve()` posts and shows the answer. A refusal is shown where it happened, which
is the rule step 8 already follows for **assemble**. The record stays frozen on the page after a
successful post, because the reviewer may still want to read it.

**Acceptance criteria.** **approve** posts and the step says which tables took the row. A 503
because no database is attached is shown in step 8 in the service's words, and the record stays on
screen. Nothing in the tree still says a record is stored nowhere.

**Source.** § *The page*; `docs/tool-decision-pipeline/spec.md`'s **approve** requirement, which
this task rewrites.

**Verify.** `make check`; serve the app and walk one sample through all eight steps against a
SQLite DSN, then `SELECT` both tables.

**Out of scope.** The deck (Phase 4). The declared facets (T11).

**Blocked by.** T8.

---

## Phase 2 · The corpus describes itself

**Goal.** Every `dataset` row carries a full `class` — the derived half computed at write time, the
declared half ticked at step 7.

### T10 · The derived half of `class`

**Goal.** Five facets are computed from the document every time a row is written, and nobody can
type one.

**Context.** § *`class`* names them: `personal_data`, `number_turns`, `number_label_tools`,
`number_provided_tools`, `schema_valid`. Four are counts and one is a check.

`schema_valid` is BFCL's AST check turned on the corpus: every call names a tool in this row's own
catalog and supplies that tool's required parameters. The catalog is OpenAI tool format, so the
required list is `function.parameters.required`. `jsonschema` is already a declared dependency, and
`agent_toolkit` already holds `normalize_prediction` and `text_to_openai_tool_format` — check
before writing a parser, because `tests/guards/test_toolkit_not_reimplemented.py` exists for this.

`number_label_tools` counts `null` and `[]` alike as zero. § *Open* records that the two spellings
are not one answer elsewhere — `label: null` canonicalises as the text `null` and never matches a
panel that answered `[]`, so `label_agreement` reads 0.0 for a panel that agreed. This task counts;
it does not fold. Folding them is a task rule with a consumer on either side and is not this
task's to take.

`personal_data` reads the confirmed spans' `personal_data_class`, and `[]` where the sample had
none — which is a different fact from *nobody scanned it*, and both reach here as a `dataset` row
only if the door let them through.

**Approach.** In `services/tool_decision/records.py`, beside the door, since both read the same
document and the projection is one computation.

**Acceptance criteria.** A sample with two confirmed spans of two classes gets both, deduplicated.
An empty label gives `number_label_tools: 0`, whether it is spelled `null` or `[]`. A call naming a
tool the catalog does not offer gives `schema_valid: false`; so does a call missing a required
parameter; a call with an extra parameter does not. `number_provided_tools` counts the shipped
catalog, not the one that arrived, where the two differ.

**Source.** § *`class`* — the derived list; § *Design* — why `class` is derived where it can be.

**Verify.** `uv run pytest tests/services -q`; `make check`.

**Out of scope.** The declared half.

**Blocked by.** T7.

### T11 · The declared half, ticked where the human already is

**Goal.** Step 7 carries the ticks for every declared facet, and they ride to the store on the
record.

**Context.** § *`class`* names six: `direction`, `domain`, `language`, `have_conversation_flow`,
`call_shape`, `ambiguous`. Five are ticked; `language` is not.

`language` is already declared at step 1, handed to both model steps, and then thrown away — the
spec says so. Asking for it a second time at step 7 would be a second declaration of one fact, and
the two could disagree. Carry step 1's.

`call_shape` is a set, one value per call: `condition_met`, `user_utterance`, `every_turn`. It is
empty where the label calls nothing, and that emptiness is not a missing answer — the no-call
sample is counted as `number_label_tools: 0`. The page should not require a tick where the label is
empty.

`domain` is four values and the list is the profile's. § *Open* records that closed-versus-open is
a decision about how the labelling team works, not about the code; until it is taken, the page
offers the four and the store does not validate the string.

**Approach.** Ticks in step 7's rectangle, beside the verdict radios — that is where the human
already is, and a second form at the end would be a second place to describe one sample.
`app.js` carries them into the record under a `class` key holding the declared half only.

**Acceptance criteria.** Every declared facet is tickable at step 7 and lands in the posted body.
`language` is not asked twice and matches step 1. A label calling nothing needs no `call_shape`
tick. A stored row's `class` holds the declared half as ticked and the derived half as computed,
and no facet appears in both halves.

**Source.** § *`class`* — the declared list, and `call_shape` is declared because a flat sample
cannot prove it; § *The page*.

**Verify.** `make check`; serve the app, tick every facet, approve, and read the row back.

**Out of scope.** Validating `domain` against a list — § *Open*. A facet for what the right answer
is — § *What else to add*.

**Blocked by.** T9.

### T12 · `dataset` can be dropped and rebuilt

**Goal.** Deleting every `dataset` row and recomputing it from `record` gives the same table.

**Context.** § *`dataset`* says it is a projection and nothing writes to it except that
computation; § *Invariants* says dropping and rebuilding gives the same table. Nothing proves it
until something does it. This is also the recovery path for every later change to a derived facet:
the old rows are not migrated, they are recomputed.

**Approach.** The rebuild is the same function T7 already calls, over every `record` row. A tested
function and not a route: nothing has asked to trigger one over HTTP, and `T-1` says build for the
case that exists.

**Acceptance criteria.** Over a fixture holding sellable and withheld records: delete every
`dataset` row, rebuild, and the table equals what it held — same keys, same `class`, same
`created_time`. A record whose outcome changed between writes rebuilds to the current answer, not
the old one.

**Source.** § *`dataset`*; § *Invariants*.

**Verify.** `uv run pytest tests/store -q`; `make check`.

**Blocked by.** T10, T11.

---

## Phase 3 · The figures answer

**Goal.** `GET /text2text/tool-decision/records/stats` answers every figure in § *The figures*,
each with the denominator it came out of, and none of them stored.

### T13 · The counts over `dataset`, and the empty cells

**Goal.** The route answers, and the coverage matrix shows which cells are empty.

**Context.** § *The figures* is explicit that every figure carries its denominator: a share over
nine rows and a share over nine thousand are different claims, so the answer carries pairs and not
percentages.

The matrix is the point of `class`, and **the finding is the zeros** — a cell with no rows has to
appear in the answer, which means the answer is built from the product of the facet's declared
values and not from what `GROUP BY` happens to return. A group-by alone cannot report a cell that
has never been written.

The no-call share falls out of the same counts and is named on its own: BFCL's irrelevance
detection is a first-class metric, and a corpus with no such rows scores it at zero by
construction.

Tool coverage reads `input.tools` and `label` rather than a facet, and § *The figures* says so
explicitly — a figure that silently needs a facet nobody keeps is a figure that breaks in a year.

**Approach.** `services/tool_decision/figures.py` composing the answer from counts the adapter
hands it. The counts are Core queries over `dataset`; the JSON facets are read in Python, because a
JSON path expression is where the two dialects stop being one adapter.

**Acceptance criteria.** Over a fixture of known rows: totals, the sellable gap split by why, the
7- and 30-day counts, the newest and oldest `modified_time`, counts per facet, the
`domain` × `call_shape` cross with every empty cell present and zero, the named no-call share, the
schema-validity share, and tool coverage with a count per called tool. Every figure is a pair. The
route answers with no rows in either table. Nothing is written by the request.

**Source.** § *The figures* — how much, how fresh, how much is sellable; the coverage matrix;
schema validity; tool coverage.

**Verify.** `uv run pytest tests/edge tests/services -q`; `make check`.

**Out of scope.** The three figures that read `record` (T14). Any caching — no figure is stored.

**Blocked by.** T12.

### T14 · What the evidence buys, and what is not measured

**Goal.** The three figures that only `record` can answer, the two duplicate figures, and the one
the answer says it does not measure.

**Context.** `human_edit_rate`, `panel_disagreement` and `redaction_outcomes` read three named keys
out of `record.document`. § *Design* names this as the seam: three keys read in Python over the
rows, and the day a fourth is wanted, that is the argument for a fourth column in `dataset` rather
than for a path expression into `record`.

`panel_disagreement` is the mean `llm.label_agreement` plus the share with `consensus: null`. It is
also where § *Open*'s `null`-versus-`[]` mismatch shows up as a number: a panel that agreed on *no
tool call* can read 0.0 and land here as a disagreement that did not happen. The figure is
computed as specified; the mismatch is named in the answer's own words rather than silently
absorbed.

The duplicate figures group by the same input. § *Design* takes the Python scan over a stored
digest, because the figure is identical either way and the digest is the change to make when the
scan stops being instant. Name that in the docstring so the next person does not re-derive it.

Inter-annotator agreement is **not measured** and the answer says so. Krippendorff's α needs two
people on one sample and this flow puts one human in front of each record; the panel proxies are
not it and must not be drawn as it.

**Acceptance criteria.** The three evidence figures are right over a fixture with known edits,
votes and outcomes. `duplicate_content_same_label` and `duplicate_content_diff_label` use the names
`DuplicateGroups` already uses. The answer carries an explicit *not measured* for agreement, with
the reason. A corpus of one row does not divide by zero anywhere.

**Source.** § *The figures* — what the evidence buys, the same input twice, what is not shown.

**Verify.** `uv run pytest tests/services -q`; `make check`.

**Out of scope.** Computing α. `DuplicateDataChecking.duplicate_groups`, whose shape is still
undeclared — § *Out of Scope*.

**Blocked by.** T13.

---

## Phase 4 · The page is a deck

**Goal.** `ui/` shows one card at a time, the first card is the labelling guide, and the figures
are under it.

**What this phase is not.** It is not the drawing. `edge/static/index.html` stays what it is — the
flow explained, for whoever is building it — and nothing in it is generated from `ui/` or the other
way round. No test drives either page; a browser is the check, and each task below says what to
look at.

### T15 · One card at a time, and a bar that moves between them

**Goal.** The page shows one step, and one bar under it moves the reviewer between all of them.

**Context.** `ui/index.html` is nine sections stacked — eight steps and the fan row holding 2, 3
and 4 side by side — with `.arrow` dividers between them. `app.js` already holds every piece of
state a rail needs: `held.asked`, the `.state` badge per step written by `mark()`, and
`held.returned` for the **back to** marking.

Two things are easy to get wrong. `←` and `→` inside a textarea move the caret, and the page has
four of them — so the key handler must do nothing while the focus is in a field. And the rail must
not become a second way of saying what **back to** says: a jump means only *show me that card*,
while **back to** drops the record and leaves an instruction.

**Approach.** The nine sections stay in the markup and only one is shown. One bar under the card
holds `<`, the rail and `>`. The rail's eight markings carry the state badge each step already
paints, so `mark()` gains one line rather than the rail gaining a copy of the state. The fan is
drawn on the rail by grouping 2, 3 and 4.

The frame has a floor and no ceiling: a short card does not collapse it and a tall card scrolls
inside it, so the bar is in the same place on every card. One slide in the direction of travel, and
none of it under `prefers-reduced-motion`.

**Acceptance criteria.** One card is visible. `<` and `>` move one card and stop at the ends; the
rail jumps anywhere, in any order, whatever has answered. `←` and `→` move a card, and do not while
the caret is in a textarea or an input. Every step's state is readable from the rail without moving.
**back to** still drops the record, still marks the card it lands on, and now also shows it. A
refusal shown on a card the reviewer has flipped away from is still there when they come back.

**Source.** § *The page* — one card at a time; the deck is not a wizard; the rail; a jump is not a
**back to**; § *Design* — why a deck, the frame's height, motion.

**Verify.** `make check`; serve the app and check at 1440px and at 390px: flip through every card
with each of the three controls, type an arrow key inside every textarea, and confirm the bar does
not move.

**Out of scope.** The guide card (T16) and the figures (T17).

**Blocked by.** T9.

### T16 · The first card is the guide, and the header is a title

**Goal.** A labeller opens the page and reads how to label, not how the page is built.

**Context.** The header today is five sentences of architecture: every rectangle is one call, the
yellow cells are yours to edit, what `config/model/` holds, that nothing stores the record. It is
accurate and it is written for whoever is building the flow. The split it breaks is already a rule
— the drawing explains, `ui/` labels — so this is not a new principle, it is the page catching up
with one.

Each card's own note is the same question at a smaller scale: step 6's note explains that no
data-quality answer is an argument to the review, which is a design rationale, not an instruction.

**Approach.** A guide card before step 1. It says what a `tool_decision` sample is, what makes a
label right — including that *no tool call is needed* is an answer and not a skipped row — what to
tick at the two human steps and what each declared facet means, and what gets a sample refused. No
route name, no file path, no sentence about wiring. The header keeps the title. Each card's note is
rewritten to what to do there; the rationale that leaves has a home in the drawing.

**Acceptance criteria.** No route path, file path or module name appears in the guide or in any
card's note. The guide names every declared facet a labeller has to tick. The legend of states
stays wherever it is still read. Nothing in the drawing changed.

**Source.** § *The page* — the first card is the labelling guide; the guide says what to do and the
drawing says why.

**Verify.** `make check`; serve the app and read the guide card start to finish as somebody who has
never seen the flow. `grep -n "/text2text\|config/model\|\.py" src/dataforce/ui/index.html` returns
nothing from the guide or the notes.

**Out of scope.** Which language the guide is written in — § *Open*, and it decides the whole
card's copy. Settle it before writing the prose rather than translating afterwards.

**Blocked by.** T15.

### T17 · The strip, and the figures under the guide

**Goal.** Three numbers follow the reviewer from card to card, and the whole of § *The figures* is
under the guide.

**Context.** The strip is read sideways while the reviewer is working on something else, which is
why it is three items and why the third is the one that changes what they do next: sellable out of
reviewed, rows in the last 7 days, and how many cells of the coverage matrix are still empty.
*Which* cells is the guide card's to show.

The page must work with no database attached — that is not an error state, it is a deployment
without a store — so the strip says so in the service's own words and the eight steps are
untouched.

**Approach.** The strip in the header beside the title. The figures under the guide on the first
card, with the coverage matrix drawn so an empty cell is visible as an empty cell rather than as an
absent row. Asked for on load and again after a record is written — not on a timer, and not on
every flip.

**Acceptance criteria.** The strip is on every card and never moves. With no database attached it
says so and all eight steps work. After **approve**, the figures change without a reload. The
matrix shows every cell, including the zeros. Agreement is shown as *not measured*, with the
reason, rather than left out.

**Source.** § *The page* — the figures sit on the guide card; a strip stays on every card; asked for
on load and after a write; § *The figures* — what is not shown, and is said so on the page.

**Verify.** `make check`; serve the app with and without a DSN, approve a record and watch the
numbers move.

**Out of scope.** Any figure the store does not already answer.

**Blocked by.** T14, T16.

---

## What this plan asks of the spec

Two sentences in `spec.md` are less true after this plan than before it, and both are the spec's to
change rather than a task's to work around.

- **The record is thirteen keys, not twelve.** § *`record`* lists the document's keys, and the
  declared half of `class` has to be one of them — it is what the human answered at step 7, and
  there is nowhere else for it to arrive. T11 is where it starts mattering.
- **Logic is not handed a store.** § *Context* says a service is handed the store as an argument.
  With the decisions pure and the writing in the adapter, nothing below the edge takes one. The
  rule the sentence is enforcing (`H-8`'s fourth column) holds either way; the mechanism it names
  is not the one this plan uses.

## Open in the spec, and what each task does while it stands

| Open | Who needs it | What happens until it is answered |
|---|---|---|
| `(task, id)` or `id` alone as the key | T2, T7 | Composite, as § *`record`* states. Changing it later is a migration and a rewrite of both writes |
| The `domain` list, closed or open | T11 | The page offers the four; the store stores the string and validates nothing |
| `industry` as a second axis | T10, T13 | Not built. It is a facet or a column or neither, and building it now would be guessing which |
| What a `null` label means | T10, T14 | Counted as zero calls either way; not folded. The panel's agreement figure carries the mismatch rather than hiding it |
| The language of the guide card | T16 | Blocks T16's copy, not its structure. Settle it before writing the prose |
| The status for *no database attached* | T8 | This plan takes 503 with the variable named, and says so in one place |
