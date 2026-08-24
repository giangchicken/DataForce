# Build plan

Tasks for building what `spec.md` specifies. Read that first; this document schedules it and does
not restate it. Where the two disagree, the spec wins and this file is wrong.

**Source:** `docs/annotation-pipeline/spec.md` @ `9b9a3fe`, `AGENTS.md` §1–§9 and P0–P31 @ `a61f8cb`,
`docs/annotation-pipeline/objective.md`.

**State at the time of writing.** `src/` and `tests/` did not exist — both were deleted deliberately so
the rebuild has one answer to every question. `make check` was therefore red: it runs
`mypy --strict src/dataforce` and pytest against nothing. `config/` holds two axis manifests and one
prompt. Four things in the tree contradicted the spec; they were Phase 0 rather than discoveries made
in Phase 4.

**Phase 1 is done. Phase 0 has one task left, and Phase 2 has started.** Phase 0: T1 (`2c41599`),
T2 (`a2fc1df`), T3 (`9b9a3fe`), T4 (`7fa0432`, `f7f30f4`, `89292ce`), T32 and T33. Phase 1: T5
(`64edb99`), T7 (`b1c49b6`), T6 (`c72e5a6`), then a review round — T35, T36, T37 and T38. Phase 2: T8.
Phase 3: T11, taken early because `Engine` names both protocols.
`make check` is green over 55 modules and 313 tests, 21 of which are the first in the tree that are not
guards — but **T34 is open and CI is red on a line neither `make check` nor any guard reads.** What
each task changed is recorded at the end of the task below it. **T9 is next.**

**Scope.** Every stage of `load_data`, `data_quality`, `ai_review` and `human_review`, and both
shells. The `release` phase — `split`, `export`, `datasheet` — is declared in the flow so
`record.release` has an owner and is specified in a follow-up. Nothing here may assume its shape.

**Assumption:** no corpus is declared, and none is needed until Phase 8. The engine is source-agnostic
by design, every fixture is invented (AGENTS.md §9), and `params.source.*` stays empty until someone
declares one. Only the Smoke and Pilot rungs block on it, and both say so.

---

## How to read this

**One task is one commit.** Each is sized for one session with no prior context: read the task, read
what its *Source* points at, do it, run its *Verify*, commit.

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

Tasks in Phases 4–6 take their *Approach* from § *Shared decisions*, and state one only where they
depart from it.

**Every short reference resolves somewhere.**

| Written | Lives in |
|---|---|
| `Requirement 47` | `spec.md` § *Requirements* — 52 of them |
| `I8` | `spec.md` § *Invariants* — I1 to I19 |
| `Decision 12` | `spec.md` § *Decisions* — 22 of them |
| `pii_check` | a stage: one row of `spec.md` § *The flow*. Stages are named, never numbered — Decision 19 |
| `P27` | `AGENTS.md` § *Design Principles* — P0 to P31 |
| `§6` | a numbered section of `AGENTS.md` § *Conventions* |
| `T16` | a task in this file. The number is its name, not its place in the order — inserting T32 renumbered nothing |

---

## Phases

| # | Phase | Goal — the outcome that ends it |
|---|---|---|
| 0 | The document and the repository agree | Nothing in the tree contradicts `spec.md`, and the four standing principle conflicts are fixed or accepted in writing |
| 1 | A guard fails before there is anything to guard | `make check` is green over an empty engine, and every architectural rule is a red test first |
| 2 | The shared vocabulary exists | A record can be constructed, typed and hashed. Nothing runs |
| 3 | Both axes answer their contracts | `text2text` and `tool_decision` resolve from config and satisfy their protocols |
| 4 | One record makes the round trip | `load_data` and all of `data_quality` run in process over invented fixtures |
| 5 | The panel scores a record | All of `ai_review` runs against a stubbed panel |
| 6 | The loop through people closes | A question reaches a store, an answer comes back, a label is curated |
| 7 | Two shells, one implementation | HTTP and an in-process caller produce the same record |
| 8 | The rungs | Provisional thresholds become measured ones |

Phases 1–3 are strictly sequential, with one exception found while building and recorded at T11:
`Engine` names both protocols in its own fields, so T11 came before T9. Phases 4–6 are sequential in
the flow but each stage task inside them is independent once its upstream key exists. Phase 7 can
start as soon as Phase 4 lands.

---

## The tasks

**Needs** is what must land before this task can start; blank means *as soon as the phase opens*.
**Size** is a shape, not an estimate — **S** one module and its test · **M** several modules, or one
algorithm to get right · **L** more than one sitting, so split it if it grows while you work.

| # | Task | Phase | Needs | Size | Landed |
|---|---|---|---|---|---|
| T1 | Correct the answer type, and the three operations over it | 0 | | M | ✓ `2c41599` |
| T2 | Assign the three unowned responsibilities | 0 | | M | ✓ `a2fc1df` |
| T3 | Settle the four standing principle conflicts | 0 | | M | ✓ `9b9a3fe` |
| T4 | Clear the retired-corpus residue and the stale scaffolding | 0 | | S | ✓ `89292ce` |
| T32 | Un-number the stages | 0 | T5 | M | ✓ |
| T33 | Write down the layout, and guard it | 0 | T5 | M | ✓ |
| T34 | The CI workflow runs what `make check` runs | 0 | T4 | S | |
| T35 | The axis façade, and the guard that could not see through it | 1 | T6 | M | ✓ |
| T36 | One shared request body, and `cli.py` inside `edge/` | 1 | T5 | M | ✓ |
| T37 | Give the event stream an owner | 1 | T5 | S | ✓ |
| T38 | Why `publish` and `annotator_answers` are two | 1 | T5 | S | ✓ |
| T5 | The package skeleton and the import direction | 1 | | M | ✓ `64edb99` |
| T7 | The flow-table drift test | 1 | T3, T5 | S | ✓ `b1c49b6` |
| T6 | The guards | 1 | T5, T7 | L | ✓ `c72e5a6` |
| T8 | `errors.py`, `record.py`, `manifest.py` | 2 | T5 | M | ✓ |
| T9 | `engine.py`, `ports.py`, and the registry | 2 | T3, T8 | M | |
| T10 | `pipeline/flow.py` and `pipeline/runner.py` | 2 | T9 | S | |
| T11 | The two protocols | 3 | T8 | S | ✓ |
| T12 | `text2text` | 3 | T4, T11 | M | |
| T13 | `tool_decision` | 3 | T1, T11 | L | |
| T14 | `load_data` | 4 | T10, T12, T13 | M | |
| T15 | `label_check` | 4 | T13, T14 | S | |
| T16 | `pii_check` | 4 | T2, T14 | L | |
| T17 | `duplicate_check` | 4 | T12, T14 | M | |
| T18 | The bus and conservation properties | 4 | T14–T17 | S | |
| T19 | `jury` | 5 | T2, T13, T15 | M | |
| T20 | `cohesion` | 5 | T19 | S | |
| T21 | `triage` | 5 | T20 | S | |
| T22 | `question_generate` | 6 | T21 | M | |
| T23 | The question store | 6 | T3, T9 | M | |
| T24 | `publish` and `annotator_answers` | 6 | T2, T22, T23 | M | |
| T25 | `aggregate` and `curate` | 6 | T24 | M | |
| T26 | The Label Studio sync | 6 | T23 | M | |
| T27 | The edge | 7 | T9, T12, T13 | M | |
| T28 | The routers | 7 | T10, T27 | M | |
| T29 | The CLI and the event stream | 7 | T3, T27 | M | |
| T30 | Smoke | 8 | T29 · **a declared corpus** | M | |
| T31 | Pilot | 8 | T30 · **a corpus, the transfer review, the glossary** | L | |

The four **L** tasks are where a plan usually goes wrong. T6 is nine guards each proved against a
synthetic violation; T13 is fourteen members of which four are real algorithms; T16 is two detection
layers over a language most scrubbers do not cover; T31 is a measurement campaign, not code.

---

## Phase 0 · The document and the repository agree

**Goal:** nothing in the tree contradicts `spec.md`, and the four standing principle conflicts are
fixed or accepted in writing.

Doing this first is the whole point of a spec-driven rebuild. Every item below is a place where an
agent reading the spec would write code the repository then contradicts.

**Status: all four have landed.** Each task keeps its original text so the reason it existed stays
legible, and closes with what actually changed — including where the task turned out to be
under-scoped, which two of them were.

### T1 · Correct the answer type, and the three operations over it

**Goal.** `spec.md` states what a `tool_decision` answer is, and the three profile members that
operate on one match it.

**Context.** The spec's `Profile` protocol implies an answer is a set of names — `answer_distance`
is documented as "0.0 identical, 1.0 unrelated" with no mention of arguments, and
`vote_consensus(votes)` takes no record. A prior iteration of this project settled this differently,
with measurements, and the reasoning is recoverable: commit `1bdc63f` *"C2: the answer is calls with
arguments, and no record stores a space"* and `d368afd` *"C3: δ is soft and consensus is per
argument"*. An answer is a set of **calls** — a name *and* its arguments — because `SendStatement`
alone cannot distinguish `ky: "thang_nay"` from `ky: "thang_truoc"`.

