# Annotation Pipeline — Implementation Plan

**Source:** [`spec.md`](spec.md) (75 requirements, 19 invariants, 15 stages) and [`../profiles/tool-decision/spec.md`](../profiles/tool-decision/spec.md) (27 requirements, 5 invariants).

**One plan, two specs.** They are not independently buildable. Fourteen of the fifteen stages are written against two protocols, and `tool_decision` is the only implementation of one of them — a plan for the core alone would produce tasks whose acceptance criteria cannot be verified, because you cannot test `jury` without an answer type, a δ, and a corpus. [`guided-validation`](../guided-validation/spec.md) gets no separate plan: the pipeline consumes its question model inside `generate_questions`, so its requirements appear as acceptance criteria on that stage. [`dataforce-platform`](../dataforce-platform/spec.md) gets a plan only if the Phase 5 pilot gate says Label Studio is the constraint.

**Six phases and three revision passes, 46 tasks.** Phases are ordered by risk and learning value, not by layer, and every phase ends in something runnable. Task numbers are stable — they are cited in commit messages and in both specs — so no task is ever renumbered, and the two revision passes use R and E numbers so the tasks after them keep the numbers they were planned under. 2C is the third: the answer type changed, and requirements 70–75 are what it is being changed to.

## Where the work stands

| Phase | Outcome | Tasks | State |
|---|---|---:|---|
| 1 | The repo builds, both contracts exist, and the rules a profile must satisfy are written down | 6 | **built** |
| 2 | One raw record becomes a canonical record and comes back out as a training example | 4 | **built** |
| 2R | Every name says what it returns, a module is one workflow step, and 49 files become 30 | 3 | **built** |
| 2E | The engine touches no filesystem, `api/` is the surface every caller enters, and DVC versions data instead of orchestrating it | 6 | **built** |
| 2C | An answer is a set of calls with arguments, a conversation is as many turns as it takes, and δ tells a wrong tool from a wrong argument | 4 | |
| 3 | 21,172 records become a usable corpus with no personal data downstream | 6 | |
| 4 | 50 records voted by three jurors, ranked into a review queue, inside a token ceiling | 5 | |
| 5 | Two annotators answer ~700 questions and the pilot gate passes on all five thresholds | 7 | |
| 6 | A reproducible `release/v1` with a datasheet and a fully human-validated test split | 5 | |

Today: **264 tests** (231 under `make check`, 33 marked `integration`), **35 source modules**, and `dvc.yaml` declaring **zero stages** — and it will keep declaring none, because DVC versions data rather than orchestrating it. Nothing is a pipeline stage yet — what exists is two contracts, one modality, one profile, the surface every caller enters through, and the measurements every later gate is declared against. Phase 2E fixed the layering the first stage would otherwise have been written against; the first stage arrives in Phase 3.

**Checking the built half, in four commands.** Each proves something a later phase depends on; none needs a network or a service except the third. A fifth, `uv run dvc repro`, is gone: with DVC no longer orchestrating there is no DAG to report on.

| Command | What it proves |
|---|---|
| `make check` | ruff, `mypy --strict` on `src/`, and 231 tests |
| `uv run dataforce profile --profile tool_decision` | the profiler reads all 21,172 records, streaming, and reproduces every committed count |
| `uv run pytest -q -m integration` | the corpus-wide claims: byte-identical catalog round trip, the four validity counts, the drift check |
| `uv run pytest tests/unit/test_import_graph.py tests/unit/test_no_reimplementation.py` | invariants 16 and 17 — no concrete axis reaches `shared/` or `pipeline/`, and no toolkit function is re-implemented |

## Shared decisions — read once, apply to every task

Settled by the specs. No task re-decides them, and a task that violates one is rejected in review regardless of whether its own acceptance criteria pass.

1. **The library is not re-implemented.** No module defines a hash helper, a JSONL reader/writer, an atomic-write context manager, a JSON-from-text extractor, a template filler, or a retry wrapper. `openai`, `tenacity`, `tiktoken`, `jsonschema` appear in no pipeline import. Use the call table in spec § *What `agent-toolkit` already provides*. — core invariant 17
2. **Every artifact is read and written through `file_utils`**, which is already atomic and creates parents. No stage opens an artifact file directly. — core requirement 17
3. **Nothing under `pipeline/` or `shared/` imports a concrete profile or modality.** Both arrive through their registries. — core invariant 16
4. **Every token figure is an estimate.** `agent-toolkit`'s `Completion` discards `usage`, so budgets are enforced on `count_tokens` estimates and every reported figure is labelled "estimated". — core requirement 37, Assumption
5. **Thresholds live in `params.yaml` and `config/gates.yaml`, never in code.** `shared/gates/runner.py` is an engine: it raises with a gate's verdict and writes nothing. — core requirement 68
6. **One `except LLMError` per dispatching stage.** Nothing catches bare `Exception` around an LLM call. — core § Error Behavior
7. **Content parts use `type`, not `kind`**, with closed values `text | image | audio | video` and the payload flat on the part. — core Decisions
8. **Python `>=3.12,<3.13`**; `agent-toolkit[llm] @ git+https://github.com/giangchicken/agent-toolkit.git@v0.1.0`. `git` must exist on the installing machine. CI sets `TIKTOKEN_CACHE_DIR` against a populated cache.
9. **`data/raw/` is outside DVC entirely.** Not tracked, not committed, in `.gitignore`. Every other `data/` directory is versioned by `dvc add` when a person decides a milestone is worth keeping — DVC does not orchestrate, and `dvc.yaml` declares no stages. — core Decisions
10. **Every name contains its result**, everywhere — not only on the contracts. `X_to_Y` for a conversion, `build_X` for something assembled, `read_X` for something pulled out of a larger structure; the convention is the corpus generator's own. Rejected: a single word naming an operation without its object (`adapt`, `parse`, `of`), a name that reads backwards (`label_of`), and any name that is also a stage name (`load`, `export`). — core § The two contracts, core Decisions
11. **A module is a definition or a step, never both.** A definition module defines one noun and every conversion of it, and is expected to serve many steps. A step module serves exactly one step and nothing else — so a helper used by one step gets no file of its own. Two further limits: a module may not force a consumer to depend on what it does not use, which is why `shared/schemas/` stays a package divided by pipeline phase rather than becoming one file every stage imports; and a module's name says what is inside it. — core Decisions
12. **There is no conformance suite.** The five profile rules are stated in core § *Rules a profile must satisfy* and each profile proves them in its own tests. Nothing checks them at registration, and the cost of that is stated with the rules. — core requirement 6, core Decisions
13. **The engine computes; `declared/` reads config; `api/` is the surface.** No module under `modalities/`, `profiles/`, `pipeline/` or `shared/` opens a file, names a config or data location, imports `agent_toolkit.file_utils`, or is constructed at import time. Every path is a required parameter. Every caller enters through `api/`, `cli.py` included. — core requirements 66–69, core invariants 18–19
14. **`dataforce run [stage ...]` runs the named stages, or all fifteen.** There is no stage cache: naming stages is how a person re-does one without re-doing the corpus. — core Decisions
15. **A number a task asserts comes from `metrics/corpus_profile.json`, not from prose.** The profiler is the only thing that measures the corpus, and CI pins its output. Three figures in the profile spec's own table had drifted from it unnoticed — corrected in this pass — so a task that quotes a count quotes the profiler, and prose in either spec is secondary to the committed file.

16. **An answer is a set of calls, each with its arguments, and one call per tool name.** δ is name-first with per-argument agreement and reduces to Jaccard over names when arguments agree; consensus is majority per name then majority per argument, dropping a call it cannot assemble fully. A turn carrying a call is one canonically-rendered part, not a new part type. No task re-decides any of this — core requirements 70–75, core *Decisions*, built in Phase 2C. — the check on every task after 2C is that nothing under `pipeline/` or `shared/` changed to accommodate it.

**Two prerequisites that are not code, and both blocking.** T21 (cross-border transfer review, before the first jury run against any offshore endpoint) and T27 (the marker-DSL glossary, before T23). They are numbered tasks rather than footnotes because skipping them silently is the failure mode.

---

# Built — Phases 1 and 2

Both phases are on `main`. What follows is what exists and the test that proves it, not the reasoning that produced it — that lives in the specs, which are the durable half. Task numbers are kept because later tasks and commit messages cite them.