**Source.** `spec.md` § *Profile*, § *Per-service contracts*, § *Decisions*.
`git show 1bdc63f`, `git show d368afd`.

**Approach.** Six changes, one commit:

1. The answer is a set of calls; the empty answer is first-class, not a missing value.
2. At most one call per tool name. Two calls to one tool make the answer a multiset and force δ to
   pairwise-match them silently; `label_names_one_tool_twice` quarantines instead.
3. `answer_schema` emits `oneOf` per offered tool — the name a single-value `const`, the arguments
   that tool's own `parameters`. Together, because `OpenTicket` carrying `LookupBalance`'s argument
   is two valid halves and one invalid call. Empty catalog → `maxItems: 0`.
4. δ is name-first and soft: over the union of names, a name in both contributes the share of
   argument keys present in both and equal, a name in one contributes zero, δ is one minus the mean.
   `δ(∅, ∅) = 0` by definition. It reduces exactly to `1 − |A∩B| / |A∪B|` when every matched call has
   identical arguments, so every number measured before arguments existed still describes it.
5. `vote_consensus(votes, record)` — the record is a parameter because a call missing a `required`
   argument is dropped rather than completed, and `required` is the tool's own declaration.
6. A bare name string reads as the call with no arguments, which is what makes a names-only source a
   special case of this type rather than a second type.

Add a Decision recording the answer type and citing both commits, so this is not re-derived a third
time.

**Acceptance criteria.**
- Reading only `spec.md`, an implementer can tell that an answer carries arguments and that δ is not
  Jaccard.
- The worked ordering appears in the spec: `δ(same call) = 0 < δ(same tool, one of two arguments
  differs) = 0.5 < δ(different tools) = 1`.
- `vote_consensus` takes the record, and the spec says why.
- The ambiguity is either resolved or recorded: dropping every call yields `[]`, which is the same
  value as a panel agreeing on the empty answer. Two different facts, one representation. P22 says
  fix the type rather than the branch.

**Verify.** `grep -n "Jaccard\|set of names" docs/annotation-pipeline/spec.md` returns nothing that
still claims the old shape; the flow table still parses (15 contiguous rows, 5 phases).

**Out of scope.** Implementing any of it. This task edits one document.

**Landed — `2c41599`.** All six, plus Decision 15 citing both commits. The `[]`-versus-`None`
ambiguity is closed by construction rather than documented: a majority-empty check runs first, so `[]`
is returned only when a majority voted for it. § *The answer, and the three operations over it* is
where the type now lives.

---

### T2 · Assign the three unowned responsibilities

**Goal.** Every stage in the flow has an owner for every piece of work it does.

**Context.** Three stages cannot be built as specified because nobody owns a required piece.

**Approach.**

1. **`annotator_answers` has no parser.** `build_record` is declared "the only place a source shape
   is read", but `annotator_answers` reads a second external shape — whatever the annotation tool
   hands back. The profile defined the capture half that produced it. Add
   `answer_from_response(payload) -> Answer`, the inverse of `answer_config`. Without it the parse gets invented in the store adapter, where no
   test of the answer space can see it.
2. **`pii_check` rewrites content and leaves the label behind.** A worked case: content reads
   `Mã của mình là 480215.` and the label carries `arguments: {"ma_khach": "480215"}`. `pii_check`
   replaces the content with `<CUSTOMER_ID_1>` and bumps `content_version`; nothing rewrites the
   label. Two results — `label_assistant_mismatch` starts failing on a false positive an earlier
   stage manufactured, and `export` emits a training example whose input says `<CUSTOMER_ID_1>` and
   whose target says `480215`, teaching a model to produce a customer id absent from its input. That
   is a data-poisoning bug wearing a privacy bug's clothes. Add
   `redact_label(label, replacements) -> Label`, or state that labels never quote content. The
   spec's own record example already shows `"ma_khach": "<CUSTOMER_ID_1>"`, so it depicts the
   redacted label and assigns no stage to produce it.
3. **Nothing states the task to a model.** `question_text` is explicitly human-facing — "in their
   language, no model output may appear in it". The jury panel needs its own statement, and today it
   lives in a policy template with no declared slots. Decide: the profile fills the template
   (`jury_slots(record)`), or policy owns the string and the profile owns only the schema. Both work;
   `jury` cannot be built until one is chosen.

**Acceptance criteria.** Each of `pii_check`, `jury` and `annotator_answers` has, in its row of
§ *Per-service contracts*, a named owner for the piece that was missing. The `Profile` member count
in the spec matches the members listed.

**Source.** `spec.md` § *Per-service contracts*; the record example under § *The record*.

**Verify.** For each of the three, the spec answers "which module produces this?" in one sentence.

**Out of scope.** The PII detector patterns themselves — those are T16.

**Landed — `a2fc1df`,** and it grew. `answer_from_response` and `jury_slots` are profile members
(Profile is now fourteen, not twelve); `redact_label` is written into Requirement 17 with the
data-poisoning reasoning, because that is where the next reader hits it; policy owns the jury template
and the profile owns the slots, so a prompt change reaches the run manifest.

Naming `annotator_answers`'s parser forced the question the task had not asked: *what shape,
exactly?* Read against the Label Studio server source, two of its properties change what gets built.
`<Chat>` renders a conversation the way `text2text` wants and is **Enterprise-only**, so the
community display half is `<Paragraphs layout="dialogue">`. And a project has **one config for every
task** while our catalog is per record, so the tool list must be a dynamic choice list read from
task data — objects, not strings. § *The annotation config, and what comes back* now specifies the
config, the task payload and the `result` list, with Requirements 49–52 and I18 behind them. The
cost is recorded there too: a set of calls with typed arguments has no community widget, so an
annotator types JSON.

---

### T3 · Settle the four standing principle conflicts

**Goal.** Every P0–P31 principle either holds against the spec or is recorded as a knowing exception
with a reason.

**Context.** An audit of all 32 principles against the spec leaves four conflicts. Four earlier ones
dissolved when `AGENTS.md` was rewritten at `a61f8cb` — the `utils.py` exemption now stands
explicitly, naming stays with §5, and P21's check (*no non-HTTP entry point imports from the HTTP
package*) is satisfied by a flat `edge/`, which is not named for the HTTP layer.

**Approach.**

| Principle | Conflict | Resolution |
|---|---|---|
| **P20** | *A port with zero adapters is deleted.* `MediaResolver` has none — no media modality is built. | Delete the port. Keep the *Out of Scope* entry describing the seam; the modality protocol and the media part shape are the seam. |
| **P26** | *Dev and production run the same implementations.* SQLite stands in for Postgres and a stubbed panel for the jury, and Decision 7 waves the first through on "the schema is small enough that the two behave identically" — the exact assumption P26 refuses. | Declare an `-m integration` suite against Postgres, and rewrite Decision 7 to carry the difference as a known risk rather than an argument. |
| **P27** | *Logs are an event stream, observability built in from the start.* The spec contains no logging at all — every match for "log" in it is a substring of `catalog` or `LOGIC`. A 20,000-record run is unobservable until it finishes. | Add a § *Observability*: each stage returns what happened, the edge writes it, every event carries `run_id`, `record_id` and stage. Logging is I/O, so it stays outside under P17. Implementation is T29. |
| **P31** | *A document fact the code also states is compared by a test.* Nothing compares the flow table to the code. | Declare the guard. Implementation is T7. |

Two further principles from the rewrite need a line each. **P1** — *do not decompose along the flow of
processing* — is aimed squarely at `pipeline/`, which is fifteen step modules in flow order.
`AGENTS.md`'s own conflicts section resolves it (*step modules stand, but a decision spanning steps is
extracted under P2 and the steps call it*); the spec should record that resolution and name the one
such decision it already has: the answer type, which `jury`, `cohesion`, `aggregate` and `curate` all
reason about. **P22** —
*define errors out of existence* — lands on the `[]`-versus-`None` ambiguity in T1.

**Acceptance criteria.** All 32 principles hold, or the exception is written in the spec with its
reason. No conflict is resolved silently (§8).

**Source.** `AGENTS.md` § *Design Principles* and § *Conflicts, written down*; `spec.md` § *Invariants*,
§ *Decisions*.

**Verify.** Walk P0–P31 against the spec and produce the verdict table. Every `conflict` row has a
spec line resolving it.

**Landed — `9b9a3fe`,** as Decision 17. P20: the port is deleted, and the seam survives in the protocol,
the media part shape and Requirement 16. P26: Decision 7 rewritten to carry the difference as a risk —
the sync's idempotency rests on two unique constraints, which is exactly where SQLite and Postgres
differ — and the store tests now run under both. P27: § *Observability*, with levels specified so the
stream stays readable and I1 told to permit `logging` by name. P31: I3 now parses the flow table out of
`spec.md` itself rather than comparing code to code. P1 and P22 got the line each they needed.

---

### T4 · Clear the retired-corpus residue and the stale scaffolding

**Goal.** Nothing in the tree still describes `fc_train_final`, gates, or the pre-`edge/` layout.

**Context.** The spec says these are cleared. They are not.

**Approach.** Six deletions and renames, one commit:

| Path | State | Action |
|---|---|---|
| `metrics/corpus_profile.json` | **Done.** It was tracked, and it fingerprinted the retired corpus — record count, SHA-256, distinct tool names, and the tool names themselves — in a public repo. | Deleted. |
| `params.yaml` | `source.path`/`source.sha256` point at the retired corpus; `invalid_counts`, `gold.records: 951` and `max_answer_cardinality: 3` are measured from it. | Empty `source`, re-key `invalid_counts` to the five label-check names with no values, drop `gold` and `max_answer_cardinality` until a corpus is declared. |
| `config/modalities/text.yaml` | Identity is `text`; the spec's pair is `text2text`, and the filename *is* the identity. | Rename to `text2text.yaml`, `name: text2text`. The rename is the change. |
| `dvc.yaml` | `stages: {}` under a comment naming `load`, `remove_invalid`, `rank_for_review`, `document` and an obsolete phase numbering — and behind it a whole toolchain: a `dvc` runtime dependency nothing imports, a mypy override for it, `make repro` over an empty DAG, `.dvc/` and `.dvcignore`. | Deleted, with `pandera` and `pandas`, which had no job either. |
| `pyproject.toml` | `description` reads "Gated DVC stages…" — gates were deleted in `fa32ec1`. The `jsonschema` dev-dep comment cites `test_no_reimplementation.py` and "the core spec", both gone. | Rewrite both. |
| `docs/annotation-pipeline/workflow.md` | Step 4 of its build order names `api/policy.py` and `api/engine.py`, renamed to `edge/` in `6a091df`. | Reconcile with this plan, or reduce it to the diagrams and point at this file for order. |

`data/raw/`'s symlinks target an absolute internal path but are covered by `.gitignore`, so they are
not in the repository. Leave them.

**Source.** `spec.md` § *Context* — where the corpus retirement is recorded; `AGENTS.md` §9.

**Acceptance criteria.** `grep -ri "fc_train_final\|corpus_profile" .` returns hits only in
`spec.md`'s § *Context*, where the retirement is recorded on purpose. No tracked file names a stage
that does not exist in the flow table.

**Verify.** `git ls-files | xargs grep -l "fc_train_final"` is empty. `make check` is unchanged
(still red for the missing `src/` — that is Phase 1).

**Landed — `7fa0432`, `f7f30f4`, `89292ce`,** and it was the most under-scoped task in the plan.

Two rows were bigger than they read. *`dvc.yaml`* was not a stale comment but a vestigial toolchain, and
checking the rest of the dependency list for the same shape found two more: `pandera` and `pandas`
appeared in the spec only as a *Versions* row marked "unchanged", which is how a dependency avoids ever
being asked to justify itself. Removing three direct dependencies removed **76 packages** from the lock
— a task queue, three git implementations, a config framework, a crypto stack. Decision 18.

And two contradictions were hiding under "rename the manifest". `answer_control` read
`per_name_arguments`, which `a2fc1df` had contradicted three commits earlier: a Label Studio project
holds one config for every task while our catalog is per record, so per-tool argument fields cannot be
expressed. It is `names_and_json_arguments`. `shape` read `legacy_system_prompt` — the retired corpus's
shape — against Requirement 13, which declares one input shape and forbids parsing a catalog out of
prose; left standing, this profile read a declared-input record as an empty catalog.

`exclude_roles: [system]` is kept and its justification is not: the measurement behind it was taken on a
corpus where the catalog *was* the system turn. Marked provisional, with what would re-measure it.

`deploy/` still holds only a `.gitkeep`, and § *Versions* no longer claims otherwise — the compose file
arrives with T26, the first task that needs an instance.

---

### T32 · Un-number the stages

**Goal.** No stage has a number, anywhere.

**Context.** The flow table numbered its rows 0–14, every `STEP ·` docstring repeated its number, four
contract tables carried an index column, `workflow.md` numbered its diagram nodes and its headings, and
scope was written as *stages 0–11*. None of that is a property of a stage — it is a position in a list,
and `STAGES` is a tuple that already holds it. It is also a **shared** index: inserting one stage into
`human_review` renumbers every stage after it, so a one-row change becomes a diff across `flow.py`, five
docstrings, eight tables, three documents and the drift guard — and every one of those files goes red
having done nothing wrong. The cost lands on the day someone is inserting a stage, which is the day they
should be thinking about the stage instead.

**Approach.** Drop `Stage.number`. Replace `LAST_IN_SCOPE_STAGE = 11` with `DECLARED_ONLY`, the phases
that are in the flow and have no module — a named phase does not move when something above it does.
Requirement 3 becomes `STEP · <stage> · <what the table says>`. In prose, name the stage —
`question_generate`, not *stage 7*.

**Acceptance criteria.** Nothing in `spec.md`, `plan.md` or `workflow.md` numbers a stage, and I3 still
fails when either side of the table moves alone — including when a row only moves *position*, which the
number used to catch for free.

**Source.** `spec.md` Decision 19, Requirement 3, I3; AGENTS.md P16, P31.

**Verify.** `grep -in "stage [0-9]" docs/annotation-pipeline/*.md` is empty. `make check` green.

**Landed.** Nine mutations, nine reds: a summary reworded in the table, two rows swapped in `flow.py`, a
table row deleted, a stage module renamed on disk, `DECLARED_ONLY` emptied, `DECLARED_ONLY` naming a
phase that is not in the flow at all, the scope sentence deleted, a `STEP ·` docstring reworded, and a
`STEP ·` docstring given its number back.

Removing the number removed the thing that had made the row comparison order-insensitive, so I3 now
compares list against list rather than set against set. That is the one job the number did that had to be
rebuilt rather than dropped, and it is the argument against the cheaper version of this change — deleting
the column and leaving the comparison keyed on stage name would have silently stopped checking order.

`workflow.md`'s mermaid node ids were `S0`–`S14`, which is the same index in a third place; they are the
stage names now. Its four contract tables lost the same column `spec.md`'s did. Full reconciliation of
that document against this plan is still T4 residue and still open.

---

### T33 · Write down the layout, and guard it

**Goal.** Every file and folder in the repository has a stated job, and the statement cannot go stale.

**Context.** § *Package layout* drew the package at directory granularity — `data_quality/  STEP modules:
label_check.py, pii_check.py, duplicate_check.py` — and said nothing at all about the repository root.
`config/`, `params.yaml`, `data/`'s five tiers and `deploy/` each had a job and none of them had it
written down anywhere a person looks first. A layout drawn once and never checked is worse than none: it
reads as current.

**Approach.** Add § *Repository layout*, one row per entry at the root. Redraw § *Package layout* module
by module, where each line **is** that module's own docstring rather than a second description of it —
two summaries of one module drift the moment either is edited, and the drift is silent because both
still read fine. Then guard it, or the drawing is a lie generator: I19 parses the tree out of the
document and compares it to the package in both directions.

**Acceptance criteria.** Every module has a row and every row has a module, and the build fails when
either stops being true — including when only the *text* of a row drifts from its docstring.

**Source.** `spec.md` § *Repository layout*, § *Package layout*, I19; AGENTS.md P31, P29.

**Verify.** `uv run pytest tests/guards/test_layout_tree.py -q`, then add a module with no row and
confirm red.

**Landed.** Three mutations, three reds: a module with no row, a row with no module, and a row reworded
on one side only. A fourth check earns its place the other way — the guard is proved to *permit* the two
mediums spelling the same thing differently, since a docstring writes ` ``content`` ` and `--` where the
document writes `` `content` `` and an em dash. Without that, the first correctly-written row would have
failed and the normalisation would have been loosened under pressure.

Writing § *Repository layout* found two entries with no owner. `deploy/` has one — T26 puts the compose
file there, and § *Versions* says so — so it is recorded as a placeholder with a name on it.
`config/templates/` has none: nothing in any document references it, which makes it the empty directory
AGENTS.md §2 forbids. It is named in the table so the next task touching `config/` deletes it. And the
`.github/workflows/ci.yml` row could not be written truthfully, which is T34.

---

### T34 · The CI workflow runs what `make check` runs

**Goal.** CI passes on a tree where `make check` passes, and fails on one where it does not.

**Context.** `.github/workflows/ci.yml` is Phase 0 residue that T4's table never listed, so T4 closed
without it. Three steps are wrong.

1. `uv run dvc repro` — `f7f30f4` deleted DVC along with the dependency, the mypy override and the
   empty DAG.
2. `from dataforce.modalities.text import EMBEDDING_MODEL, _model` — `89292ce` renamed the manifest to
   `text2text`, and neither symbol exists until T12 in any case.
3. `make integration` runs in the same job as `make check`, on a public runner with no secrets. It
   wants a live panel, a real store and a Label Studio. `make check` exists precisely so that the
   commit gate needs none of those.