| # | Task | What exists now | Proved by |
|---|---|---|---|
| T1 | Repo skeleton and toolchain | `make check` = ruff + `mypy --strict` + 231 tests. `uv`, `src/` layout, `dvc init`, `params.yaml`, `.gitignore` covering `data/raw/`. `cli.py` is the only module that configures a logging handler; everything else takes `get_logger(__name__)` | `tests/unit/test_repo_hygiene.py` |
| T2 | Canonical record and artifact schemas | Typed `Part` (`text \| image \| audio \| video`), `Record`, and `rid` from the content parts' digests — each part contributing `type:role:digest`, so identity is order-independent and modality-independent. One pandera schema per artifact. **R2 reduced 14 schema modules to 6: `base.py` plus one per pipeline phase** | `test_record.py`, `test_artifact_schemas.py` |
| T3 | Gate runner | A gate is a named predicate over a stage's inputs and outputs with thresholds from `config/gates.yaml`. A failure writes `GATE_FAILED.json` carrying the assertion, observed, expected and up to 100 offending `rid`s, then exits non-zero. No numeric threshold in `runner.py` | `test_gate_runner.py` |
| T4 | The two protocols and their registries | `Modality` with four members; `Profile` with twelve protocol attributes — the nine of requirement 2 plus `name`, `version`, `modality`. Both member sets are pinned as literals, so adding a member fails a test. A profile whose declared modality differs from `--modality` is a hard stop. **R1 renamed ten of them** | `test_protocols.py`, `test_registries.py` |
| T5 | The five profile rules, written down | Core spec § *Rules a profile must satisfy*: five rules, each with the pipeline behaviour that depends on it and the symptom when it breaks, plus the cost of not enforcing them in Decisions. **Not a code task.** The 392-line suite it replaces is still on disk — R3 deletes it. The standing check is that T9 and **T32** each carry rule tests for their own profile | the spec section; T9's and T32's *Verify* lines |
| T6 | Guard tests | Import graph (no concrete axis reaches `shared/` or `pipeline/`); no re-implementation (no local hash, JSONL, atomic-write, JSON-extract, template or retry helper, and none of the four banned imports); toolkit boundary (the library's own `consumer_smoke.py`, cloned at the pinned tag because it is not in the wheel) | `test_import_graph.py`, `test_no_reimplementation.py`, `tests/integration/test_toolkit_boundary.py` |
| T7 | `text` modality | Turns become text parts with roles preserved and text byte-identical; `model2vec potion-multilingual-128M` embeddings, deterministic across runs; an escaped display control that never interpolates corpus text into markup. `personal_data_detectors` returns nothing until T13 | `test_text_modality.py`, `tests/integration/test_text_retrieval.py` |
| T8 | `tool_decision` catalog format, both directions | The `TOOLS:` block read into a tool name, **one verbatim `description`** and a JSON Schema of parameters, and rendered back — all 21,172 corpus catalogs round-trip byte-identically. Every marker token survives verbatim. `group_key` is the catalog fingerprint, never `source_index`. A malformed block yields `empty_catalog`, not an exception | `test_catalog_format.py`, `test_build_record.py`, `tests/integration/test_tool_decision_corpus.py` |
| T9 | The answer contract | `answer_schema` per record (that record's catalog as an `enum`), `answer_distance` with `δ(∅,∅)=0` returned before the division, `vote_consensus` as the strict-majority set, the four named validity checks, and a `training_example` that states the answer twice and asserts the two equal | `tests/unit/test_answers.py`, `tests/unit/test_tool_decision.py` |
| T10 | `dataforce profile` | Streams the 126 MiB source — peak allocation a fraction of it — and writes `metrics/corpus_profile.json` beside the source SHA-256. CI fails on drift and names the count that moved; pointed at the 2026-08-17 backup it reports `label_assistant_mismatch = 48` and fails | `tests/integration/test_corpus_profile.py` |
| — | Declared config *(unplanned)* | `shared/manifest.py`, `shared/prompts.py` — **E2 moved both to `declared/`, leaving the `Manifest` type behind in `shared/`** — `config/modalities/text.yaml`, `config/profiles/tool_decision.yaml`, `config/prompts/profiles/tool_decision/question.v1.txt`, and three JSON Schemas for the input shapes. Delivered without a task in the plan; recorded here so the tree and the plan reconcile | `test_manifests.py`, `test_prompts.py`, `tests/integration/test_input_schemas.py` |

## The measurements Phases 1 and 2 were verified against

**Read the scope of this table before using a number from it.** These describe **one reference source** — the file Phases 1 and 2 were built and checked against, whose answer is a bare array of tool names. It is not the input this pipeline is being built for; core requirements 70–75 and Phase 2C say what that is. So a number here is evidence that the code works on a real file at real size, and it is **not** a threshold a later task may declare against. A task that needs an expected count measures the source it will actually run on and declares it in `params.yaml`, the same way this one was.

That distinction is the correction this pass makes to the plan. Six of the rows below were cited by later tasks as if they described the corpus those tasks would run on, which is how a plan quietly overfits to whatever was measured first: the zero-label stratum in T20, the token estimate in T18, the gold set in T25 and the fingerprint groups in T15 and T29 all read a number from this table. Each of those citations is now marked as an *order of magnitude to plan against*, not a value to gate on.

All from `metrics/corpus_profile.json`, which is what CI pins — see shared decision 13.

| Measurement | Value | Depended on by |
|---|---|---|
| Records | 21,172 | sizing only — every gate declares its own count in `params.yaml` |
| Answer cardinality 0 / 1 / 2 / 3 | 7,498 / 10,596 / 2,757 / 321 | T20's stratum design — the *shape* (an empty answer is common and is a real answer), not these proportions |
| Distinct tool names in labels | 14,411 | profile Decisions — no fixed class space, so no Confident Learning |
| Distinct catalog fingerprints | 17,583 — 16,276 singletons, largest group 112 | T15, T29 |
| Distinct `meta` key-sets | 22 | T8's fixture coverage |
| Labelled by `gemma-4-31B-it` | 14,241 (67.3%) | T18 (no `gemma` juror on primary duty), T31 |
| Records a person already checked | 951 | T25 — that a gold set has to come from somewhere and this pool is biased, not that it is 951 |
| Total prompt characters | 100,557,297 | T18's token estimate — an order of magnitude for budgeting, re-measured before any jury run |
| All four validity counts | 0 | T12 — that a check reading 0 is the tripwire. C2 adds a fifth check, so the set is not closed |

Three of these nine were wrong in the profile spec's table and are corrected in this pass: fingerprints were quoted as 17,596 with 16,293 singletons, key-sets as 13, and prompt characters as 100,557,307. The profiler fingerprints the **parsed** catalog where the earlier probe hashed raw block text, which collapses thirteen pairs differing only in formatting — the smaller number is also the right one, because `group_key` is that same parsed fingerprint. Two further figures in that table were wrong and are corrected with them: catalog size is 1–20 tools rather than 0–20, which is the direct reason `empty_catalog` reads 0, and the 491 duplicate user turns are 491 *groups* covering 982 records.

**What Phase 2 left open, deliberately.** `privacy_signals` in the corpus profile is an empty object: the detectors arrive with T13, which fills it, and the drift test pins the five counts from then on. Until then the drift test pins seven figures rather than every figure in the file.

---

# Phase 2R — Revision: names, file grouping, and one deletion

**Goal:** the code that exists becomes readable by someone who did not write it — every member named for what it returns, every module one step of the workflow, and 392 lines of generic checking replaced by a table in the spec.

**Why here and not later.** All three changes get more expensive with every stage added. Today two implementations and no stages call these names; after Phase 3 there are five stages, after Phase 4 seven. The rename is a mechanical diff now and a coordinated one later. Nothing in this phase changes behaviour, and no test of the profile or the core is lost: R3 removes only the tests that tested the deleted suite, and R1 and R2 change no count at all. Same assertions, same corpus counts.

**Order: R3, then R1, then R2.** R3 first because it is pure deletion, and because `conformance.py` and `tests/conformance/test_suite.py` are 590 lines that reference `delta`, `consensus` and `adapt` — renaming them and then deleting them is work done twice. R1 before R2 so a rename lands in the file it currently lives in and `git` can follow the move separately, which keeps two reviewable diffs instead of one that is both.

**Blocked by.** T10. **Blocks.** T11 — no stage should be written against the old names.

## R1 · Rename every function so its name contains its result

**Goal.** No function in the profile or either contract is named for an operation without its object, and no function shares a name with a stage.

**Context.** Three defects, one of them objective. `load` and `export` were also the names of stages 0 and 13, so a sentence mentioning either was ambiguous — `load` appears ten times in the core spec and most of them are the stage. `adapt`, `parse`, `of` and `label_of` name an operation with no object, so they mean nothing read alone: *parse what, into what?* And the file names have the same problem — `catalog.py`, `adapter.py`, `source.py`, `checks.py` name a topic rather than contents.

The convention is not invented for this task. The corpus generator already had it: `tools_to_catalog`, `tool_to_block`, `build_system_prompt`, `to_strict_openai`, `render_params`. **Every name contains its result**, with a verb in front only when the bare noun would be ambiguous.

**Relevant files.** `src/dataforce/modalities/base.py`, `src/dataforce/profiles/base.py`, both registries, `modalities/text/`, `profiles/tool_decision/`, `cli.py`, every test module, `docs/profiles/tool-decision/spec.md`, `README.md`.

**Proposed approach.** No signature changes. The contracts:

| Contract | Was | Is | Returns |
|---|---|---|---|
| Modality | `load` | `content_parts` | `list[Part]` |
| Modality | `embed` | `embedding` | `Sequence[float]` |
| Modality | `privacy_detectors` | `personal_data_detectors` | `list[Detector]` |
| Modality | `display_control` | `display_config` | `UIControl` |
| Profile | `adapt` | `build_record` | `Record` |
| Profile | `delta` | `answer_distance` | `float` |
| Profile | `consensus` | `vote_consensus(votes)` | `Answer \| None` |
| Profile | `question` | `question_text` | `str` |
| Profile | `answer_control` | `answer_config` | `UIControl` |
| Profile | `export` | `training_example` | `dict[str, Any]` |

`validity_checks`, `group_key`, `answer_schema`, `name`, `version` and `modality` are unchanged; each already contains its result. `build_record` takes the verb because `record` alone is the name of the argument nearly every other function here already receives.

Inside the profile:

| Was | Is | Lands in |
|---|---|---|
| `catalog.render` | `tools_to_catalog` | `utils.py` — **done** |
| `catalog.parse` | `catalog_to_tools` | `utils.py` — **done** |
| `catalog.render_system_prompt` | `build_system_prompt` | `utils.py` — **done** |
| `catalog.as_function` | `to_strict_openai` | `utils.py` — **done** |
| `adapter.catalog_names` | `catalog_names` | `utils.py` |
| `adapter.catalog_fingerprint` | `catalog_fingerprint` | `utils.py` |
| `adapter.answer_space_for` | `answer_space` | `schema.py` |
| `answers.delta` | `answer_distance` | `answer.py` |
| `answers.consensus` | `vote_consensus` | `answer.py` |
| `export.export` | `training_example` | `answer.py` |
| `SourceContract.of` | `read_source_contract(manifest)` | `source_contract.py` — **done** |
| `contract.label_of` | `contract.read_label` | `source_contract.py` — **done** |
| `contract.role` / `contract.field` | `role_name` / `field_name` | `source_contract.py` — **done** |
| `adapter.adapt` | `build_record` | `build_record.py` |
| `adapter.catalog_of` | `read_catalog` | `build_record.py` |
| `profiler.measure` | `corpus_measurements` | `measure_corpus.py` |
| `profiler.drift` | `moved_measurements` | `measure_corpus.py` |

The rename landed in three sittings. The `source_contract.py` rows went first, when the manifest was simplified and every one of their call sites was being rewritten anyway. The four `tool_schema.py` conversions came next and alone, because they are the generator's own names and the two codebases were disagreeing about what one conversion is called: `catalog.py` is now diffable against `openai_to_catalog.py` and `catalog_to_openai.py` one conversion at a time. Nothing in the conformance suite touched those four, so they did not have to wait for R3. `catalog_to_tools` is deliberately the exact inverse of `tools_to_catalog`, which is what a round-trip test reads as. The rest went after R3, in one diff. The **Lands in** column is R2's, not this task's: every function above is still in the module it started in.

**Done.** Fourteen names in this sitting and twenty-two across the task, with no signature change but one — `vote_consensus(votes)`, where the parameter was `answers` and the profile already called it `votes`. Both contracts read as their return values, and `tests/unit/test_protocols.py` pins the two new member sets as literals. Two guards arrived in `tests/unit/test_naming.py`, both of which fail on the tree they were written against: three functions shared a name with a stage (`load`, `embed`, `export`) and six were bare operations (those three plus `adapt`, `measure`, `drift`). They read the fifteen stage names out of the core spec's own stage table rather than repeating them. **251 tests → 253**, the two being those guards; nothing else moved, and `metrics/corpus_profile.json` is byte-identical after `dataforce profile`.

The guards scan `modalities/` and `profiles/` — the scope of this task's goal, and not a clean bill for the rest: `manifest.load`, `prompts.load` and `prompts.render` break both halves of the convention today, in `shared/`, where no contract and no profile is involved. Renaming those three is a separate call, and the guard's own docstring says so rather than leaving the omission to be discovered.

**Acceptance criteria.**
- `Modality.__protocol_attrs__` and `Profile.__protocol_attrs__` contain none of the ten old names, and `tests/unit/test_protocols.py` pins the new sets as literals.
- No function name equals a stage name. A test asserts the two sets are disjoint, reading the stage names from the spec's stage table.
- No single-word function name that is a bare operation survives in `src/`: `adapt`, `parse`, `of`, `render`, `export`, `load`, `embed`, `measure`, `drift`.
- No behavioural change: the same test count as after R3, all passing, and `metrics/corpus_profile.json` byte-identical after `dataforce profile`.

**Source.** core requirements 1, 2; core § The two contracts; core Decisions (*Every contract member is named for what it returns*); shared decision 10.

**Verify.** `make check && uv run dataforce profile --profile tool_decision && git diff --stat metrics/corpus_profile.json`

**Out of scope.** Record field names. `group_key`, `label`, `answer_space` and `meta` stay as they are — renaming a field means rewriting artifacts, and no artifact exists yet to make it free.

## R2 · A module is a definition or a step, and its name says which

**Goal.** Nine modules in the profile become seven, each named for its contents, and only three of them are used by more than one step of the flow — the three that define a noun.

**Context.** Two review findings. First, the file names name topics rather than contents: `catalog.py`, `adapter.py`, `source.py`, `checks.py`. Second, and the real one: *"why the files attend in many state? i dont want it."* Today `adapter.py` is used by four parts of the flow, `answers.py` by four, `catalog.py` by two — so following one step means opening files that also belong to three other steps.

The resolution is to say which kind each module is, because the two kinds have opposite rules. A **definition** defines one noun and every conversion of it, and is *supposed* to serve many steps: a definition used in one place is not a definition, it is that step. A **step** serves exactly one step of the flow and nothing else. Once that line is drawn, the answer to "why does this file turn up in four states" is: only definitions do, there are three, and each is named for the noun it defines.

**Relevant files.** `src/dataforce/profiles/tool_decision/`, `src/dataforce/shared/schemas/`, `src/dataforce/pipeline/`.

**Proposed approach.**

| Module | Kind | Holds | Lines |
|---|---|---|---|
| `tool_schema.py` | definition | what a tool is and every conversion of it — `tools_to_catalog`, `catalog_to_tools`, `build_system_prompt`, `to_strict_openai`, `catalog_names`, `catalog_fingerprint`, and the `Tool` / `Catalog` / `Gap` types. Absorbs `catalog.py` (449) and the catalog half of `adapter.py`. *Since split: the conversions are `utils.py`, the three types are `schema.py`* | ~505 |
| `answer.py` | definition | what an answer is — `answer_schema`, `answer_space`, `answer_distance`, `vote_consensus`, `training_example`. Absorbs `answers.py` (61) and `export.py` (37) | ~110 |
| `source_contract.py` | definition | what this corpus calls things, read from the manifest. Was `source.py` | ~120 |
| `build_record.py` | step | stages 0–1 — `build_record`, `read_catalog`, `validity_checks`, `max_answer_cardinality`, `group_key`. Absorbs the rest of `adapter.py` and `checks.py` (121) | ~330 |
| `ask_annotator.py` | step | stages 7–8 — `question_text`, `answer_config`, `readable_catalog`. From `profile.py` | ~85 |
| `measure_corpus.py` | tool | `dataforce profile`. Not in the flow at all: it reuses stage 0 to count things. Was `profiler.py` | ~280 |
| `__init__.py` | — | the profile object, and nothing else. The front door is the index | ~120 |
| `schemas/` | — | **kept as a folder.** JSON Schema per input shape, read by tests rather than imported | 3 files |

`validity_checks` gets no module of its own: it serves stage 1 and nothing else, so it sits beside the stage-0 code that produces what it checks. That is the review instruction — *"the checks.py if only use for 2, do not split to file"* — as a general rule rather than one exception.

Outside the profile: `shared/schemas/` stays a package split by pipeline phase (14 modules → `base.py` plus one module per pipeline phase, of which there are four), so a stage imports its own phase and nothing else, and `schema_for(name)` still resolves all of them by name for the round-trip test that must iterate every artifact. `shared/manifest.py` and `shared/prompts.py` stay apart — a caller that wants a prompt has no business importing manifest loading. (E2 moved both into `declared/`; the reason they stay two modules is unchanged.) The eight empty `pipeline/**/__init__.py` are deleted until a stage needs them.

**Done.** **48 modules → 30.** The profile's nine became seven, `shared/schemas/`'s fourteen became six, and the eight empty `pipeline/**/__init__.py` are gone until a stage needs them.

The definitions are the modules with more than one importer, and that is checked rather than claimed: `schema` has four, `source_contract` and `utils` three each, `answer` two, and every other module in the package has one or none. Both step modules are imported by `__init__.py` and by nothing else. `measure_corpus` reads the front door the way `cli.py` does — which is the one thing this task added that the table above did not name: `PROVENANCE_KEY` is re-exported from `__init__.py`, because it is what the load stage stamps and a tool that fakes stage 0 has to spell it without importing a step.

`profile.py` became `__init__.py` (77 lines), so the object *is* the index: every member is one line naming the module that does the work. The cost is one delegation per member — `question_text` and `answer_config` were 20 lines of behaviour on the class and are now two lines there and one file for stages 7–8. Actual sizes against the estimates: `tool_schema.py` 482 (~505), `build_record.py` 247 (~330), `measure_corpus.py` 288 (~280), `source_contract.py` 120, `answer.py` 110, `ask_annotator.py` 80.

One split that reads oddly and is deliberate: `schema.py` writes the answer space and `utils.catalog_names` reads it back, because what is read back out of it is a catalog. `answer_space` is about the answer; its inverse is about the tools.

**No behavioural change, four ways.** 220 passing and 33 deselected under `make check`, 253 collected — every count identical to before. `mypy --strict` clean on 30 files. Integration 32 passed, 1 skipped. `dvc repro` up to date, and `metrics/corpus_profile.json` byte-identical after `dataforce profile` over all 21,172 records, with zero measurements moved.

Two test modules were renamed with the source modules they test: `test_catalog.py` → `test_tool_schema.py` (now `test_catalog_format.py`) and `test_tool_decision_adapter.py` → `test_build_record.py`. `tests/unit/test_answers.py` keeps its name, because the core spec names that file. One error in the table above is corrected in place: `shared/schemas/` becomes `base.py` plus **four** phase modules, not five — there are four pipeline phases.

**Acceptance criteria.**
- `find src -name '*.py' | wc -l` reports 30, down from 48.
- Exactly three modules in the profile are imported by more than one step, and each is marked `DEFINITION` in its opening comment with the noun it defines.
- Every step module names the stages it serves in its opening comment, and is imported by nothing but the profile object.
- No module is named for a topic. A reader can predict the contents from the filename.
- No behavioural change: the full suite passes unchanged, `test_import_graph.py` still finds no concrete axis imported from `shared/` or `pipeline/`, and `dvc repro` still reports up to date.

**Source.** core § Repository layout; core Decisions (*A module holds one step of the workflow — and merging stops where the consumers differ*); shared decision 11.

**Verify.** `make check && uv run pytest -q -m integration && find src -name '*.py' | wc -l`

**Out of scope.** Splitting `tool_schema.py`. Its ~505 lines are one grammar in two directions, and the byte-identical round trip over 21,172 corpus catalogs is the proof the directions agree — a split puts the two halves where that proof no longer reads as one thing. It is also the module the generator's `openai_to_catalog.py` and `catalog_to_openai.py` correspond to, and keeping that correspondence one-to-one is what lets the two codebases be diffed.

**Since revised, and the reason above is why it was revised the way it was.** `tool_schema.py` is now `utils.py`, and the `Tool`, `Catalog` and `Gap` types moved to `schema.py` under the rule that a shape belongs in a schema module and a conversion does not. The grammar was left whole: both directions and every format string are still in one module, so the round trip is still one proof and the correspondence with the generator's two modules is still one-to-one.

## R3 · Delete the conformance suite

**Done.** 392 lines of `conformance.py` and 198 of `test_suite.py` are gone; `register()` is an isinstance check and a dict write. **273 tests → 251.** The 28 that went were all tests of the suite: 19 in `test_suite.py`, one running it over every registered profile, four in the profile's own module, four asserting it ran at registration. Six arrived: four for what registration still does, and two for the rules the suite was the only cover for — an answer surviving a JSON round trip, and `consensus` returning the unanimous answer over sampled answers rather than two chosen ones. No test of the profile itself was lost.

**Goal.** `profiles/conformance.py` is gone, `register()` resolves a name and nothing else, and the five rules live in the spec.

**Context.** The suite was built to make "generic" a checked claim, and 95 of its 392 lines were machinery for inventing sample answers out of an arbitrary JSON Schema — written for profiles that do not exist. The review decision is that a rule the author is told to follow is the author's responsibility. **What this costs, stated once:** nothing now fails when `answer_distance` stops being a metric, and the symptom is cohesion numbers that look fine and mean nothing. `tool_decision` keeps that guarantee because `tests/unit/test_answers.py` already proves the metric axioms over random pairs directly — what is lost is the guarantee for the *next* profile, which is why T32 names its absence as the trigger to rebuild the suite.

**Relevant files.** `src/dataforce/profiles/conformance.py`, `src/dataforce/profiles/registry.py`, `src/dataforce/profiles/base.py`, `src/dataforce/shared/errors.py`, `tests/conformance/`, `cli.py`.

**Proposed approach.** Delete `conformance.py` (392) and `tests/conformance/test_suite.py` (198). `register(profile)` becomes an isinstance check and a dict write, returning nothing; `Registration` and `report_for` go with it, and importing a profile no longer runs anything — which also stops a hand-edited manifest from failing at import time. Move `tests/conformance/test_tool_decision.py` to `tests/unit/`, dropping its suite-driven tests and keeping the ones that test this profile directly, and fold `tests/conformance/test_registered_profiles.py` into `tests/unit/test_registries.py`. Rename `ConformanceError` to `InvariantError`: it survives because `training_example` raises it when the two statements of an answer disagree, which is invariant 4 and not conformance.

**Acceptance criteria.**
- No module imports `conformance`, and `tests/conformance/` no longer exists.
- `register()` is under 20 lines and runs no check beyond `isinstance`.
- The five rules are in the spec with their symptoms, and `tool_decision`'s own tests still prove all five.
- The test count drops by exactly the tests that tested the suite, and no test of the profile itself is lost — reported as a before/after count in the commit message.

**Source.** core requirement 6; core Decisions (*Profile rules are stated for the author, not enforced by a shared suite*); shared decision 12.

**Verify.** `make check && uv run pytest -q --collect-only | tail -1`

**Out of scope.** Removing the profile's own answer tests. `tests/unit/test_answers.py` — `test_delta.py` until this task, renamed to the name the core spec already gave it — is now the only thing proving rules 1 to 3 for this profile, so it grew rather than shrank.

---

# Phase 2E — The engine / API split

**Goal:** the engine computes and touches no filesystem, `declared/` is the only package that reads `config/`, `api/` is the surface every caller enters through, and DVC versions data instead of orchestrating it.

**Source:** [`../engine-api-split/spec.md`](../engine-api-split/spec.md).

**Why here, and why now is the only cheap moment.** Two facts. `dvc.yaml` declares **zero stages**, so dropping orchestration is a documentation change today and fifteen stage rewrites after Phase 6. And both axes are constructed at *import* time off a relative path — `TEXT = TextModality(manifest.load(...))` — so the library only works when the process's working directory is the repo root. That is discovered by the first caller who is not the CLI, which is exactly what `api/` exists to be. T11 is the first task that writes a stage, and a stage written against the old layering gets rewritten.

**What is actually wrong, in five places.** `shared/manifest.py:27` `Path("config")`; `shared/prompts.py:29` `Path("config/prompts")`; `shared/gates/runner.py:40` `Path("config/gates.yaml")` plus two files written by `check()`; `build_record.py:57` `Path("params.yaml")`; `measure_corpus.py:39` reads the corpus and reads and writes `metrics/corpus_profile.json`.

**E1–E4 change no behaviour.** Each is a move or an injection and the same assertions pass. E5 adds two guards, E6 adds a surface.

**Done, in five commits rather than six.** E2 and E3 landed together: making `root` a required parameter is what breaks `TEXT = TextModality(read_manifest(...))`, because the import-time call has no root to pass, so splitting them would have meant writing `Path("config")` inline at both singleton sites and deleting it one commit later. **253 tests → 264**, all of them added rather than changed: one in E1, one in E4, three in E5, six in E6. **30 source modules → 35** — one `Registry` replacing two, three in `declared/`, three in `api/`. `metrics/corpus_profile.json` is byte-identical after every one of the five, with zero measurements moved.

Two things the source documents did not account for, both found in the code and recorded in the commits that fixed them. `Manifest` had to stay in `shared/` while only its reader moved, because invariant 4 forbids the engine importing `declared/` and three engine modules need the type; this is the one place R2's "a definition owns every conversion of its noun" and the layering rule disagree, and the layering won. And `ask_annotator.question_text` was a **sixth** I/O site, missed by the spec's table of five because it was indirect — `prompts.render(version, ...)` read `config/prompts` from inside the engine — which is why `prompts.render` is deleted rather than renamed to `fill_prompt`: once a profile is handed its template, nothing reads a prompt by version and then fills it.

| # | Task | Blocked by |
|---|---|---|
| E1 | One `Registry`, no module-level registry state | — |
| E2 | `declared/` — the only package that reads `config/` | E1 |
| E3 | No import-time singleton; the CLI is the composition root | E2 |
| E4 | The last three I/O sites, and gates that write nothing | E3 |
| E5 | The two guards that keep the engine shut | E4 |
| E6 | `api/` — the published surface, and `cli.py` becomes a shell | E5 |

## E1 · One `Registry`, no module-level registry state

**Done.** `0ff3735`. Both 40-line axis registries collapse into one `Registry` class holding instance state for both, and `tests/conftest.py` loses the autouse `_isolated_registries` fixture — a deletion rather than a rewrite, since there is no longer global state to leak. Two explicit methods rather than one `register(impl)`: dispatching on isinstance would have to guess which axis a bad object *meant* to be, and a class missing `display_config` would get "neither a Modality nor a Profile" instead of the member list it lacks. **253 tests → 254**, the one being two registries in one process holding different implementations on both axes.

**Goal.** Two `Registry` objects can hold different profiles in one process, and no registration leaks between tests without a fixture to contain it.

**Context.** `modalities/registry.py` and `profiles/registry.py` are the same 40 lines twice over a module-level `_REGISTRY: dict`. `tests/conftest.py` carries an autouse fixture whose docstring says why: *"Registration is process-global; a test that registers must not leak."* One process serving two configurations is exactly what an `api/` package invites, so the global has to go before the surface arrives — and the fixture disappears with it, which is a net simplification rather than a cost.

**Relevant files.** `src/dataforce/modalities/registry.py`, `src/dataforce/profiles/registry.py`, new `src/dataforce/shared/registry.py`, `cli.py`, `tests/conftest.py`, `tests/unit/test_registries.py`, `tests/unit/test_import_graph.py`.

**Proposed approach.** One `Registry` class in `shared/registry.py` with instance state, holding both axes: `register(impl)`, `modality(name)`, `profile(name, *, modality=None)`. The modality-mismatch hard stop moves onto `Registry.profile` unchanged — it is the one thing registration checks and the reason it is not a plain dict. Delete both axis registry modules and the `_isolated_registries` fixture. `cli.py` builds one registry in `_register_implementations`.

**Acceptance criteria.**
- No module-level mutable registry exists anywhere in `src/`.
- A test builds two registries with different profiles and asserts neither sees the other's.
- `test_import_graph.py` still finds no concrete axis imported from `shared/` or `pipeline/` — `shared/registry.py` names neither axis, it takes objects.
- The mismatched-pair error message is unchanged, asserted by the existing test.
- No behavioural change: 253 tests, all passing.

**Source.** engine/api spec requirement 6, Decision *One `Registry` class*.

**Verify.** `make check && uv run pytest -q --collect-only | tail -1`

**Out of scope.** Making registration lazy or discovering implementations by entry point. A registry is handed objects; who builds them is E3's question.

## E2 · `declared/` — the only package that reads `config/`

**Done, with E3, as `8a0d87a`.** See E3 below — the two are one change.

**Goal.** One package reads the `config/` directory and turns it into objects, and every path it takes is a required parameter.

**Context.** `manifest.py` and `prompts.py` sit in `shared/`, which is the engine, and both default to a relative path. `thresholds()` lives inside the gate engine for the same reason. Moving all three into `declared/` is what lets the no-I/O guard in E5 be written without an exemption list. This also closes a debt R1 recorded and deliberately left: `prompts.load` shared a name with stage 0 and `prompts.render` was a bare operation, both exempted because they sat in `shared/` where no contract was involved. They are moving anyway.

**Relevant files.** `src/dataforce/shared/manifest.py`, `src/dataforce/shared/prompts.py`, `src/dataforce/shared/gates/runner.py`, new `src/dataforce/declared/`, `tests/unit/test_manifests.py`, `tests/unit/test_prompts.py`, `tests/unit/test_gate_runner.py`.

**Proposed approach.** `git mv` both modules into `declared/`, and move `thresholds` out of `runner.py` into `declared/thresholds.py`. `root` and `path` become required keyword arguments — every `Path(...)` module constant is deleted, not defaulted. Rename `prompts.load` → `read_prompt` and `prompts.render` → `fill_prompt`; `digest` and `versions` keep their names. `manifest.load` → `read_manifest`. Every `ConfigError` message moves verbatim.

**Acceptance criteria.**
- `declared/` holds three modules and is the only package in `src/` importing `agent_toolkit.file_utils` for config.
- No module-level `Path` constant naming `config/` or `params.yaml` survives anywhere in `src/`.
- `tests/unit/test_naming.py`'s two guards extend to `declared/` and pass — no bare operation, no stage name.
- Every existing config error message is asserted unchanged.
- No behavioural change: 253 tests, all passing.

**Source.** engine/api spec requirements 3, 4; core requirement 67.

**Verify.** `make check`

**Out of scope.** Changing what a manifest declares, or the prompt-version scheme. `prompt_version` is still the path.

## E3 · No import-time singleton; the CLI is the composition root

**Done, with E2, as `8a0d87a`.** The criterion the pair exists for: `cd /tmp && python -c "import dataforce.profiles.tool_decision"` succeeds, where the deleted default gave `ConfigError - no manifest at config/modalities/text.yaml; modalities declared here: []` from the same directory. `declared/` holds `manifest.py`, `prompts.py` and `thresholds.py`, every path a required keyword argument, and `CONFIG`, `PROMPTS` and `GATES_CONFIG` are deleted rather than defaulted. Eight test modules moved one import each to `conftest`, which builds both axes once through the same composition root every caller uses. **254 tests, unchanged.**

**Goal.** Importing a concrete modality or profile reads no file, and works from any working directory.

**Context.** `TEXT = TextModality(manifest.load("modalities", MANIFEST_NAME))` and `TOOL_DECISION = ToolDecisionProfile(manifest.load("profiles", MANIFEST_NAME))` run at import. This is the single fact that makes `api/` impossible today: a web handler importing `dataforce` fails on a relative path. Eight test files import a singleton, and they are the whole blast radius.

**Relevant files.** `src/dataforce/modalities/text/__init__.py`, `src/dataforce/profiles/tool_decision/__init__.py`, `cli.py`, `tests/conftest.py`, and the eight test modules that import `TEXT` or `TOOL_DECISION`.

**Proposed approach.** Delete both module-level constructions; keep `MANIFEST_NAME` on each, since the name is a fact about the implementation. `cli.py` becomes the composition root: read both manifests through `declared/`, build both objects, register them. Add a **session-scoped** `conftest.py` fixture building the same pair from the repo's real `config/`, so each of the eight test modules changes one import to one fixture argument and no assertion moves.

**Acceptance criteria.**
- `python -c "import dataforce.profiles.tool_decision"` succeeds with a working directory that is not the repo root. This is the criterion the whole task exists for.
- No module under `modalities/` or `profiles/` calls `read_manifest`.
- The eight test modules keep every assertion they have.
- No behavioural change: 253 tests, all passing.

**Source.** engine/api spec requirement 2; core requirement 66, core invariant 19.

**Verify.** `make check && (cd /tmp && uv run --project "$OLDPWD" python -c "import dataforce.profiles.tool_decision")`

**Out of scope.** Removing `MANIFEST_NAME`, and any change to what a manifest contains.

## E4 · The last three I/O sites, and gates that write nothing

**Done.** `11ecaf8`. No module under `modalities/`, `profiles/`, `pipeline/` or `shared/` imports `agent_toolkit.file_utils`, calls `open()`, or holds a `Path(...)` literal; the four surviving mentions of `params.yaml` there are `#` comments. `corpus_measurements` also needed `size`, because the measurement carries `source.bytes` and that cannot be recovered from the records. The ceiling became a `ToolDecisionProfile` constructor argument, since `Profile.validity_checks()` takes no parameters — so an undeclared ceiling now fails while the profile is being built, earlier than the property claimed. **254 tests → 255.**

**Goal.** No engine module opens a file, and a gate raises with its verdict instead of writing one.

**Context.** Three sites are left after E2 and E3. `validity_checks` reads `params.yaml` for one integer. `measure_corpus` reads the 126 MiB corpus, reads a baseline and writes it back. `gates.runner.check` writes `metrics.json` and `GATE_FAILED.json` into a directory it is handed. Each is a different shape of the same mistake, and each has an obvious owner one layer up.

**Relevant files.** `src/dataforce/profiles/tool_decision/build_record.py`, `src/dataforce/profiles/tool_decision/measure_corpus.py`, `src/dataforce/shared/gates/runner.py`, `src/dataforce/cli.py`, `tests/unit/test_tool_decision.py`, `tests/unit/test_gate_runner.py`, `tests/integration/test_corpus_profile.py`.

**Proposed approach.** `validity_checks(contract, *, answer_ceiling: int)` — `max_answer_cardinality` moves to `declared/`, and the "read once, not once per 21,172 rows" property is preserved because the caller reads it once. `corpus_measurements(raw_items: Iterable[Mapping], modality, profile, *, digest: str)` — the streaming stays in the caller, which is what keeps the file from being held whole; `source_digest` moves out with it, and `profile_corpus`'s baseline read/compare/write becomes CLI-side until E6 moves it to `api/`. `check(...)` becomes `assert_gates(stage, results) -> None`, raising `GateFailed` with every `GateResult` attached and writing nothing; `require_upstream_ok` moves out of the engine, since reading a marker file is a filesystem check.

**Acceptance criteria.**
- No `open()`, no `Path` literal naming `config/`, `data/`, `metrics/` or `params.yaml`, and no `agent_toolkit.file_utils` import under `modalities/`, `profiles/`, `pipeline/` or `shared/`.
- An undeclared ceiling still fails before the first record, asserted by the existing test.
- `dataforce profile --profile tool_decision` still streams: peak allocation a fraction of 126 MiB, asserted by the existing integration test.
- `metrics/corpus_profile.json` is byte-identical afterwards, with zero measurements moved.
- No behavioural change: 253 tests, all passing.

**Source.** engine/api spec requirements 1, 7; core requirement 66, core § Error Behavior.

**Verify.** `make check && uv run pytest -q -m integration && uv run dataforce profile --profile tool_decision && git diff --stat metrics/corpus_profile.json`

**Out of scope.** Introducing `api/`. E4 pushes I/O up to `cli.py`; E6 gives it a home.

## E5 · The two guards that keep the engine shut

**Done.** `ade6857`. Both were run against `0ff3735` — after E1, before any of this phase's moves — and both failed there. The AST guard scanned 27 engine modules and named exactly the five sites the spec's table listed, with lines; the subprocess guard raised `ConfigError` on `config/modalities/text.yaml`. Docstrings are exempt, which is a decision and not an oversight: three engine docstrings name where the policy lives, and the alternative was rewriting good prose to dodge a guard. The exemption is itself proved on a synthetic docstring, and `conftest.docstring_ids` is now shared with `test_prompts.py` rather than written twice. **255 tests → 258**, no source file changed.

**Goal.** The layering is asserted by a test rather than remembered, and both guards are shown failing on the tree they were written against.

**Context.** R1 proved its two naming guards against `HEAD` before trusting them, and this is the same move: a guard that has never failed is a guard nobody has checked. There were five I/O sites and one import-time construction to fail on.

**Relevant files.** new `tests/unit/test_layering.py`, `tests/unit/test_import_graph.py`, `tests/conftest.py`.

**Proposed approach.** An AST walk over `SOURCE_ROOT` for every module whose path contains `modalities`, `profiles`, `pipeline` or `shared`: no `open(` call, no string literal naming `config/`, `data/`, `metrics/` or `params.yaml`, no import from `agent_toolkit.file_utils`, and no import of `dataforce.api` or `dataforce.declared`. Assert the guarded set is non-empty so it cannot pass vacuously, as `test_import_graph.py` does. The second guard is a subprocess: `python -c "import dataforce.profiles.tool_decision"` with `cwd=tmp_path`, which cannot be written in-process because the module is already imported.

**Acceptance criteria.**
- Both guards fail when run against the tree as it was before E2, demonstrated in the commit message with the sites they name.
- The AST guard names the offending module and the line, not just "a violation".
- Test count rises by exactly the guards added.

**Source.** engine/api spec § Testing Strategy; core invariants 18, 19.

**Verify.** `make check && uv run pytest -q tests/unit/test_layering.py -v`

**Out of scope.** Guarding `cli.py`, `api/` or `declared/` — all three are supposed to do I/O.

## E6 · `api/` — the published surface, and `cli.py` becomes a shell

**Done.** `246296d`. `cli.py` is 108 lines importing `argparse`, `json`, `logging`, `sys`, `Path`, `api` and `DataForceError` — no `read_yaml`, no `write_json`, no `open`, and no call into either axis except through `api/`. **258 tests → 264.** Three deviations, each for a reason found in the code. `registry=None` is dropped from `open_engine`: as specified it could not work, since a second call with the same registry builds new axis objects with the same names and registration correctly refuses them; `Engine.registry` exposes the registry instead. `api.profile_corpus`, not `api.measure_corpus`, because the profile package already has a module of that name and `api/artifacts.py` imports it. And `Engine.policy` holds paths that `run_manifest` digests, because recording digests at read time puts `file_digest` in `engine.py` and `Engine` in `artifacts.py` — a circular import for a difference that shows only if a policy file is edited mid-run. `open_engine`'s `modality=` is optional: a profile declares which one it composes with, so naming a different one is the hard stop and naming none takes the profile at its word, which is what `dataforce profile` needs.

**Goal.** Every caller enters through `api/`, and `cli.py` holds argument parsing, logging setup and exit codes and nothing else.

**Context.** After E5 the engine is clean but the I/O it shed is sitting in `cli.py`, which makes the CLI the only way in. `api/` is what an in-process caller uses, and it is where the run manifest — the thing that replaces DVC's declared dependencies — is written. The surface starts small on purpose: it grows one function per stage as the stage arrives, and today only stage 0's ingredients exist.

**Relevant files.** new `src/dataforce/api/{__init__,engine,artifacts}.py`, `src/dataforce/cli.py`, `tests/unit/test_api.py`.

**Proposed approach.** `api.open_engine(*, modality, profile, config_root, registry=None)` reads both manifests through `declared/`, builds and registers both axes, and returns an `Engine` carrying the resolved pair plus the policy it read. `api.build_records(engine, raw_items)` and `api.measure_corpus(engine, source)` are the surface that exists today. `api/artifacts.py` is the only place an artifact is read or written, and it owns `require_upstream_ok`, the gate-verdict files and the run manifest. `api.run(engine, stages)` lands with T11, when there is a stage to sequence. `cli.py` keeps `_parser`, logging setup and exit codes.

**Acceptance criteria.**
- `cli.py` contains no `read_yaml`, no `write_json`, and no call into a profile or modality other than through `api/`.
- A test drives `api.build_records` end to end with no filesystem at all — raw dicts in, records out.
- `api.open_engine` with a `config_root` in a tmpdir works from any working directory.
- The run manifest records every policy file's SHA-256 and both axes' `name@version`, asserted on a fixture.
- `dataforce profile --profile tool_decision` behaves identically; `metrics/corpus_profile.json` byte-identical.

**Source.** engine/api spec requirements 5, 8, 9; core requirements 68, 69.

**Verify.** `make check && uv run pytest -q -m integration && uv run dataforce profile --profile tool_decision && git diff --stat metrics/corpus_profile.json`

**Out of scope.** The HTTP service — a later task wrapping `api/` without touching the engine. `api.run` and stage sequencing, which arrive with T11. Replacing `shared/schemas/`, which is its own spec.

# Phase 2C — Revision: the answer is compound

**Why this phase exists.** Phases 1 and 2 were built and verified against a source whose answer is a bare array of tool names. That is not the input this pipeline is for: a tool-decision answer is a set of **calls**, each with the arguments it is called with, and a conversation runs as many turns as it takes. Core requirements 70–75 specify that; this phase is the delta between them and the code.

It is a revision phase rather than a set of Phase 3 tasks for the same reason 2E was: **fourteen of the fifteen stages are written in terms of the answer type.** δ, consensus, the capture control, α, the triage buckets and the export assertion all read it. Changing it after the first stage exists means changing the stage too, and changing it after the jury has run means throwing away votes. It is cheapest now and it gets more expensive every task.

**Task numbers use C so the tasks after this phase keep the numbers they were planned under** — the same rule as 2R and 2E.

**What is *not* in scope.** Nothing under `pipeline/` or `shared/` changes. That is the two-axis design paying off and it is also the check on this phase: a diff that touches the generic core means the answer type leaked out of the profile, and the fix is in the profile.

## C1 · A turn that carries a call becomes one canonical part

**Goal.** `content_parts` renders a `tool_calls` turn into one text part holding canonical JSON, so a call is a turn like any other and `rid` is reproducible.

**Context.** Today `content_parts` does `turn["content"]` and builds a `TextPart` — verified failure modes: `ValidationError` on `"content": null`, `KeyError` when the key is absent. Core requirement 70 settles the shape and *Decisions* settles why it is not a new part type: the part `type` discriminates kinds of content, and a modality that started reading arguments would have acquired an opinion about what an answer is.

**Relevant files.** `src/dataforce/modalities/text/__init__.py`, `tests/unit/test_modalities.py`.

**Proposed approach.** One rule in `content_parts`: a turn with no string `content` and a `tool_calls` array renders to `json.dumps(calls, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, with each call reduced to `{"name": …, "arguments": {…}}` and `arguments` parsed first if the source spelled it as a JSON string. Nothing else about the modality changes. A turn with neither a string nor calls is still an error — it is a source-layout problem and requirement 70 does not license guessing.

**Acceptance criteria.**
- One call spelled three ways — reordered keys, added whitespace, `arguments` as a string versus an object — yields one part, one digest and one `rid`. Invariant 2.
- A multi-turn record with `role: "tool"` turns builds, embeds and displays; `tool` needs no declaration to be carried, only to be read by meaning.
- The names-only source still produces byte-identical parts. Nothing about a string turn changes.

**Verify.** `uv run pytest tests/unit/test_modalities.py tests/unit/test_build_record.py`, then `make check`.

**Out of scope.** Parsing the call into an answer — that is C2. This task only renders.

## C2 · The answer type: calls with arguments, and the space that constrains them

**Goal.** `answer_schema` and `answer_space` describe a set of calls, each name from the record's catalog and each argument set validating against that tool's own `parameters`.

**Context.** Core requirement 71. The catalog already carries `parameters` per tool — `Tool.parameters` is a JSON Schema and `to_strict_openai` already emits it — so the argument space is data the record already has, not something new to declare. This is also where requirement 73's check lands: one call per tool name per answer.

**Relevant files.** `src/dataforce/profiles/tool_decision/schema.py`, `utils.py`, `build_record.py`, `tests/unit/test_build_record.py`, `tests/unit/test_tool_decision.py`.

**Proposed approach.** Two functions, and the split between them is requirement 71. `answer_space(catalog)` stays what it is — the names, 136 bytes, the cheap index `group_key`, three checks and the capture control read. A new `answer_schema_for(record)` materialises the full constraint at the point of use: `oneOf` per tool, `name` a single-value `const`, `arguments` that tool's `parameters` read out of the catalog the record already carries. Nothing persists it, so no artifact grows. `catalog_names` is unchanged, which is why `group_key` and the fingerprint are untouched. A fifth validity check, `label_names_one_tool_twice`, is added to `CHECK_NAMES` and to `params.yaml`'s declared counts.

**Acceptance criteria.**
- An answer whose call names a tool the record offered and whose arguments satisfy that tool's schema validates; one violating either does not, and the pull gate rejects rather than truncates it — invariant 5.
- **No artifact grows.** `answer_space` on a built record is byte-identical to what it is today; the compound schema exists only inside the call that needs it. Asserted on a record with an eight-tool catalog, where the materialised schema is larger than the catalog itself.
- `catalog_names(record)` returns the same names as before for a record built either way. `group_key` unchanged.
- A record naming one tool twice is quarantined under the new check's name; the check appears in `params.yaml` with a declared count.
- The existing quarantine-not-crash behaviour holds: an answer of the wrong shape entirely is still reported by a named check, never a `TypeError`.

**Verify.** `make check`, then `uv run pytest -q -m integration`.

**Out of scope.** δ and consensus — C3. The capture control — C4.

## C3 · δ and consensus over a compound answer

**Goal.** `answer_distance` distinguishes a wrong tool from a right tool with one differing argument, and `vote_consensus` assembles a call only when it can assemble it fully.

**Context.** Core requirements 72 and 74, and the *Decisions* entry that rejects both simpler alternatives. This is the task with the most downstream reach and the least code: every cohesion figure, every triage bucket and every α reads it, and it is one function plus a consensus rule.

**Relevant files.** `src/dataforce/profiles/tool_decision/answer.py`, `tests/unit/test_answer.py`.

**Proposed approach.** Name-first: over the union of names, a matched name contributes the share of argument keys present in both and equal (two argument-less calls contribute 1), an unmatched name contributes 0, and δ is one minus the mean. Consensus: strict majority per name, then strict majority per argument key, and a call missing a `required` key with no majority is dropped rather than completed.

**Acceptance criteria.**
- Hand-worked: `0 = δ(same call) < δ(same tool, one argument differs) < δ(different tools) ≤ 1`.
- Profile rule 1's four properties hold on the compound type, including on the empty answer. The triangle inequality is not asserted — requirement 4 says why.
- **Reduction:** when every matched call has identical arguments, δ equals Jaccard over names to the bit, over the same vote sets the names-only implementation was measured on. This is the assertion that proves the old behaviour is a special case rather than something replaced.
- A 2–1 split on one argument value yields the majority value; a required key with no majority drops the call and does not half-build it.

**Verify.** `make check`. The α degenerate case against `krippendorff` still passes — T19 depends on δ being an arbitrary distance, and this is the first proof that it really is.

**Out of scope.** Weighting a record's calls by anything other than the mean over the union of names. Requirement 72 records that the mean is a choice; changing it is a threshold decision with its own task, not a refinement of this one.

## C4 · Capturing a compound answer, and the declared fallback

**Goal.** `answer_config` captures a name and that name's arguments, or the declared JSON fallback, with which one shipped recorded on the project.

**Context.** Core requirement 75. `<Choices>` captures a name and nothing else, so this is the first place the annotation tool may not be able to express the answer space — and the fallback has to be specified before T22 builds a project against it, because it changes what an annotator can physically express and therefore what their agreement means.

**Relevant files.** `src/dataforce/profiles/tool_decision/ask_annotator.py`, `tests/unit/test_ask_annotator.py`.

**Proposed approach.** Generate the per-name argument fields from each tool's `parameters` where the tool supports conditional visibility; otherwise one text control capturing JSON, validated at pull time against C2's schema. Either way the payload allowlist is unchanged — invariant 10 does not soften because the control got richer.

**Acceptance criteria.**
- A generated config validates against a live Label Studio instance, and a submitted answer pulls back inside the record's answer space.
- The fallback path rejects an out-of-space answer at pull time rather than truncating it — invariant 11.
- Which control shipped is on the project record.
- No model output in the payload. Invariant 10's allowlist test still passes on the built payload.

**Verify.** `make check`, then the Label Studio integration test.

**Out of scope.** Deciding which control ships. That is a measurement on a live instance, and T22 owns it.

---

# Phase 3 — `data_quality` over the real corpus

**Goal:** 21,172 records become a usable corpus — personal data found and reported, near-duplicates grouped, and nothing downstream matching a personal-data pattern. Five DVC stages, five gates, and the first working `dataforce run`.

**Re-sized since the first plan.** This phase was written expecting ~1,563 quarantined records, 7.4%. The catalog reader settled that: all four validity counts read **0**, because the 841 and 722 in the profile spec were artifacts of a stricter tool-name pattern than the reader ships with. `remove_invalid` therefore moves roughly nothing, and the phase's value moves with it — from *filtering* to *privacy and duplicates*. The checks stay as gates: one reading 0 is what tells you when it stops.

## T11 · `load` stage and `dataforce run`

**Goal.** Stage 0: raw source → canonical records with the source version pinned, reachable through the command the spec advertises.

**Context.** This is the first task that has to resolve a `modality × profile` pair and stamp it, so it is where `dataforce run --modality text --profile tool_decision` stops being a stub. No earlier task owned that command, which is why it lands here rather than in Phase 1: an entry point with nothing to run is not testable.

**Blocked by.** 2E — a stage written against the old layering would read `params.yaml` off a relative path and be rewritten. R2 settled the names and the modules; 2E settles who reads files and who orchestrates. **And 2C**: this stage calls `content_parts` and `build_record` on every record, so it has to be written against the answer type it will keep, not the one it would then be rewritten for.

**Relevant files.** `src/dataforce/pipeline/data_quality/load.py`, `src/dataforce/api/`, `src/dataforce/cli.py`.

**Proposed approach.** Stream via `iter_json_array_file` or the modality's loader; never load whole. Record per-record provenance: source file SHA-256, byte offset, the raw record verbatim, modality and profile `name@version`, ingest timestamp. Unparsable records are carried with `parse_status = "unparsed"` and their raw text — nothing is dropped. `api.open_engine` resolves both axes from a `Registry` and hard-stops on a mismatched pair; `api.run` sequences the named stages. The stage function itself is pure -- records in, records out -- and `api/artifacts.py` reads the source and writes `loaded.jsonl`. `cli.py` holds no stage logic of its own.

**Acceptance criteria.**
- Gate: `parsed + unparsed == source count`, and the source SHA-256 matches `params.yaml`.
- A source SHA-256 differing from `params.yaml` is a hard stop, not a warning — a changed source is a new dataset version decided by a human.
- Every output record carries all five provenance fields, with `producer` as `name@version` for both axes.
- `dataforce run --modality text --profile tool_decision` runs the declared stages; naming a pair the profile does not declare hard-stops before stage 0 opens the source.
- `dataforce run load` twice over one source writes a byte-identical artifact and a byte-identical run manifest. It is not a no-op -- there is no stage cache -- and nothing asserts it is fast.

**Source.** core requirements 7, 13, 14, 17; core § Error Behavior (source SHA-256, profile/modality disagreement).

**Verify.** `uv run dataforce run load && uv run pytest tests/integration/test_load.py`

## T12 · `remove_invalid` stage and `dataforce requeue`

**Goal.** Stage 1: records that fail a provable check leave the main path into `quarantine/invalid/<check>.jsonl`, and can be re-admitted by an explicit command.

**Changed by 2C.** Five checks, not four: `label_names_one_tool_twice` arrives with C2, and its expected count is declared in `params.yaml` with the others. The quarantine names are the check names, so the fifth adds a file rather than changing any behaviour here.

**Context.** Written expecting 1,563 records, 7.4% on the reference source; the measured answer there is **0**, and that changes what this stage is for. It is no longer a saving — it is the tripwire that tells you the source or the reader moved, and it has to exist before the expensive stages so that a future non-zero count stops the run instead of costing 7.4% of the jury's ~101M estimated tokens and then teaching the model something false. Nothing is deleted: "remove" is scoped to the main path.

**Blocked by.** T11.

**Relevant files.** `src/dataforce/pipeline/data_quality/remove_invalid.py`, `src/dataforce/cli.py`.

**Proposed approach.** Run the profile's `validity_checks()`; each failure writes the record to `quarantine/invalid/<check>.jsonl` naming the check it failed and removes it from the main path. Expected counts per check come from `params.yaml`, already populated at 0 from the reader's own run. `dataforce requeue --check <name>` re-admits a class and versions the pipeline.

**Acceptance criteria.**
- Gate: each check's count is within ±10% of its declared number; outside that is a hard stop reporting the delta. With every count declared 0, any non-zero count is a stop.
- `label_assistant_mismatch` rising above 0 is a hard stop — upstream drove it to zero, and a return means a curation step wrote one field and not the other.
- A fixture with one record failing each check asserts each lands in the right quarantine file under the right name, and that the main-path count drops by exactly that many.
- No record is silently deleted and none silently kept: `quarantined + kept == input`.
- `dataforce requeue --check empty_catalog` returns those records to the main path and changes `dvc.lock`.

**Source.** core requirements 15, 16; core invariant 1; profile § Error Behavior; profile § Testing Strategy (Validity gate).

**Verify.** `uv run dataforce run remove_invalid && uv run pytest tests/integration/test_remove_invalid.py`

## T13 · `text` privacy detectors — Vietnamese, literal and spoken form

**Goal.** The modality's fourth member: detectors that find personal data in Vietnamese call-centre transcripts, where it appears in spoken form that no off-the-shelf scrubber detects.

**Context.** Vietnam's Personal Data Protection Law 91/2025/QH15 has been in force since 1 January 2026, with Decree 356/2025/ND-CP as implementing guidance. Redaction here is a legal requirement, not a nicety. The digit-word signal fires on 3,485 records (16.46%) and is a **superset** — it also matches prices, dates and reference codes — so it bounds the population needing review rather than counting personal data.

**Blocked by.** R1 (the member is `personal_data_detectors`).

**Relevant files.** `src/dataforce/modalities/text/privacy.py`, `src/dataforce/profiles/tool_decision/measure_corpus.py`.

**Proposed approach.** Detect phone numbers, email addresses, national ID numbers, bank account numbers and full personal names in the customer turn, in both literal and spoken form: digit words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), spoken `@` (`a còng`), spoken punctuation (`chấm`, `gạch dưới`). Run against both the raw text and `string_utils.normalize_text(text, remove_tone_marks=True)`, so a transcript spelling `khong` or `chin` is not missed while patterns stay written in correct Vietnamese. Offsets resolve back onto the original; the normalized form is a matching aid and is never stored. Return the uniform span shape — a list of typed spans over a named part — so the redaction stage, its report, its vault and its gate are written once. This is also what fills `privacy_signals` in the corpus profile, empty since T10.

**Acceptance criteria.**
- A hand-built fixture of spoken phone numbers, spoken emails and national IDs asserts recall on all three.
- The same fixture's prices, dates and order references assert **no** detection — the LLM layer of T14 is what separates these, but the regex layer must not be the only filter.
- A tone-stripped variant asserts `normalize_text` matching catches `khong chin khong mot`.
- Every returned span's offsets index the original text, verified by slicing.
- Run over the full corpus, the detectors reproduce the five signal counts — 3,485 / 770 / 435 / 238 / 97 — and `metrics/corpus_profile.json` carries them, so the drift test pins them from here on.

**Source.** profile requirements 9, 10; core requirement 11; profile § Personal data in the corpus; profile § Testing Strategy (Vietnamese privacy).

**Verify.** `uv run pytest tests/unit/test_text_privacy.py -v && uv run dataforce profile --profile tool_decision`

## T14 · `pii_check` stage, vault, and `enable_redact`

**Goal.** Stage 2: find personal data, always report it, and replace it only when `enable_redact` says so.

**Context.** The two layers have separate jobs — the regex layer sets recall and is allowed to be noisy, the LLM layer sets precision. Replacement rather than deletion is load-bearing: the ground truth of this corpus turns on whether a required value was *supplied*, so deleting a phone number converts a correct call into what looks like a correct `{hold_missing}`, silently inverting the label on ~2% of records.

**Blocked by.** T12, T13.

**Relevant files.** `src/dataforce/pipeline/data_quality/pii_check.py`.

**Proposed approach.** Layer 1 is the modality's detectors. Layer 2 verifies each candidate through `llm.complete_structured` over a ±80-character window against a fixed classification schema, deciding personal data versus price, date or reference code. **Always** write `pii_findings.jsonl` — every candidate span with its class, its window and the verifier's verdict. A verification response failing its schema leaves the span **unverified, not negative**, and the record is quarantined. With `enable_redact: true`, verified spans become stable typed placeholders scoped per record (`<PHONE_1>`, `<EMAIL_1>`), so a value referenced twice stays co-referent. The placeholder-to-original mapping goes to `data/raw/pii_vault.jsonl`, outside DVC. Reports record per-class counts and a sample of 20 *placeholders in context* — never original values. Checkpoint so an LLM outage resumes with verified spans kept.

**Acceptance criteria.**
- Gate: every high-recall hit is verified or the record is quarantined; zero literal personal-data matches in any release-tier artifact. — core invariant 3
- With `enable_redact: false` the stage reports and leaves content untouched, and the downstream personal-data scan then fails so nothing ships — the default cannot silently release personal data.
- A record mentioning one phone number twice yields `<PHONE_1>` both times.
- A modality with no redactor for a part fails closed: the record is quarantined to `quarantine/pii/`, never advanced.
- A repo test asserts the vault is in `.gitignore`, in no `.dvc` file, and that `data/raw/` is absent from DVC entirely.
- An LLM outage mid-stage resumes from checkpoint without re-verifying settled spans.

**Source.** core requirements 12, 18, 19, 20, 21; core invariant 3; profile requirements 11, 12; core § Error Behavior (privacy rows).

**Verify.** `uv run dataforce run pii_check && uv run pytest tests/integration/test_pii_check.py tests/unit/test_vault_hygiene.py`

**Human step inside this task.** Run with `enable_redact: false` over the full corpus, read `pii_findings.jsonl` — the digit-word signal fires on 3,485 records — tune the patterns and the verification prompt against what it shows, and only then set `enable_redact: true` in `params.yaml`. That flip is a committed change to `params.yaml`, whose digest every run records in its run manifest, so the decision is attributable.

## T15 · `embed` and `dedup` stages

**Goal.** Stages 3 and 4: vectors for every record, and near-duplicates grouped so variants of one scenario cannot straddle a split.

**Blocked by.** T14.

**Relevant files.** `src/dataforce/pipeline/data_quality/{embed,dedup}.py`.

**Proposed approach.** `embed` calls the modality's `embedding` and writes `embeddings.npy`. `dedup` removes exact duplicates on `compute_hash` of the content digest, keeping the record with richer metadata, then finds near-duplicates with SemHash over the embeddings. Cluster members are **not deleted**: they get a shared `dup_cluster_id` and one is marked `is_representative`. Deletion happens at export from an explicit filter. `group_key` is the profile's, unioned with `dup_cluster_id`.

**Acceptance criteria.**
- Gates: embedding row count matches record count; exact duplicates 0; a cluster report is emitted.
- Known duplicate pairs from the corpus land in one cluster — 491 duplicate-user-turn groups covering 982 records, and 1 duplicate (system, user) pair.
- No record is deleted by `dedup`; the count out equals the count in, with cluster fields added.
- `source_index` is rejected as a group key by an explicit test, since it is unique per record and gives no leakage protection.
- The 112-record catalog group shares one `group_key`.

**Source.** core requirements 22, 23, 24; profile § Dedup and grouping tests; profile Decisions (group split).

**Verify.** `uv run dataforce run embed dedup && uv run pytest tests/integration/test_dedup.py`

## T16 · Stub audio modality — the seam test

**Goal.** Prove the modality seam holds without building an audio modality.

**Context.** Typed content parts, media by reference, and the uniform privacy-span shape could not be retrofitted without touching all fifteen stages, so they are in now. This is the seam's only test until a real audio modality exists, and it is what stops the seam rotting.

**Blocked by.** T15.

**Relevant files.** `tests/integration/test_modality_seam.py`, `tests/fixtures/stub_audio/`.

**Proposed approach.** A stub modality returning one audio part with a `uri` and `sha256` and no inline bytes, paired with a trivial profile. Run `load` → `remove_invalid` → `pii_check` → `embed` and assert the stages neither inline the media nor crash. The stub's `personal_data_detectors()` returns nothing for the audio part, which must make `pii_check` fail closed rather than pass the record through.

**Acceptance criteria.**
- The four stages complete or quarantine, and no artifact contains a base64 blob or a non-text part lacking `uri` and `sha256`.
- `pii_check` quarantines the audio record rather than advancing it, because the stub cannot redact it.
- No stage needed a change to accommodate the audio part.

**Source.** core requirements 8, 9, 11, 12; core invariant 4; core § Testing Strategy (Modality boundary).

**Verify.** `uv run pytest tests/integration/test_modality_seam.py`

---

# Phase 4 — `ai_review` at S0

**Goal:** 50 records answered independently by three jurors from three distinct families, cohesion and corpus-conflict computed, and a ranked review queue produced — inside an estimated-token ceiling, with key-pool failover proven.

## T17 · Key pool, traffic controllers, error taxonomy

**Goal.** Dispatch across several API keys that degrades throughput on exhaustion and hard-stops on misconfiguration.

**Context.** Three library facts shape this. `set_config_resolver` installs one process-global resolver keyed by model name, so per-call rotation cannot be expressed through it — credentials are passed explicitly per call, which the library documents as winning over the resolver, and no resolver is installed. `get_traffic_controller` memoizes per (loop, name) and ignores later callers' limits, so controllers are constructed in exactly one place before dispatch. `LLMRateLimitError.retry_after` is never populated, so cooldown is a declared constant.

**Blocked by.** T1.

**Relevant files.** `src/dataforce/pipeline/ai_review/lib/keypool.py`.

**Proposed approach.** Each pool entry carries its own request and estimated-token budget. Pass `api_key=` / `base_url=` explicitly on every call. Back off per key on `LLMRateLimitError`; quarantine a key on `ProviderQuotaExceededError` for the declared cooldown and continue on the rest. `LLMAuthenticationError` and `LLMConfigError` stop the run — a bad key is a configuration defect, and treating it as exhaustion would hide it behind degraded throughput. One `TrafficController` per key group, all constructed before dispatch.

**Acceptance criteria.**
- A 429 on one key and a quota error on another produce votes identical to a single-key run.
- An auth error stops the run instead of quarantining the key.
- All keys in a group exhausted leaves that juror incomplete for the affected records, which keep their votes and are re-queued rather than scored on a partial panel.
- No `set_config_resolver` call exists anywhere in the source.
- Controllers are constructed in exactly one place, asserted by test.

**Source.** core requirement 32; core § Error Behavior (key rows); core § gap table; profile Decisions (key pool lives here).

**Verify.** `uv run pytest tests/unit/test_keypool.py -v`

## T18 · `jury` stage

**Goal.** Stage 5: several models answer the dataset's own task per record, and every vote is valid or a clean abstention.

**Changed by 2C.** The schema handed to `complete_structured` is now per record and per tool — `oneOf` over the catalog, each branch carrying that tool's `parameters` — which is a bigger schema and a stricter one. Two consequences to measure here rather than assume: a provider's structured-output mode may reject or silently flatten a `oneOf` of that size, and the abstention rate is the thing that tells you. Estimated tokens per vote rise with the catalog, so T18's budget is re-estimated after C2 rather than carried over.

**Context.** The answer schema *is* the constraint, enforced inside the library — `info.ok is False` is the abstention, and there is no path where a malformed response becomes a truncated set. The panel must be family-diverse and clean: `model_family` collapses every unrecognised name to `"unknown"`, so a panel containing one is not proved diverse, it is unmeasured.

**Blocked by.** T15, T17.

**Relevant files.** `src/dataforce/pipeline/ai_review/jury.py`, `lib/{panel,vote,consensus,escalate}.py`, `config/panel.yaml`, `config/prompts/jury_vote.v1.txt`.

**Proposed approach.** Call `llm.complete_structured(prompt, profile.answer_schema, mode="prompt", temperature=0)`. `mode="prompt"` is deliberate: under `"auto"`, two jurors on endpoints differing in `response_format` support get different constraint mechanisms and cohesion across them is not a meaningful number. Retry a non-conforming answer **once**, then record an abstention carrying `ValidationInfo.raw`, `.error`, `.repaired`, `.strategy`, and store `.reasoning` whenever the juror emitted any. Cache on `(rid, model, prompt_version)`, excluding the API key. Staged escalation: a 3-juror sweep, then 7 jurors on records showing conflict or low cohesion. The prompt lives at `config/prompts/jury_vote.v1.txt`, asks the task in Vietnamese, and is filled with `slot_filling`.

**Acceptance criteria.**
- Gate: ≥3 jurors over ≥3 distinct families, none `"unknown"`; no juror from the corpus's labelling family except one tagged `control`; estimated tokens ≤ budget; invalid-vote rate ≤ 5% per juror.
- A stubbed endpoint returning a clean array, a fenced array, prose-wrapped JSON, an out-of-catalog name, a non-array and empty each becomes a valid set or a clean abstention, with `repaired` true for exactly the fenced and prose-wrapped cases.
- Panel diversity fails against a one-family config and against a config containing an unrecognised model name.
- Two cold runs over a fixture against a recording proxy produce byte-identical votes; forcing key rotation mid-run changes nothing. — core invariant 7
- Per record: every vote, the consensus, the plurality, `exact_unanimity`, `cohesion = 1 − mean pairwise δ`, `corpus_conflict = δ(consensus, existing_label)`, `est_tokens`.
- Exhausting the token estimate mid-run stops cleanly with cast votes retained and run status `partial`.
- `slot_filling`'s `{{double-brace}}` placeholders leave `{trigger}` and `{hold_missing}` untouched. — profile invariant 1
- No stored vote is a truncation of a malformed response. — core invariant 6

**Source.** core requirements 25–32, 35, 37; core invariants 5, 6, 7, 8; profile requirements 13, 14, 16, 25; profile Decisions (`mode="prompt"`, no `gemma` juror).

**Verify.** `uv run dataforce run jury && uv run pytest tests/integration/test_jury.py -v`

**Out of scope.** Juror weight calibration (needs the gold set — T25). The consensus tier of requirement 34.

## T19 · `agreement.py` — α over any δ, cohesion, plurality

**Goal.** The agreement statistics the jury and the aggregation stages both need, computed over an arbitrary distance.

**Changed by 2C.** δ is now a weighted average and does not satisfy the triangle inequality — core requirement 4 says which four properties are claimed. Nothing here needs it: α, cohesion and corpus conflict read pairwise distances only. This task's acceptance criteria must say so explicitly, because the next person to reach for a clustering or embedding approach over answers is the one who needs to know it is not available.

**Context.** The `krippendorff` package covers nominal, ordinal, interval and ratio scales only, so α over a set-valued distance is written here. Its nominal degenerate case is tested against the library so the implementation is anchored.

**Blocked by.** R1.

**Relevant files.** `src/dataforce/shared/agreement.py`.

**Proposed approach.** α with a pluggable distance — the profile's `answer_distance`, δ in the formulas; cohesion as `1 − mean pairwise δ`; plurality. Nominal α delegates to the `krippendorff` package. Nothing here imports a concrete profile: the distance arrives as an argument.

**Acceptance criteria.**
- α over an arbitrary δ matches a hand-computed example.
- α with an identity distance equals `krippendorff`'s nominal α on the same data.
- Cohesion over hand-worked vote sets matches by hand, including all-abstention and unanimous cases.

**Source.** core requirements 52, 53; profile § Testing Strategy (Set-valued α).

**Verify.** `uv run pytest tests/unit/test_agreement.py -v`

## T20 · `rank_for_review` stage

**Goal.** Stage 6: decide which records a human should look at, and why, with the sampling design reconstructible.

**Context.** Two axes, not one score: a confidently unanimous jury disagreeing with the label is a **label** problem, while a split jury disagreeing with the label is usually a **guideline** problem. They need different people and produce different fixes. Every threshold here is currently a guess, which is why the pilot measures bucket precision before scale depends on it.

**Blocked by.** T18, T19.

**Relevant files.** `src/dataforce/pipeline/ai_review/rank_for_review.py`, `lib/{buckets,strata,sampling}.py`.

**Proposed approach.** Bucket on the two axes into `agreed`, `ambiguous_agreed`, `likely_label_error`, `hard_record`, with thresholds from `params.yaml`. Fill the queue from declared strata with declared quotas, always including a uniform random audit sample and the entire test split. This profile's strata are `likely_label_error`, `hard_record`, zero-label — 7,498 records, 35.4%, deliberately oversampled because it carries the corpus's real difficulty — the audit sample and the test split. Size the audit sample as `n = z²·p(1−p)/e²`, recomputing and requesting more if the observed rate exceeds the assumed `p`. Records with fewer than the minimum valid votes are excluded from triage rather than bucketed on thin evidence.

**Acceptance criteria.**
- Gate: every stratum met its quota; audit `n` ≥ computed.
- Bucket assignment matches a hand-built (cohesion, conflict) grid including boundary values.
- Audit sizing reproduces worked values: `p=0.05, e=0.02 → 457`; the profile default is `n = 500`.
- Every queued record records which stratum selected it and with what probability; the residual-error estimator refuses to run when any lacks one. — core invariant 15
- A record with one valid vote is excluded, not bucketed.

**Source.** core requirements 39–44; core invariant 15; profile requirements 20, 21, 22.

**Verify.** `uv run dataforce run rank_for_review && uv run pytest tests/integration/test_rank_for_review.py -v`

## T21 · Cross-border transfer review — blocking, not code

**Goal.** A written determination of where the corpus and each juror endpoint sit, completed before the first jury run against any offshore endpoint.

**Context.** The jury sends Vietnamese call-centre transcripts to several external LLM endpoints. Both specs name this as a prerequisite rather than a stage, and it is sharper here than in the core because of what the content is. Vietnam's PDPL 91/2025/QH15 and Decree 356/2025/ND-CP are in force.

**Blocked by.** T14, so the review can state whether content is redacted at the point of transfer.

**Proposed approach.** Not a pipeline task. Record, per juror endpoint: the operator, the hosting jurisdiction, the contractual terms on retention and training use, and whether transferred content is redacted. Attach the determination to `docs/` and reference it from the release datasheet.

**Acceptance criteria.**
- Every endpoint in `config/panel.yaml` appears in the determination with a jurisdiction.
- The determination states whether `enable_redact` was on for the content transferred.
- No jury run against an offshore endpoint precedes the determination's date.

**Source.** core § Out of Scope (Cross-border transfer review); profile § Out of Scope.

**Verify.** The document exists, covers every configured endpoint, and predates the first live jury run — checked by comparing its date against `dvc.lock`'s jury stage.

---

# Phase 5 — `human_review`, S0 smoke through S1 pilot

**Goal:** the smoke rung proves the plumbing in one sitting, then two annotators answer ~700 questions over 500 records and the pilot gate passes on all five thresholds. This is where the project learns whether the questions are answerable at all.

## T22 · Label Studio deployment, generated config, payload allowlist

**Goal.** A self-hosted Label Studio whose labeling config is generated by the pipeline, carrying nothing a model produced.

**Context.** The UI config is **composed, not owned**: the modality contributes the control that displays the content, the profile contributes the control that captures the answer, and neither may emit the other's half. This split is why a new modality does not multiply the profiles that already exist. Label Studio Community honouring `maximum_annotations` is an Assumption the smoke rung verifies before anything is built on it.

**Blocked by.** R1 — this is the task that first calls `display_config` and `answer_config`, the two members requirement 3 composes. **And C4**, which decides what the capture half even is.

**Changed by 2C.** This task now owns a measurement it did not have: **whether Label Studio can express per-name argument fields at all.** Core requirement 75 declares the fallback — one JSON text control validated at pull time — so the outcome is not a blocker either way, but which one shipped is recorded on the project because it changes what an annotator could physically express and therefore what their agreement means. Measure it on the live instance before the pilot, not during it.

**Relevant files.** `src/dataforce/pipeline/human_review/labelstudio/{config,client}.py`, `deploy/docker-compose.yml`.

**Proposed approach.** Compose the config from `modality.display_config(record)` and `profile.answer_config(record)`. For this profile the correction control is a dynamic `<Choices value="$tool_choices" choice="multiple">` populated from that record's own catalog plus an explicit "no tool" option, so a correction is a set drawn from the catalog by construction. All content and glossary HTML is built by the pipeline and **escaped**. The published payload's key set must equal an explicit **allowlist** — an allowlist, not a denylist, so a new field cannot leak by being forgotten.

**Acceptance criteria.**
- The generated config validates against a live instance in CI via testcontainers: create project, push three tasks, pull back a submitted annotation.
- The allowlist test runs on the built payload without a server and fails when any extra key appears. — core invariant 10
- Corpus text containing markup renders escaped, asserted on the built config.
- A test confirms `maximum_annotations` produces the expected overlap on a Community instance; if it does not, the fallback of one project per annotator joined on `rid` is implemented instead and the Assumption is struck from the spec.

**Source.** core requirements 3, 46, 47, 48, 49; core invariant 10; profile requirement 23; core Assumption (`maximum_annotations`).

**Verify.** `uv run pytest tests/integration/test_labelstudio.py tests/unit/test_payload_allowlist.py -v`

## T23 · `generate_questions` stage

**Goal.** Stage 7: each queued record becomes one focused, answerable question.

**Blocked by.** T20, T27.

**Relevant files.** `src/dataforce/pipeline/human_review/generate_questions.py`, `lib/questions.py`, `config/prompts/`, `config/templates/`.

**Proposed approach.** Follow `guided-validation`: focus chosen **by rule**, not by the LLM; batch pre-generation; token budget as a hard ceiling; idempotence on `(rid, prompt_version, model)`. For this profile the focus rule is the marker DSL. Prompts are files read with `read_txt` and filled with `slot_filling`; output comes from `complete_structured`, and the question wording itself comes from the profile's `question_text`.

**Acceptance criteria.**
- Gate: schema-valid ≥ 98%, measured from `ValidationInfo.ok`; estimated tokens ≤ budget.
- Re-running with the same `(rid, prompt_version, model)` produces byte-identical questions and makes no LLM call.
- A template whose fill values contain `{trigger}` and `{hold_missing}` returns them untouched; an uncovered `{{placeholder}}` is left in place rather than blanked.
- The generator's proposed answer is stored in the pipeline and appears in no published payload.

**Source.** core requirement 45; profile requirements 24, 25; profile invariant 1; [`guided-validation`](../guided-validation/spec.md) spec.

**Verify.** `uv run dataforce run generate_questions && uv run pytest tests/integration/test_generate_questions.py -v`

## T24 · `publish` and `pull` stages

**Goal.** Stages 8 and 9: questions reach annotators carrying nothing a model produced, and answers come back normalized.

**Blocked by.** T22, T23.

**Relevant files.** `src/dataforce/pipeline/human_review/{publish,pull}.py`.

**Proposed approach.** `publish` creates the project from the generated config, pushes the allowlisted payload, and is idempotent on `rid`. A gold set of ≥50 expert-labelled records is mixed in as ordinary tasks, visually indistinguishable — the 951 records already carrying `human_checked` are the pool it is drawn from. `pull` normalizes responses and **rejects, rather than repairs**, any response marked incorrect that carries no correction; rejected responses return to the queue with the reason attached. Corrections are asserted inside the profile's answer space at pull time, because a structural guarantee in someone else's UI is not one of ours.

**Acceptance criteria.**
- Gate: every incorrect verdict has a correction; the payload key set equals the allowlist.
- No vote, reasoning trace, consensus, cohesion, conflict, bucket, stratum, or generator answer appears in any published payload. All of it joins back on `rid` after pull. — core requirement 33, invariant 10
- Label Studio unreachable on publish retries with backoff five times, then fails with pushed tasks recorded; a re-run pushes no duplicate.
- A correction outside the answer space is rejected at pull time. — core invariant 11
- Gold records are indistinguishable from ordinary tasks in the payload.

**Source.** core requirements 33, 46, 48, 50, 51; core invariants 10, 11; core § Error Behavior (Label Studio, incorrect verdict).

**Verify.** `uv run dataforce run publish pull && uv run pytest tests/integration/test_publish_pull.py -v`

## T25 · `aggregate` stage and the pilot gate

**Goal.** Stage 10: two annotators become one verdict weighted by demonstrated reliability, and the five pilot thresholds are measured.

**Context.** This gate is the project's decision point. α below 0.667 means the guideline is broken, not the annotators, and the remedy is a guideline revision and a re-pilot — never a lower threshold. α above 0.95 on a subtle task means the questions dodge the hard cases.

**Blocked by.** T19, T24.

**Changed by 2C.** α on *corrections* is computed with the profile's `answer_distance`, which is now the soft δ — so a pilot where annotators agree on every tool and differ on argument values produces a high α rather than a low one, and that is the intended reading. Two things follow for the gate: the 0.667 floor was set with a names-only δ in mind and is re-examined on pilot data before it gates anything, and the per-focus breakdown must separate a tool disagreement from an argument disagreement, because they need different remedies — the first is a guideline problem, the second is usually a question that did not show the annotator the parameter.

**Relevant files.** `src/dataforce/pipeline/human_review/aggregate.py`, `lib/{alpha,gold}.py`.

**Proposed approach.** Krippendorff's α on the verdict (nominal) across all overlapped records, per question focus and overall. Agreement on corrections as α with the profile's `answer_distance`. Where overlap ≥ 2, aggregate verdicts with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote; aggregate corrections with the profile's `vote_consensus`. Score each annotator continuously against the gold set, and use the same gold set to calibrate juror weights as mean per-answer score against human-validated labels.

**Acceptance criteria.**
- Gate: α on verdict ≥ 0.667; α ≤ 0.95 or a recorded investigation; question flag rate ≤ 10%; per-annotator gold accuracy ≥ 0.85; `likely_label_error` bucket precision ≥ 0.30.
- α below 0.667 hard-stops with the per-focus breakdown.
- α above 0.95 warns and requires a written review note carried into the datasheet.
- Bucket precision below its floor hard-stops; the panel or the thresholds change before the full corpus depends on them.
- An annotator below 0.85 on gold has work held pending review, with submitted answers re-queued for a second opinion rather than discarded.
- Each juror's gold-calibrated weight is reported, and a juror below the declared floor is dropped for that release with the drop recorded.

**Source.** core requirements 36, 50, 52, 53, 54, 64; profile requirements 15, 20; core § Error Behavior (α, bucket precision, annotator gold).

**Verify.** `uv run dataforce run aggregate && uv run pytest tests/integration/test_aggregate.py -v`

## T26 · `curate` stage and the adjudication project

**Goal.** Stage 11: disagreements are resolved by a reviewer who produced neither answer, and every record records who decided what.

**Context.** Label Studio Community has no review workflow. This is that workflow.

**Blocked by.** T25.

**Relevant files.** `src/dataforce/pipeline/human_review/curate.py`, `lib/adjudicate.py`.

**Proposed approach.** Disagreements, and records below an aggregated-confidence threshold, go to a second adjudication project showing both answers and both notes, resolved by a reviewer who produced neither. Curation records for every record whether its label is `original`, `corrected`, `jury_consensus`, or `unvalidated`, with the validator and the decision date.

**Acceptance criteria.**
- Gate: every correction is inside the profile's answer space.
- An adjudication task is never routed to an annotator who answered it.
- Every curated record carries `validation.status`, `validators`, and `decided_at`.
- Stages 8–10 loop cleanly: publish → annotate → pull → aggregate → adjudicate → publish again, with no duplicate tasks.

**Source.** core requirements 55, 56; core § stage graph (the 8–10 loop).

**Verify.** `uv run dataforce run curate && uv run pytest tests/integration/test_curate.py -v`

## T27 · Marker-DSL glossary confirmed in writing — blocking, not code

**Goal.** A written, agreed glossary of `{trigger}`, `{hold_other}`, `{hold_missing}`, `{constraint}`, `{turn_trigger}`, `{or}`, obtained before questions are generated.

**Context.** `guided-validation` declares this a blocking prerequisite, and the profile spec confirms the pilot is where it is obtained. The marker language is the annotator's only evidence; if two annotators read `{hold_other}` differently, α measures the glossary's ambiguity rather than the records' difficulty, and no threshold change fixes that.

**Blocks.** T23.

**Proposed approach.** Not a pipeline task. Write one definition per marker with a worked example from the corpus, have it reviewed by whoever owns the tool catalogs, and commit it under `config/templates/` so it ships in the annotation surface and in the datasheet.

**Acceptance criteria.**
- Every marker token the reader can emit has a definition and a corpus example.
- The glossary is referenced by the generated Label Studio config, not pasted into it.
- A plausible-but-wrong question has no automated detector — the flag rate is the only signal, which is why 10% is a gate. The glossary is what makes the flag rate interpretable.

**Source.** profile § The marker DSL; [`guided-validation`](../guided-validation/spec.md) (blocking prerequisite); core § Error Behavior (final paragraph).

**Verify.** The glossary exists, covers every marker the reader emits (asserted by a test comparing the two lists), and predates the first `generate_questions` run.

## T28 · Run S0, then S1, then the one threshold re-tuning pass

**Goal.** Climb two rungs and record what each proved.

**Context.** You do not climb without passing. S0 proves the plumbing in one sitting; S1 proves the instruments — is the question answerable, is the guideline right, do two people agree, and does each triage bucket predict what humans actually find.

**Blocked by.** T21, T26, T27.

**Proposed approach.** S0: 50 records, ~70 questions, 1 annotator, 3 jurors stubbed then live. Verify `maximum_annotations`, key-pool failover and cache determinism. S1: 500 records, ~700 questions, 2 annotators at 100% overlap, 3 real jurors. Then exactly one re-tuning pass on the bucket thresholds from the pilot's measurement — a bucket whose precision the pilot cannot establish gets no quota at scale.

**Acceptance criteria.**
- S0 completes end to end and its three verifications are recorded.
- S1 passes all five pilot-gate thresholds, or the run stops and the guideline is revised and re-piloted.
- Each bucket's precision against human verdicts is reported.
- Thresholds are re-tuned exactly once, and the change is a commit to `params.yaml`.
- Any bucket with unestablished precision is given quota zero at scale.

**Source.** core requirements 41, 63, 64; profile requirements 19, 22.

**Verify.** `uv run dataforce run` completes for both rungs; `metrics.json` carries α per focus, gold accuracy per annotator, flag rate, and bucket precision.

---

# Phase 6 — Release

**Goal:** a DVC-tracked `release/v1` reproducible from one git commit, with a fully human-validated test split, zero leakage, and documentation that states how the dataset was made.

## T29 · `split` stage and decontamination

**Goal.** Stage 12: train / validation / test where no scenario appears on both sides.

**Context.** Records sharing a catalog are near-variants of one scenario — the largest such group is 112 records, and 16,276 of 17,583 fingerprints are singletons, so the groups that matter are few and large. A random split puts variants on both sides, inflating every metric, and every metric produced before such a fix would be void.

**Blocked by.** T26.

**Relevant files.** `src/dataforce/pipeline/release/split.py`, `lib/decontaminate.py`.

**Proposed approach.** Group-based on `group_key`, never random. A group is wholly in one split, and the same holds for any training subsample. The test split is **100% human-validated**: a record that has not been annotated cannot enter test at any budget, and `jury_consensus` records are barred permanently. Decontamination verifies zero n-gram overlap between test and train and zero shared `group_key`.

**Acceptance criteria.**
- Gate: zero group leakage; zero n-gram overlap. Either is a hard stop.
- A planted group spanning what would be a random split is caught, and so is a planted n-gram overlap.
- The 112-record catalog group is wholly in one split, as a named fixture. — profile invariant 5
- No test record has `validation.status` outside `{original, corrected}`. — core invariant 13

**Source.** core requirements 57, 58, 59; core invariants 12, 13; profile invariant 5; profile Decisions (group split).

**Verify.** `uv run dataforce run split && uv run pytest tests/integration/test_split.py -v`

## T30 · `export` stage, provenance, and training subsamples

**Goal.** Stage 13: training files in the shape a trainer expects, each record carrying where it came from.

**Blocked by.** T29.

**Changed by 2C.** `training_example`'s equality assertion — invariant 4, the answer in the target turn equals `meta.label` — is now over a nested structure rather than two flat arrays, so it compares canonically-rendered forms and not Python objects whose key order differs. The target turn ships in the source's own call shape, which means `training_example` is where the canonical part becomes a provider's `tool_calls` again; per core *Decisions*, no provider's JSON is ever stored, so that mapping lives here and nowhere earlier.

**Relevant files.** `src/dataforce/pipeline/release/export.py`, `lib/manifest.py`.

**Proposed approach.** Emit the profile's `training_example` — for `tool_decision`, SFT JSONL in the source `messages` shape with the curated label in both the assistant message and `meta.label`, asserted equal on the way out. Every exported record carries source SHA-256, pipeline version, modality and profile versions, `agent-toolkit` version, validation status, validator, dedup cluster, split, stratum, and the panel version where the jury touched it. Emit deterministic 25% / 50% / 100% subsamples of the training split, group-disjoint and recorded in the manifest. Dedup deletion happens here, from an explicit filter. Write `MANIFEST.sha256` listing every file's digest.

**Acceptance criteria.**
- Gate: test is 100% human-validated; counts reconcile against the stage inputs.
- `meta.label` equals the parsed assistant message on every exported record. — profile invariant 4
- Every exported record carries all eleven provenance fields.
- The three subsamples are group-disjoint, deterministic across runs, and listed in the manifest.
- Every answer in every exported artifact validates against `profile.answer_schema`. — core invariant 5

**Source.** core requirements 23, 60, 61; core invariant 5; profile requirements 18, 26; profile invariant 4.

**Verify.** `uv run dataforce run export && uv run pytest tests/integration/test_export.py -v`

## T31 · `document` stage: datasheet, data statement, Croissant

**Goal.** Stage 14: a consumer can judge this dataset without reading the pipeline.

**Context.** A corpus that is two-thirds machine-labelled must be documented as such, and the human-validated test split is the mitigation that makes the release measurable at all.

**Blocked by.** T30.

**Relevant files.** `src/dataforce/pipeline/release/document.py`, `lib/{datasheet,croissant}.py`.

**Proposed approach.** A datasheet (Gebru et al.), a data statement (Bender & Friedman), and a Croissant file validated by `mlcroissant`. The datasheet states the machine-labelled share explicitly — 14,241 of 21,172, 67.3%, by `gemma-4-31B-it`, and 1,358 records already relabelled once — and names the jury panel with each juror's family and gold-calibrated weight. It carries the residual-error estimate from the audit sample, any α-above-0.95 review note, the `enable_redact` setting, and the cross-border determination reference from T21. Documentation is a gated stage: a missing required field fails the release.

**Acceptance criteria.**
- Gate: all required fields present; the Croissant file validates under `mlcroissant`.
- The datasheet names every juror with family and weight, and states the machine-labelled share.
- The residual-error estimate is present, with the stratum and selection probability of every record it was computed from. — core invariant 15
- A deliberately omitted required field fails the stage.

**Source.** core requirements 62, 65; profile requirement 27.

**Verify.** `uv run dataforce run document && uv run pytest tests/integration/test_document.py -v`

## T32 · Second profile — the genericity guard

**Goal.** A deliberately trivial single-label classification profile runs the whole graph end to end.

**Context.** Two profiles is the cheapest proof that the core is not secretly one profile's code. Everything before this task could pass while `pipeline/` quietly assumed set-valued answers. Since R3 deleted the conformance suite, this is also the first test of whether the five profile rules survive as prose: a second profile arriving without its own rule tests is the signal to rebuild the suite after all.

**Blocked by.** T31.

**Relevant files.** `src/dataforce/profiles/simple_classification/`, `tests/e2e/test_second_profile.py`.

**Proposed approach.** Single-label classification over a 30-record text fixture: the answer is one class, `answer_distance` is `0` if equal else `1`, `vote_consensus` is the mode. Run all fifteen stages with stubbed jurors, a stubbed generator and a containerized Label Studio. Follow the definition/step module rule from the start — this profile is small enough that it should be three files, not nine.

**Acceptance criteria.**
- All fifteen stages complete for the second profile with no change to any module under `pipeline/` or `shared/`.
- Its own tests prove the five profile rules for a single-label answer. **If this profile arrives without them, that is the signal to build the suite after all** — see core Decisions.
- Any change required in `pipeline/` to make this pass is itself a defect report against the core, recorded before the change is made.

**Source.** core § Testing Strategy (Genericity); core invariant 16; core requirement 6.

**Verify.** `uv run pytest tests/e2e/test_second_profile.py -v`

## T33 · End-to-end reproducibility in CI

**Goal.** Two `dataforce run` invocations from a clean checkout produce byte-identical artifacts. This passing is the definition of the pipeline being done.

**Blocked by.** T32.

**Relevant files.** `tests/e2e/test_smoke_reproducible.py`, `deploy/` CI config.

**Proposed approach.** The smoke rung *is* the integration test: `dataforce run` from raw to release against stubbed jurors, a stubbed generator and a containerized Label Studio, asserting a byte-identical run manifest and `MANIFEST.sha256` on a second run.

**Acceptance criteria.**
- Two cold runs from a clean checkout produce identical `MANIFEST.sha256`. — core invariant 14
- The run is reproducible from one git commit plus one `dataforce run`.
- CI runs it on every push.

**Source.** core requirement 61; core invariant 14; core § Testing Strategy (End to end).

**Verify.** `uv run pytest tests/e2e/test_smoke_reproducible.py`

---

## What this plan deliberately leaves out

Taken from the specs' own Out of Scope sections, restated so no task quietly picks them up: real image / audio / video modalities beyond the T16 stub; model training and evaluation; actual-token accounting, which needs `usage` on `agent-toolkit`'s `Completion`; local patches to `agent-toolkit`, since gaps there are fixed by a release there; Confident Learning, which needs a fixed class space this corpus does not have; synthetic data generation; active learning; fine-tuning a juror; our own annotation service, which the T28 pilot gate decides; and automatic write-back to `fc_train_final.json`.