So CI has been red since Phase 0 while `make check` has been green locally since Phase 1, which is the
worst arrangement: the signal everyone reads is the one that is wrong.

**Approach.** Delete the `dvc repro` step: there is no DAG and no tool. The embedder cache is a
decision, not a rename — it pre-warms a sentence-transformer for `duplicate_check`, and the module it
warms does not exist until T12. Prefer dropping it and letting T17 add caching when it needs it: a
cache warm for code nobody has written is the flexibility AGENTS.md §2 forbids, and T17 is where the
need would actually be felt. Move `make integration` out of the commit gate into a job of its own,
gated on the secrets it needs, so a missing credential reads as *not run* rather than *failed*.

**Acceptance criteria.** The commit gate runs `make check` and nothing that names a deleted tool, an
unwritten module, or a service the runner has no credential for. A pushed commit that fails
`make check` fails CI, and one that passes passes.

**Source.** `Makefile`; `spec.md` § *Repository layout*, the `.github/workflows/ci.yml` row.

**Blocked by.** Nothing. It is open because T4 never listed the file.

**Verify.** `grep -c "dvc\|modalities\.text\b" .github/workflows/ci.yml` is 0. A pushed branch is
green.

**Out of scope.** Adding jobs — a matrix, coverage, a release step. This task makes the existing job
true, and no more.

---

## Phase 1 · A guard fails before there is anything to guard

**Goal:** `make check` is green over an empty engine, and every architectural rule is a red test
first.

P29: *write the guard before the code it constrains, and prove it fails.* Written after the services,
a guard only ratifies whatever was already done.

### T5 · The package skeleton and the import direction

**Goal.** `make check` passes over a package containing no behaviour.

**Context.** `src/dataforce/` does not exist. `make check` runs `ruff check`, `ruff format --check`,
`mypy --strict src/dataforce`, and `pytest -q -m "not integration"`.

**Approach.** Create the tree from `spec.md` § *Package layout* with every module present, each
carrying its docstring — first word `DEFINITION ·`, `LOGIC ·`, `STEP ·` or `TOOL ·` — and nothing
else. State the import direction in the top-level package docstring: *`edge/` and `cli.py` may import
the engine; the engine may not import them.* Create `tests/` with the five directories the spec
declares.

**Acceptance criteria.** `make check` is green. Importing `dataforce.modalities.text2text` and
`dataforce.profiles.tool_decision` from a directory holding no `config/` succeeds and writes nothing
(Requirement 37).

**Source.** `spec.md` § *Package layout*, Requirements 36–37.

**Verify.** `make check`; then `cd $(mktemp -d) && python -c "import dataforce.profiles.tool_decision"`.

**Out of scope.** Any function body.

**Landed — `64edb99`.** Fifty-seven modules: 15 `DEFINITION`, 12 `STEP`, 8 `TOOL`, 6 `LOGIC` — and 15
that are none of the four.

Requirement 2 names four kinds and none of them describes an `__init__.py` that re-exports and holds
nothing of its own. The spec's own § *Package layout* had already written a fifth, `façade ·`, over
`pipeline/__init__.py`, so §8 applies rather than bending one of the four: the break is now recorded
in Requirement 2 and in the top-level package docstring, which is also where the import direction is
stated once.

The half of I1 that needs no AST scan came with it — a subprocess importing both axes from a directory
with no `config/`, which is Requirement 37 as something a machine runs.

---

### T6 · The guards

**Goal.** Every architectural invariant is a test that has been observed to fail.

**Context.** Nine of the eighteen invariants are checkable before any service exists: I1 (engine opens
no file), I2 (`pipeline/` imports no concrete axis), I3 (names match the flow table), I4 (axis
implementation shape), I5 (identity never in a class body), I6 (nothing re-implements
`agent-toolkit`), I7 (every field described), I16 (no axis `base.py` imports its own
implementation), I17 (stage order exists once). I8 and I11 need services and are Phase 4.

**Approach.** One module per guard in `tests/guards/`, each an AST scan or model introspection.
Each is proved against a *synthetic* violation — a small source string the guard is run over — so it
is known to go red. P30: permit an annotated exemption naming a reason and an owner; keep the list
short and dated.

**Acceptance criteria.** Each guard has a companion assertion that it rejects a synthetic violation.
`make check` green. The `agent-toolkit` guard names all of `compute_hash`, `normalize_text`,
`slot_filling`, `extract_json_from_text`, `read_jsonlines`, `write_jsonlines`, `read_yaml`, and the
LLM client surface.

**Source.** `spec.md` § *Invariants*; AGENTS.md P28–P30.

**Verify.** `uv run pytest tests/guards -q`. Then temporarily add a violating import to a
`pipeline/` module and confirm I2 fails; revert.

**Out of scope.** I8, I11, I15 — they need running services.

**Landed — `c72e5a6`,** as eight guards rather than nine; I3 went with T7, which had to come first.

A synthetic violation proves the rule and not the wiring — a scan can reject a source string and still
be pointed at nothing — so each rule was *also* run against a real violation written into the real tree
and reverted. Twelve mutations, twelve reds.

Three rules needed their scope argued. **I5** flags only a *constant* assignment: a pydantic model
declaring `name: str` is a field, not a class claiming an identity, and a guard that could not tell them
apart would be switched off by the first model written. **I17** counts stages *called from one function*,
not named in a module — a `data_quality` router must mention three stages, one sub-endpoint each, so
counting mentions would forbid the routes the spec requires; the other half of I17, that a phase endpoint
reaches `run_phase`, has no handler to be asserted of yet and is left stated rather than pretended.
**I7** is vacuous over today's tree, which is the argument for writing it now rather than after
`record.py`.

I6's owned-name list is parsed out of the spec sentence that states it, not copied from it (P31).

P30's escape hatch arrived with the guards rather than after the first argument about one: a line names
an invariant, a reason, an owner and a date, and `test_exemptions.py` is the review. The list is empty.

---

### T7 · The flow-table drift test

**Goal.** The flow table in `spec.md` and `pipeline/flow.py` cannot disagree without CI saying so.

**Context.** P31 requires it; I3 already promises it. An earlier version of this test existed and was
deleted with the rest of `tests/` under Decision 11 — the reason was that the old suite encoded a
design that no longer holds, which was true of what it asserted and not of the idea.

**Approach.** Parse the table out of `spec.md` — `| phase | stage | what it does |` — and compare
its rows, in order, against `PHASES` and `STAGES` in `pipeline/flow.py`. Compare module filenames and
`STEP ·` docstrings against the same source.

**Acceptance criteria.** Changing either side alone fails the build. The failure message names which
row and which side.

**Source.** `spec.md` § *The flow*, I3; AGENTS.md P31.

**Verify.** `uv run pytest tests/guards/test_flow_table.py -q`, then edit one stage name in the spec
and confirm red.

**Landed — `b1c49b6`, and taken before T6.** I17 needs the list of stage names and `flow.py` is the only
place allowed to hold it, so the table had to exist before the guard that reads it. T7's stated
dependencies are T3 and T5, not T6, so the swap cost nothing.

Written in P29's order: the test first, red on an ImportError — a weak red, since a missing symbol proves
nothing about the comparison — then `flow.py`, then seven mutations, one per way the two sides can drift.
Six went red first time. Rewording a summary in `flow.py` did not, because only the `(phase, stage)`
pair was compared — the row also carried a number then — which made `summary` a fourth statement of the
flow that nothing checked. The row is now compared whole. T32 later took the number off both sides, and
the ordering the number used to assert became a list-against-list comparison.

`PHASES` is derived from `STAGES` rather than listed beside it (P16). Deriving a stage's module path
stayed in the test: nothing in the engine dispatches over the table yet, and a function with no caller
in `flow.py` would make a `DEFINITION` module hold logic.

---

### T35 · The axis façade, and the guard that could not see through it

**Goal.** Importing an axis cannot load an implementation of it, and a guard fails if that changes.

**Context.** Both axis façades said *"the protocol, and every implementation of it"*. Follow that and
`from dataforce.modalities import Modality` loads `text2text`, so a stage that imports only the
protocol has a concrete axis behind it — and I2, which reads the *stage's* imports, sees a clean line.
The registry stops being the only way in while every guard stays green. Requirement 38 said the stages
were blind; it did not say anything above an implementation had to be.

Underneath it was a worse one. `tree.py`'s `module_at` named a package's `__init__.py`
`dataforce.modalities.__init__` and resolved its relative imports against *that*, so
`from . import text2text` in a façade came out as `dataforce.modalities.__init__.text2text` and matched
no implementation. Every guard is a filter over that resolution, so the bug did not fail a guard — it
made two of them find nothing, which reads exactly like nothing being wrong.

**Approach.** Façades re-export `base.py` only. Widen I16 from *"no axis `base.py` imports an
implementation"* to *"nothing above an implementation names one"*, covering `base.py` and
`__init__.py` on both axes. Fix `module_at`. Then test the machinery itself — `tests/guards/test_tree.py`
— because a rule that finds nothing is indistinguishable from a rule nothing violates (AGENTS.md §8).

**Acceptance criteria.** A façade that re-exports its implementation fails the build, in the relative
spelling as well as the absolute one. `module_at` names no module `…__init__`.

**Source.** `spec.md` Requirement 38, I16, § *Package layout*; AGENTS.md P18.

**Verify.** Put `from . import text2text` in `modalities/__init__.py` and confirm red.

**Landed.** Found in review, not by a guard, which is the finding. The sequence is worth recording:
the façade re-export was written into the real tree and **all 283 tests passed**. I16 was widened; the
synthetic re-export went red and the real one still passed. That gap is what exposed `module_at` —
the synthetic module resolved correctly because the test said what its package was, and the real one
did not.

`module_from_source` grew a `package` argument for the same reason: its default is the parent, which
is right for a module and wrong for an `__init__.py`, where the package *is* the name. A synthetic
façade that cannot say so proves nothing about a real one.

Three mutations, three reds after the fix, all three green before it: a relative re-export, a deep
relative re-export on the other axis, and the `base.py` case that I16 already covered — kept, because
widening a rule is how the half that worked gets broken.

---

### T36 · One shared request body, and `cli.py` inside `edge/`

**Goal.** The layout stops arguing for two things the routes do not support.

**Context.** Two claims in § *Package layout* did not survive being counted.

*Four `schemas.py` files, "because each router needs a quarter of what a single module would hold".*
Every route but `/load-data` takes `RecordsRequest` and returns `RecordsResponse`. So three of the four
modules would have imported that pair from somewhere, and the layout had no somewhere — which makes the
honest reading of four `schemas.py` files three duplicates of a shape that must stay identical. A change
to it would have had to land in three places to be correct, and nothing would have said so.

*`cli.py` at the package's top level, beside `record.py`.* The spec defines the edge as everything that
touches a file, a socket or a clock; `cli.py` reads argv, opens JSONL and writes it. It was edge in the
wrong place, and the rule paid twice: `engine_modules()` carried two exclusions instead of one, and I17
needed `cli.py` as a special case beside `edge/routers/`. A second condition is a second thing to forget
when a third shell lands.

**Approach.** `routers/schemas.py` for the shared pair; a per-router `schemas.py` only for what one
router alone speaks. `data_quality` and `ai_review` speak nothing of their own, so they become one
module each — §6's rule, and the same rule `pipeline/` already runs on. Move `cli.py` to
`edge/cli.py`, then collapse both scans to one condition.

**Acceptance criteria.** No model is defined twice. `engine_modules()` has one exclusion. The console
entry point still resolves.

**Source.** `spec.md` Decisions 20 and 21, Requirement 36, § *Request and response models*.

**Verify.** `uv run dataforce --help`; `make check`; put `from dataforce.edge.cli import main` in an
engine module and confirm I1 red.

**Out of scope.** Writing any of these models. This task moves and merges docstring-only modules.

**Landed.** 57 modules became 54. The trade on the router shape is written into Decision 20 rather
than left implicit: giving `ai_review` a model of its own later promotes a module back to a package,
which is one move and visible in review. That is the cheaper failure than three copies drifting.

`load_data/router.py` claimed "one sub-endpoint per service" for a phase with one service. Fixed while
it was in front of me — it was wrong before the move and would have been wrong after.

---

### T37 · Give the event stream an owner

**Goal.** The three keys every event carries are written in one place.

**Context.** § *Observability* is specified in full — stdlib `logging.getLogger(__name__)` in every
module, a handler installed by the edge, `run_id` / `record_id` / stage on every record, INFO per
stage per batch and WARNING per record. The layout had no module for any of it, and the spec said
*"`edge/main.py` and `edge/cli.py` each install one handler"*. Two shells implementing one contract
from a paragraph is two copies of it, and the paragraph is not one of them: nothing would fail when
they drift, because an event stream has no test that reads it.

The absence of an *engine* module is deliberate and stays that way — a service emits through the
standard library and names no destination, which is what keeps logging inside Requirement 36. What
was missing is the edge's half.

**Approach.** `edge/observability.py`, `TOOL ·` — the handler and the three keys. Both shells install
what it builds. Nothing in the engine imports it; the engine calls `logging` and this decides where
that goes.

**Acceptance criteria.** The format and the mandatory keys exist once. I1 still passes — no engine
module reaches the edge to emit.

**Source.** `spec.md` § *Observability*; AGENTS.md P27.

**Verify.** `make check`. I19 requires the new module to have a row in the layout.

**Out of scope.** Writing the handler. This declares the owner; T29 fills it.

**Landed** with one wording fix from the same review: `edge/store/repository.py` called itself *"the
QuestionStore port, implemented over a session"*. The port is `ports.py`. Calling the adapter a port
is the path by which someone adds a method to "the port" here, and the engine then has to import
`edge/store/` to name a type — the exact inversion Decision 12 moved `ports.py` inward to prevent.
The name that was proposed for it, `PostgresQuestionStore`, is wrong for a different reason worth
recording: SQLite and Postgres are one adapter with two DSNs, not two adapters (Decision 7). It reads
`LOGIC · the QuestionStore adapter, over a SQLAlchemy session.`

---

### T38 · Why `publish` and `annotator_answers` are two

**Goal.** The document answers the merge question where the reader asks it.

**Context.** A review proposed merging the two: halves of one decision — the shape of the exchange with
the question store — separated only by time, therefore temporal decomposition. The proof offered was
three changes said to touch both files: a new value in the question's enum, a different `question_id`
scheme, a different idempotency guarantee.

None of the three touches either file. The enum is the profile's capture half and its inverse is
`answer_from_response`, a member of the same profile; `question_id` is minted by `question_generate` and
merely read by these two; idempotency is two unique constraints in `edge/store/`. The proposal was
therefore not taken — but the reason it was asked is real: § *Per-service contracts* explains why
`ai_review` is three stages and said nothing about why `human_review` is five. Two files that talk to one
store and have no stated reason to be apart will be asked about again.

**Approach.** Two paragraphs under the `human_review` contract table — why the pair is two stages, and
where each piece of the shape they exchange is owned — and Decision 22 recording the merge as considered
and declined, with its cost.

**Acceptance criteria.** The next reader who asks this finds the answer beside the table, and the
Decisions section says what was given up by not merging.

**Source.** `spec.md` § *Per-service contracts*, Requirements 29–33 and 49, I18; AGENTS.md P1, P2, P16.

**Verify.** `make check` — the flow table is unchanged, so I3 and I19 both still pass over the same
fifteen rows and 55 modules.

**Out of scope.** Any code change. The claim was about module boundaries and the boundaries were right;
what was missing was the sentence saying so.

**Landed** as two paragraphs and Decision 22. No module moved, no test changed, and the flow still has
fifteen rows.

---

## Phase 2 · The shared vocabulary exists

**Goal:** a record can be constructed, typed and hashed. Nothing runs.

### T8 · `errors.py`, `record.py`, `manifest.py`

**Goal.** The three modules every layer uses.

**Context.** `record.py` holds `Record` *and* `Part` — a part is a piece of record content, and
`build_record` on the profile axis takes a `Sequence[Part]` too, so it belongs to neither axis
(Requirement 47). `ConfigError` is the one exception this codebase defines.

**Approach.** Pydantic models following `spec.md` § *The record*, which carries a comment on every
key. Requirement 1 and I7: `Field(..., description=…)` on every field, grouped under
`# --- Section ---`. `record_id` is 16 hex over canonicalised content via `agent-toolkit`'s
`compute_hash` — never re-implemented.

**Acceptance criteria.** I7 passes over the whole module. I9: `record_id` is stable across a shuffled
re-ingest and sensitive to content. I10: `Record` has no answer-space field, and constructing one
raises.

**Source.** `spec.md` § *The record*, Requirements 1, 47; I7, I9, I10.

**Verify.** `make check`; `uv run pytest tests/stages -q -k record`.

**Landed.** The whole drawing, not only the keys `load_data` writes: 23 models and 101 described
fields, because § *The record* carries a comment on every key and Requirement 1 says the record is the
place a key's meaning is written down next to the key. A record holding only the load-time half would
leave the other eleven keys with no home, and no later task claims them. I7 stopped being vacuous on
the same commit — it had nothing to find until this module existed, which is what P29 asked of it. The
tests are `tests/stages/test_record.py` and `test_manifest.py`: a record is not a stage, but it is what
every stage reads and returns, and this task's *Verify* already pointed there.

Four shape decisions, each with a cost. **Every model is frozen and every sequence is a tuple**, which
is Requirement 41's `output == input` *structurally* before there is a second stage to assert it
against: a stage returns `model_copy(update=…)` or it returns nothing. The guarantee stops at the
record's own shape — `meta`, `label` and the resolved configs are free-form JSON, and a dict inside one
of them is still a dict. **`record_id` is a field and not a validator over `content`:** `pii_check`
rewrites content, so an id recomputed on construction would change under redaction and take every join
in the corpus with it. **A key's model is named for what the key holds, never for the stage that writes
it** (§5) — `data_quality.label_check` holds a `LabelVerdict`, because `LabelCheck` is already the
profile's word for one of the five checks (Requirement 47), and two of those in one import is the
ambiguity §5 is about. **`class` is a keyword here and a key there**, so a span's field is
`personal_data_class` aliased to `class`, serialised by alias in both directions and proved through one
JSON round trip.

Two gaps in the drawing, found by typing it and not closed here. `annotator_answers.responses` has no
`was_skipped`, but Requirement 50 says a skip is stored, counted and excluded from `aggregate`'s
overlap, and the store's `annotator_answer` table already has the column — so either the record grows
the key or `aggregate` reads the store, which it may not. Requirement 49's `malformed` corrected value
has no key at all. Both belong to T24 and T25, recorded here so they are decided rather than discovered.

One consequence of Requirement 6, written down because it is easy to miss: `record_id` is over content
and nothing else, so two records with identical content are one id. That is exactly what
`duplicate_content_diff_label` is for — same content, different label — and it cannot name the other
record by an id the two share. T17 settles it: either a duplicate group references `source_id`, or the
id takes something more than content and Requirement 6 changes.

---

### T9 · `engine.py`, `ports.py`, and the registry

**Goal.** An `Engine` exists inside the engine and holds no I/O.

**Context.** Decision 12 — the abstraction belongs to the layer that consumes it (P18). `Engine` and
`Registry` are `dataforce/engine.py`; `open_engine` is Phase 7. `ports.py` holds `QuestionStore`;
`MediaResolver` was deleted under T3, so `ports.py` holds one port.

**Approach.** `Engine` is a frozen dataclass: the resolved pair, the registry, thresholds, and the
digests of the policy files that produced them. A registry is instance state (Requirement 39) — two
registries in one process hold different implementations, and registering a second implementation of
one name is refused.

**Acceptance criteria.** I1 passes over `engine.py`. Two registries in one process are independent.
A duplicate registration raises `ConfigError`.

**Source.** `spec.md` § *Engine and edge*, Requirements 36, 39; Decision 12.

**Verify.** `uv run pytest tests/guards -q && uv run pytest tests/stages -q -k registry`.

---

### T10 · `pipeline/flow.py` and `pipeline/runner.py`

**Goal.** The flow table exists once in code, and something owns the order a phase runs in.

**Context.** `POST /data-quality` runs three stages in order; nothing owned that order, so a router
composing them would put a piece of the flow table at the edge and keep a second copy of it
(Requirement 48). `pipeline/__init__.py` is a façade that re-exports both, consistent with the axis
packages.

**Approach.** `flow.py` is `DEFINITION ·` — `PHASES` and `STAGES`. `runner.py` is `LOGIC ·` —
`run_phase(engine, phase, records)`, folding that phase's stages over the records in the table's
order.

**Acceptance criteria.** T7's drift test passes. I17: no module under `edge/routers/` or `cli.py`
names two stages in sequence.

**Source.** `spec.md` § *Package layout*, Requirement 48; I3, I17.

**Verify.** `uv run pytest tests/guards -q`.

---

## Phase 3 · Both axes answer their contracts

**Goal:** `text2text` and `tool_decision` resolve from config and satisfy their protocols.

### T11 · The two protocols

**Goal.** `Modality` (six members) and `Profile` (fourteen) exist, with their types opaque at the base.

**Context.** Requirement 47 — a protocol that names a type forces it to be defined at or above the
protocol, so `Answer`, `AnswerConfig` and `LabelCheck` are aliases in `profiles/base.py` and the
concrete models live in the implementation's `schema.py`. Otherwise `base.py` imports a concrete
axis, which I16 forbids.

**Approach.** Two `Protocol` classes and the type aliases they name — nothing that satisfies either.
`Answer`, `AnswerConfig` and `LabelCheck` in `profiles/base.py`; `Detector` and `DisplayConfig` in
`modalities/base.py`. Both import `Part` from `record.py`, and neither imports an implementation.

**Acceptance criteria.** I16 passes. Requirement 40: `name`, `version` and `modality` are never
assigned in a class body — they come from `config/<axis>/<name>.yaml`, whose filename is the
identity, and `version` is a string.

**Source.** `spec.md` § *Modality*, § *Profile*, Requirements 40, 47; I5, I16.

**Verify.** `uv run pytest tests/guards -q`.

**Landed — before T9, which this plan did not say it had to be.** `Engine` holds the resolved pair, so
`engine.py` names `Modality` and `Profile` in its own fields; without them the pair types as `object`
and every stage that calls a member needs a cast to do it. T9's stated dependencies are T3 and T8, and
this task is missing from them — the same shape as the T7-before-T6 swap, and it cost nothing but the
phase boundary.

Two `Protocol` classes, five opaque aliases, and one re-export per façade. The aliases are
`type X = Any` (PEP 695), which is what *opaque* means here: the base names the type so a signature can
use it and says nothing about what is inside, because saying more would make the protocol a description
of its single implementation (P18) and naming the model would be the import I16 forbids. `Answer` is
the sharpest of the five — what an answer *is* is the whole of what a profile declares.

The façades now hold what their docstrings already promised: `from .base import Modality`, and nothing
that implements it. I16 and I5 were vacuous over these four modules until this commit, because an empty
file names nothing.

---

### T12 · `text2text`

**Goal.** One modality implementation, resolvable from `config/modalities/text2text.yaml`.

**Context.** Six members: `content_parts`, `embedding`, `personal_data_detectors`, `display_config`,
plus `name` and `version`. The embedder is `model2vec` with static embeddings, so a vector is a pure
function of its input and two runs dedup identically. `exclude_roles: [system]` is a measured choice
recorded in the manifest.

**Approach.** `__init__.py` is the implementation and its six members, `schema.py` the `Detector` and
`DisplayConfig` models, `utils.py` the conversions over them. Identity and `exclude_roles` come from
the manifest; nothing is assigned in a class body (Requirement 40).

**Acceptance criteria.** I4: the implementation is `__init__`, `schema`, `utils`, and `schema`
imports no `utils`. The same input produces the same vector across two processes.

**Source.** `spec.md` § *Modality*; `config/modalities/text2text.yaml` after T4.

**Verify.** `uv run pytest tests/stages -q -k text2text`.

**Out of scope.** `speech2text`, `image2text`, `video2text` — the seam is specified and unbuilt.

---

### T13 · `tool_decision`

**Goal.** One profile implementation, and the four operations over its answer type.

**Context.** T1 settled what an answer is. This is the largest single task in the plan: fourteen
members, of which four carry real algorithms — `answer_schema` (`oneOf` per tool), `answer_distance`
(name-first and soft), `vote_consensus` (per name, then per argument), and `label_checks` (five
checks). Everything a stage knows about the task comes from here.

**Approach.** `schema.py` holds the answer models — a call is a name and its arguments.
`utils.py` holds the conversions over them, which is exactly the exemption §6 grants and
`AGENTS.md`'s conflicts section confirms. The five checks are `label_assistant_mismatch`,
`label_not_in_catalog`, `empty_catalog`, `label_cardinality_anomaly`, `label_names_one_tool_twice`.

**Acceptance criteria.**
- δ's worked ordering holds to the bit: `δ(same call) = 0 < δ(same tool, one of two arguments
  differs) = 0.5 < δ(different tools) = 1`, and `δ(∅, ∅) = 0`.
- With every matched call argument-less, δ equals `1 − |A∩B| / |A∪B|` exactly.
- `vote_consensus` drops a call missing a `required` argument rather than completing it.
- `answer_schema` rejects `OpenTicket` carrying `LookupBalance`'s argument, which an `enum` of names
  beside a free-form object could not do.
- No record stores an answer space (I10).

**Source.** `spec.md` § *Profile*, the Decision added in T1; `git show 1bdc63f`, `git show d368afd`.

**Verify.** `uv run pytest tests/stages -q -k tool_decision`. The δ ordering is a hand-worked
assertion, not a property test.

---

## Shared decisions for every stage task in Phases 4–6

These are the *Approach* for T14 to T26 — stated once so ten task descriptions do not repeat them. A
task below adds an *Approach* of its own only where it departs from this.

- **One signature.** `def <stage>(engine: Engine, records: Iterable[Record]) -> ServiceResult`.
  `ServiceResult` carries `records` and any side output the edge must persist. The engine returns
  side output; it never writes it. There is no third field — **the records are the report**.
- **Record in, record out.** Each stage writes exactly one key (I8) and returns as many records as it
  was given (I11). No stage removes a record; quarantine is a value and deduplication is a group
  annotation.
- **Preconditions, not gates.** A stage declares the upstream keys it needs and *skips* a record that
  lacks them, marking it. A run always completes. The only exception raised anywhere is
  `ConfigError`, before any record is read.
- **Preconditions live in code** (P12) — beside the signature, not only in the spec's *skips when*
  column.
- **One test module per stage** in `tests/stages/`, asserting that stage's row: it writes its key,
  writes nothing else, returns as many records as it got, and skips exactly the records its
  precondition excludes.
- **Fixtures are invented, never extracted from real data** (AGENTS.md §9), in `objective.md` §2's
  shape.
- **No network in `make check`.** Every jury test uses a stubbed panel.
- **Nothing re-implements `agent-toolkit`** (I6).

---

## Phase 4 · One record makes the round trip

**Goal:** `load_data` and all of `data_quality` run in process over invented fixtures.
Every task here follows § *Shared decisions*.

### T14 · `load_data`

**Goal.** Every source item becomes one record with identity, content, provenance and label.

**Context.** The only place a source shape is read. The input is standard OpenAI chat-completion
records with `tools` as data. `meta.label` is the answer and nothing else is — a conversation may
contain completed `tool_calls` from earlier turns, and an extractor scraping those produces the wrong
answer. Which key holds the label is declared in the profile manifest, not assumed.

**Approach.** `content_parts` from the modality, `build_record` from the profile. Stamp `provenance`
— Decision 4 — with `run_id` supplied by the edge, because the engine has no clock. The catalog is
**not** copied onto the record as an answer space.

**Acceptance criteria.** A fixture whose conversation contains a prior `tool_call` and whose
`meta.label` names a different tool produces a record whose `label` is the declared key's value.
An undeclared label key raises `ConfigError` naming the manifest, the key, and what *is* declared.

**Source.** `spec.md` § *Per-service contracts* row 0; `objective.md` § *`meta.label` is the answer*.

**Verify.** `uv run pytest tests/stages/test_load_data.py -q`.

---

### T15 · `label_check`

**Goal.** The five checks that need no opinion run, and a failing record is marked rather than
removed.

**Context.** The checks are the profile's, delivered by T13. `params.invalid_counts` is empty until a
corpus is declared; a check reading 0 is what tells you when it stops reading 0.

**Acceptance criteria.** A record failing any check carries `quarantined: true` and travels on.
`failed_checks` names which. `len(out) == len(in)`.

**Source.** `spec.md` § *Per-service contracts* row 1, Requirement 22.

**Verify.** `uv run pytest tests/stages/test_label_check.py -q`.

---

### T16 · `pii_check`

**Goal.** Personal data is found in Vietnamese text and replaced with stable typed placeholders,
content and label together.

**Context.** Two layers. Layer one is patterns over the raw text *and* over
`normalize_text(text, remove_tone_marks=True)`, covering the spoken forms an off-the-shelf scrubber
misses: digits as words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), `@` as `a còng`, `.` as `chấm`. It
is tuned for recall and is *allowed* to be noisy — a digit run is also a price, a date, an order
reference. Layer two is a model pass over a bounded window marking each hit verified or not. Legal
basis: Law 91/2025/QH15 and Decree 356/2025/ND-CP.

Redaction rewrites `content` **and** the label (T2), bumping `content_version`. The placeholder map
is side output returned to the edge, never written by the engine and never committed.

**Acceptance criteria.**
- Adversarial fixtures pass: spoken digits with and without tone marks, `a còng`, `chấm`, one value
  used twice in one record yielding one placeholder, and a digit run that is a price — layer one
  flags it, layer two clears it.
- A value appearing in both content and a label argument is replaced in both with the same
  placeholder, and `label_assistant_mismatch` still passes afterwards.
- `enable_redact: false` reports and leaves content untouched, `decision: "reported"`. The run
  completes.
- I13: the placeholder map is never read by a stage and is covered by `.gitignore`.

**Source.** `spec.md` § *PII, in two layers*; T2 item 2.

**Verify.** `uv run pytest tests/stages/test_pii_check.py -q`.

---

### T17 · `duplicate_check`

**Goal.** Near-duplicates are grouped on the record and never removed.

**Context.** The modality's embedding is the content side. Whether two records are duplicates *for
this task* also depends on the answer — two identical prompts with different catalogs are not
duplicates in `tool_decision`. Decide whether `scenario_hash` is already that function under a
split-shaped name, or whether the profile contributes a separate answer-side key. Settle before
writing either.

**Acceptance criteria.** `duplicate_content_same_label` and `duplicate_content_diff_label` are
populated as group annotations. No record is dropped. Two runs over one corpus group identically.

**Source.** `spec.md` § *Per-service contracts* row 3, Requirement 23.

**Verify.** `uv run pytest tests/stages/test_duplicate_check.py -q`.

---

### T18 · The bus and conservation properties

**Goal.** I8 and I11 hold across every stage built so far.

**Context.** Requirement 41 says `output == input` at every stage, "structurally — not asserted,
because there is nothing to assert against". Once four stages exist there is something: run them in
sequence and watch the diff. This catches a stage quietly filtering, which is the failure the whole
precondition design exists to prevent.

**Approach.** Build one corpus, run every in-scope stage, and assert that each step's diff is exactly
one key and that the set of `record_id`s is identical at every step. One test, both properties, in
`tests/properties/`. Re-run it as each later phase lands.

**Acceptance criteria.** Over a corpus containing at least one quarantined record, one duplicate pair
and one record that fails every precondition downstream of `label_check`: each step's diff is exactly one
key, and the `record_id` set is identical at every step including the last. A stage that drops a
record fails this test rather than the reviewer noticing.

**Source.** `spec.md` I8, I11, Requirement 41.

**Verify.** `uv run pytest tests/properties -q`. Then make one stage return `records[:-1]` and
confirm red; revert.

**Out of scope.** I15 — that needs both shells and is T29.

---

## Phase 5 · The panel scores a record

**Goal:** all of `ai_review` runs against a stubbed panel. The live panel is Smoke.
Every task here follows § *Shared decisions*.

### T19 · `jury`

**Goal.** A panel of models answers the record's own task, and every vote is kept.

**Context.** Costs money per record, so it is cached. Skips a record whose
`label_check.quarantined` is true — no point paying a panel to judge a record already known broken.
The model-facing task statement is whatever T2 item 3 decided. `agent-toolkit` owns retry and rate
limiting; an exhausted call is one missing vote.

**Acceptance criteria.** A vote that does not validate against `answer_schema` is kept with
`valid: false` and counted in `invalid_votes`, never silently dropped. `prompt_version` and
`panel_version` are on the record, because a change to either invalidates comparison.

**Source.** `spec.md` § *Per-service contracts* row 4, Requirements 24 and 28.

**Verify.** `uv run pytest tests/stages/test_jury.py -q` — stubbed panel, no network.

---

### T20 · `cohesion`

**Goal.** Two numbers per record: how much the jurors agree with each other, and with the existing
label.

**Context.** Pure arithmetic over what `jury` wrote, using the profile's δ. Separate from `jury`
because it re-runs for free while the panel does not.

**Acceptance criteria.** `method` is recorded so the two numbers are comparable across runs.
`δ(∅, ∅) = 0` does not produce `NaN` on the empty-answer population.

**Source.** `spec.md` § *Per-service contracts* row 5, Requirement 25.

**Verify.** `uv run pytest tests/stages/test_cohesion.py -q`.

---

### T21 · `triage`

**Goal.** Each record lands in a bucket, and some are selected for a human.

**Context.** Thresholds come from `params.thresholds.triage` and are provisional until the pilot
measures them. This stage gets **exactly one** re-tuning pass after the pilot. A bucket whose
precision the pilot cannot establish gets **no quota**.

**Acceptance criteria.** `reason` names which rule selected the record, so a quota can be audited.
No numeric literal in the module (P25).

**Source.** `spec.md` § *Per-service contracts* row 6, Requirements 26 and 27; Decision 3.

**Verify.** `uv run pytest tests/stages/test_triage.py -q`.

---

## Phase 6 · The loop through people closes

**Goal:** a question reaches a store, an answer comes back, a label is curated.
Every task here follows § *Shared decisions*.

### T22 · `question_generate`

**Goal.** One question at a time about one record, in the annotator's language.

**Context.** Reads `triage` **only** to decide which records get a question. Requirement 30: no model
output may reach an annotator — no vote, no cohesion number, no bucket in the payload. The written
glossary is a precondition on the *run*, checked once at composition and raised as `ConfigError`.

**Acceptance criteria.** I12 passes on the payload and the generated config — no vote, no cohesion
number, no bucket in `data`. Answering *incorrect* requires the corrected value, enforced by
`visibleWhen` + `required` rather than by hope. The tool list is a **dynamic** choice list, because a
Label Studio project has one config for every task and our catalog is per record. `question_id` rides
inside `data`, because Label Studio assigns its own task ids.

**Source.** `spec.md` § *Per-service contracts* row 7, § *The annotation config, and what comes
back*, Requirements 29, 30 and 52; I12.

**Verify.** `uv run pytest tests/stages/test_question_generate.py -q`.

---

### T23 · The question store

**Goal.** Three tables behind the `QuestionStore` port.

**Context.** `question`, `publication`, `annotator_answer`, owned by `edge/store/`, every column
carrying its purpose in the model. SQLAlchemy 2.0 declarative, Alembic migrations. SQLite by default,
Postgres by URL, DSN read at the edge from `DATAFORCE_DATABASE_URL`. The two unique constraints —
`(question_id, external_system)` and `external_annotation_id` — are what make the sync idempotent.

**Acceptance criteria.** Migrations apply cleanly to an empty database. The same store tests run
twice — SQLite in `make check`, Postgres under `-m integration` — because the sync's idempotency rests
on two unique constraints, which is exactly the behaviour the two engines disagree about (Decision 7,
rewritten under T3). The three tables carry `was_skipped` and `lead_time_seconds`: both are instruments
the pilot reads, not bookkeeping.

**Source.** `spec.md` § *The question store*; Decisions 6 and 7; T3's P26 row.

**Verify.** `uv run pytest tests/stages -q -k store` (SQLite in `tmp_path`); `make integration`.

---

### T24 · `publish` and `annotator_answers`

**Goal.** Questions reach the store and answers come back, with no Label Studio anywhere.

**Context.** Decision 6 — `publish` writes to a database we own; the sync is separate (T26). The
annotation config is composed from the modality's display half and the profile's capture half, and
neither may emit the other's. `annotator_answers` parses responses through `answer_from_response`
(T2 item 1).

**Acceptance criteria.** Both stages run to completion against a store with no Label Studio
configured. `publish` records the receipt on the record; `annotator_answers` skips a record the
store names no questions for. **I18 round-trips the format:** compose the config and payload for a
fixture, feed back a synthetic `result` in Label Studio's shape, and assert the answer that comes
out is the one that went in — and that a `textarea` value given as a string rather than a list
fails. A corrected value that does not validate against `answer_schema` is recorded `malformed`,
never coerced; `was_cancelled` is stored as a skip and excluded from `aggregate`'s overlap.

**Source.** `spec.md` § *Per-service contracts* rows 8–9, § *The annotation config, and what comes
back*, Requirements 31, 32, 33, 49 and 50; Decision 6; I18.

**Verify.** `uv run pytest tests/stages/test_publish.py tests/stages/test_annotator_answers.py -q`.

---

### T25 · `aggregate` and `curate`

**Goal.** One verdict per record, then the final label.

**Context.** `aggregate` uses Krippendorff's α for incomplete overlap and skips a record with fewer
responses than the rung's overlap floor — that record keeps its answers and gets no verdict.
`curate` writes `status`, the validators, and where they disagreed, who adjudicated. A verdict of
*incorrect* with no corrected value is recorded as `status: "unresolved"`.

**Acceptance criteria.** The final label validates against `answer_schema`. Agreement uses the
profile's δ, not string equality.

**Source.** `spec.md` § *Per-service contracts* rows 10–11, Requirements 34 and 35.

**Verify.** `uv run pytest tests/stages/test_aggregate.py tests/stages/test_curate.py -q`.

---

### T26 · The Label Studio sync

**Goal.** `POST /human-review/publish/sync` moves questions out and annotations back, idempotently.

**Context.** `label-studio-sdk`, optional extra. Label Studio server 1.23.0. Running the sync is
optional; every other endpoint works with no instance anywhere.

**Acceptance criteria.** Running it twice in each direction is a no-op the second time — the two
unique constraints are what make it so. Label Studio unreachable fails the sync, changes no record
key, writes no `publication` row, and leaves every other endpoint unaffected.

**Source.** `spec.md` § *The question store*, § *Routes*, § *Versions*; Decision 6.

**Verify.** `uv run pytest tests/stages -q -k sync` against a fake client; `make integration`
against a real instance.

---

## Phase 7 · Two shells, one implementation

**Goal:** HTTP and an in-process caller produce the same record.

### T27 · The edge

**Goal.** `open_engine` composes a run, and one module is the only place a file is read or written.

**Context.** `edge/bootstrap.py` is the composition root (P19) — the only builder of an `Engine`.
`edge/policy.py` turns `config/<axis>/*.yaml`, `params.yaml` and prompts into declarations.
`edge/artifacts.py` is the one place a record file, `metrics.json` or a run manifest is touched.
Corpus-level numbers are a fold here, for reading — never computed by a stage, never compared against
a threshold that stops anything.

**Acceptance criteria.** An engine builds with **no filesystem anywhere** — both axes handed
`Manifest` objects and a template string. Naming no modality takes the profile at its word; naming a
different one raises `ConfigError` saying which modality the profile composes with. I14: two runs of
one unchanged configuration produce byte-identical run manifests.

**Source.** `spec.md` § *Engine and edge*, § *Configuration*, Requirements 36, 44 and 45; Decision 12.

**Verify.** `uv run pytest tests/shells -q`; `make check`.

---

### T28 · The routers

**Goal.** Four main endpoints and their sub-endpoints, on the style reference's pattern.

**Context.** `create_app()` factory, one `APIRouter(tags=[…])` per domain, kebab-case URLs, thin
handlers mapping `ValueError` → 400 and anything else → 500. Request and response models live in
`edge/routers/<domain>/schemas.py`, one per router, every field described. A phase route calls
`run_phase`; it never names a stage sequence (I17).

**Acceptance criteria.** A stage route returns `200` with every record it was given, because a bad
record is a marked record rather than a failed request. `ConfigError` is 400, a malformed body is
pydantic's 422. `GET /branches` lists registered modalities and profiles with versions.

**Source.** `spec.md` § *Routes*, § *Request and response models*, Requirement 48; I17.

**Verify.** `uv run pytest tests/shells -q`.

---

### T29 · The CLI and the event stream

**Goal.** One subcommand per stage, dispatched over the flow table; and a run can be watched while it
runs.

**Context.** The CLI is a dispatch over `flow.py`, not fifteen hand-written subcommand bodies —
every stage has one signature and Requirement 46 makes the in-process call the same call, so it stays
roughly one screen however many stages exist. The event stream is now specified in § *Observability*:
the engine emits through stdlib `logging`, `edge/main.py` and `cli.py` each install one stdout handler,
and every event carries `run_id`, `record_id` and stage. Levels are part of the contract — INFO per
stage per batch, WARNING per record for what a human must look at, ERROR only for `ConfigError`, and no
DEBUG per record, because twenty thousand records times fifteen stages is a log nobody reads.

**Acceptance criteria.** I15: the same input through `pii_check(engine, records)` and
`POST /data-quality/pii-check` produces equal records. Adding a stage to `flow.py` adds a subcommand
with no edit to `cli.py`. A long run emits progress while running, not only after it stops.

**Source.** `spec.md` § *Running it*, § *Observability*, Requirement 46; I15; `AGENTS.md` P27.

**Verify.** `uv run pytest tests/shells -q`; run the CLI over a fixture and watch the output.

---

## Phase 8 · The rungs

**Goal:** provisional thresholds become measured ones.

**Blocked on a declared corpus.** Both tasks. Everything above runs on invented fixtures; these do
not. Also blocked on the two prerequisites that are not code: the cross-border data-transfer review
before the first offshore jury call, and the written glossary before the first generated question.
Both are preconditions on opening the engine, checked once and raised as `ConfigError`; this plan
requires them recorded and does not perform them.

### T30 · Smoke

**Goal.** One annotator, a stubbed panel and then a live one, end to end.

**Context.** The first rung: the smallest corpus that exercises every stage, and the first time the
flow meets a real panel and a real person. It is not expected to measure anything — its job is to
size the pilot and to find what only breaks outside a fixture.

**Blocked by.** T29, and a declared corpus.

**Acceptance criteria.** A record travels every built stage and reaches a human. Costs and latencies are
recorded so the pilot can be sized.

**Source.** `spec.md` § *Testing Strategy* — the three rungs.

**Verify.** `make integration`.

---

### T31 · Pilot

**Goal.** Two annotators at 100% overlap against a real jury, measuring the instruments.

**Context.** The pilot answers four questions: is the question answerable, is the guideline right, do
two people agree, does each bucket predict what humans find. It is what turns `params.thresholds`
from provisional into measured, and `triage` gets exactly one re-tuning pass on the result. A bucket
whose precision the pilot cannot establish gets no quota.

**Blocked by.** T30, a declared corpus, the cross-border data-transfer review, and the written
glossary.

**Acceptance criteria.** `params.thresholds.pilot` is populated from measurement — α, flag rate, gold
accuracy, bucket precision — and the re-tuning pass is a single committed diff to `params.yaml`.

**Source.** `spec.md` § *Testing Strategy*; Decision 3.

**Verify.** `make integration`; the threshold diff is one commit with the measurement in its message.

---

## Not planned here

- **`release`** — `split`, `export`, `datasheet`. Declared in the flow so
  `record.release` has an owner; specified in a follow-up. Nothing before it may assume its
  shape. Note that `export` carries the precondition that keeps an unredacted corpus out of a
  release, so **until it exists, nothing prevents a reported-but-unredacted corpus reaching an
  artifact** — the stated cost of Decision 10.
- **The web view.** One Vite + TypeScript SPA over these same endpoints, on the style reference's
  pattern. A later task by `objective.md` §9, and this plan keeps it one.
- **Real `speech2text`, `image2text`, `video2text`.** The seam is specified and unenforced.
- **Our own annotation platform.** Deferred, not cancelled; the pilot decides.
