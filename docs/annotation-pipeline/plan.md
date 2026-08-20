# Annotation Pipeline — Implementation Plan

**Source:** [`spec.md`](spec.md) (65 requirements, 17 invariants, 15 stages) and [`../profiles/tool-decision/spec.md`](../profiles/tool-decision/spec.md) (27 requirements, 5 invariants).

**One plan, two specs.** They are not independently buildable. Fourteen of the fifteen stages are written against two protocols, and `tool_decision` is the only implementation of one of them — a plan for the core alone would produce tasks whose acceptance criteria cannot be verified, because you cannot test `jury` without an answer type, a δ, and a corpus. [`guided-validation`](../guided-validation/spec.md) gets no separate plan: the pipeline consumes its question model inside `generate_questions`, so its requirements appear as acceptance criteria on that stage. [`dataforce-platform`](../dataforce-platform/spec.md) gets a plan only if the Phase 5 pilot gate says Label Studio is the constraint.

**Six phases and one revision pass, 36 tasks.** Phases are ordered by risk and learning value, not by layer. Every phase ends in something runnable.

Phases 1 and 2 are **built**. The revision pass between 2 and 3 exists because building them taught three things the first plan had wrong, and all three get more expensive with every stage added: the contract members were named for activities rather than results, a file per concern made following one record's path cross ten files, and a 392-line generic conformance suite was checking five properties that fit in a table. Revision tasks are numbered R so the tasks after them keep the numbers they were planned under.

| Phase | Outcome | Tasks |
|---|---|---:|
| 1 | The repo builds, both contracts exist, and the rules a profile must satisfy are written down | 6 |
| 2 | One raw record becomes a canonical record and returns through `training_example` | 4 |
| 2R | The names say what they return, a module is a workflow step, and 49 files become 30 | 3 |
| 3 | 21,172 records become a usable corpus with no personal data downstream | 6 |
| 4 | 50 records voted by three jurors, ranked into a review queue, inside a token ceiling | 5 |
| 5 | Two annotators answer 500 questions and the pilot gate passes | 7 |
| 6 | A reproducible `release/v1` with a datasheet and a fully human-validated test split | 5 |

---

## Shared decisions — read once, apply to every task

These are settled by the specs. No task re-decides them, and a task that violates one is rejected in review regardless of whether its own acceptance criteria pass.

1. **The library is not re-implemented.** No module defines a hash helper, a JSONL reader/writer, an atomic-write context manager, a JSON-from-text extractor, a template filler, or a retry wrapper. `openai`, `tenacity`, `tiktoken`, `jsonschema` appear in no pipeline import. Use the call table in spec § *What `agent-toolkit` already provides*. — core invariant 17
2. **Every artifact is read and written through `file_utils`**, which is already atomic and creates parents. No stage opens an artifact file directly. — core requirement 17
3. **Nothing under `pipeline/` or `shared/` imports a concrete profile or modality.** Both arrive through their registries. — core invariant 16
4. **Every token figure is an estimate.** `agent-toolkit`'s `Completion` discards `usage`, so budgets are enforced on `count_tokens` estimates and every reported figure is labelled "estimated". — core requirement 37, Assumption
5. **Thresholds live in `params.yaml` and `config/gates.yaml`, never in code.** `shared/gates/runner.py` is an engine.
6. **One `except LLMError` per dispatching stage.** Nothing catches bare `Exception` around an LLM call. — core § Error Behavior
7. **Content parts use `type`, not `kind`**, with closed values `text | image | audio | video` and the payload flat on the part. — core Decisions
8. **Python 3.12.14**; `agent-toolkit[llm] @ git+https://github.com/giangchicken/agent-toolkit.git@v0.1.0`. `git` must exist on the installing machine. CI sets `TIKTOKEN_CACHE_DIR` against a populated cache.
9. **`data/raw/` is outside DVC entirely.** Not tracked, not committed, in `.gitignore`.
10. **Every contract member is named for what it returns**, and no member shares a name with a stage. `content_parts`, `embedding`, `personal_data_detectors`, `display_config`; `canonical_record`, `answer_schema`, `answer_distance`, `vote_consensus`, `validity_checks`, `question_text`, `answer_config`, `group_key`, `training_example`. — core § The two contracts, core Decisions
11. **A module holds one step of the workflow — and merging stops where the consumers differ.** Everything a step does lives in one module, so following one record's path does not cross ten files. Two limits: a module may not force a consumer to depend on what it does not use, which is why `shared/schemas/` stays a package divided by pipeline phase rather than becoming one file every stage imports; and a *format* used by several steps stays its own module. — core Decisions
12. **There is no conformance suite.** The five profile rules are stated in core § *Rules a profile must satisfy* and each profile proves them in its own tests. Nothing checks them at registration, and the cost of that is stated with the rules. — core requirement 6, core Decisions

**Not code, and blocking.** Two prerequisites are human work that gates specific phases; they are tasks 21 and 27 rather than footnotes, because skipping them silently is the failure mode.

---

# Phase 1 — Foundation and contracts

**Goal:** the repo builds under one command, the two contracts exist as protocols, and the rules a profile must satisfy are written down where its author will read them.

## T1 · Repo skeleton and toolchain

**Goal.** `make check` runs lint, types and tests on an empty but structured repository, and `dvc repro` succeeds with zero stages.

**Context.** This repository currently holds only `docs/` and `README.md`. Every later task adds to a structure this one establishes. The layout is fixed by the spec and is not a design question.

**Relevant files.** `pyproject.toml`, `uv.lock`, `Makefile`, `.gitignore`, `dvc.yaml`, `params.yaml`, `src/dataforce/`, `tests/{unit,integration,e2e,fixtures}/`, `deploy/`.

**Proposed approach.** `uv` for dependency management, `src/` layout. Create the full directory tree from spec § *Repository layout* with `__init__.py` files only. `dvc init`. `params.yaml` holds the source file path and its SHA-256, `enable_redact: false`, and empty threshold blocks. `.gitignore` covers `data/raw/`, `.env`, and `*.jsonl` outside `tests/fixtures/`. Ruff, mypy strict, pytest. `src/dataforce/cli.py` exposes `dataforce` with `run`, `profile`, `requeue` as stubs that exit non-zero with "not implemented".

**Acceptance criteria.**
- `make check` passes on a clean clone with no source modules beyond `cli.py`.
- `uv run dataforce --help` lists `run`, `profile`, `requeue`.
- `uv run dvc repro` exits zero.
- `data/raw/` is in `.gitignore`, appears in no `.dvc` file and in no `dvc.yaml` output list.
- `cli.py` is the only module that configures a logging handler; every other module uses `get_logger(__name__)`.

**Source.** core § Repository layout; core requirement 21; shared decision 5, 8, 9.

**Verify.** `make check && uv run dvc repro && uv run pytest tests/unit/test_repo_hygiene.py`

**Out of scope.** Any stage logic. Any profile or modality.

## T2 · Canonical record, typed content parts, artifact schemas

**Goal.** One record shape that every stage adds to and none removes from, with a pandera schema per artifact.

**Context.** The record shape is the one thing the spec says must be right before the first line of code, because retrofitting typed parts or media-by-reference would touch all fifteen stages. Get this wrong and every later task inherits it.

**Relevant files.** `src/dataforce/shared/record.py`, `src/dataforce/shared/schemas/`.

**Proposed approach.** `Part` as a mapping with `type` (`text | image | audio | video`), `role`, and either `text` or `uri` + `sha256` + modality metadata. `Record` per spec § *Canonical record*, with pydantic for construction and pandera for artifact validation. One schema file per artifact: `loaded`, `usable`, `pii_findings`, `deduped`, `votes`, `queue`, `questions`, `published`, `responses`, `aggregated`, `curated`, `split`. `rid` is computed from the content parts' digests — text parts contribute text, media parts contribute `sha256` — never from raw bytes or position.

**Acceptance criteria.**
- Re-ingesting a shuffled fixture yields byte-identical `rid` values. — core invariant 2
- No artifact schema admits a non-text part lacking `uri` and `sha256`, and none admits a base64 blob. — core invariant 4
- A round-trip test writes each artifact with `write_jsonlines`, reads it with `read_jsonlines`, and validates against its schema.
- A part with `type: "audio"` and a `uri` passes every schema that carries content, with no change to the text schemas.

**Source.** core requirements 8, 9, 10; core invariants 2, 4; core § Canonical record.

**Verify.** `uv run pytest tests/unit/test_record.py tests/unit/test_artifact_schemas.py`

**Out of scope.** Any modality implementation. `privacy`, `jury`, `triage`, `validation` blocks are declared in the schemas but populated by later tasks.

## T3 · Gate runner

**Goal.** A gate engine that halts `dvc repro` with a machine-readable failure, and the conservation assertion that runs on every stage.

**Context.** "Every stage has a gate that stops the run" is the architecture's response to the data-cascade finding. Every stage task depends on this, so it comes before all of them.

**Relevant files.** `src/dataforce/shared/gates/runner.py`, `config/gates.yaml`.

**Proposed approach.** A gate is a named predicate over a stage's inputs and outputs, with thresholds read from `config/gates.yaml` / `params.yaml`. On failure write `data/<stage>/GATE_FAILED.json` carrying the assertion, observed and expected values, and up to 100 offending `rid`s, then exit non-zero. Ship one universal gate: `output + quarantined + deduped_out == input`, written to `metrics.json` on every stage.

**Acceptance criteria.**
- A failing gate writes `GATE_FAILED.json` with all four fields and exits non-zero, and `dvc repro` halts.
- No stage consumes an input whose gate did not pass.
- The conservation assertion catches a deliberately record-dropping stage.
- `runner.py` contains no numeric threshold.

**Source.** core invariant 1; core § Error Behavior; shared decision 5.

**Verify.** `uv run pytest tests/unit/test_gate_runner.py`

## T4 · The two protocols and their registries

**Goal.** `Modality` with four methods and `Profile` with nine members — each named for what it returns — resolved by name, with versions stamped onto every artifact.

**Context.** These two protocols are the whole thesis: everything else in the pipeline is written once against them. The member lists are closed — "exactly four" and "exactly seven" are requirements, not descriptions.

**Relevant files.** `src/dataforce/modalities/base.py`, `registry.py`, `src/dataforce/profiles/base.py`, `registry.py`.

**Proposed approach.** Protocols exactly as spec § *The two contracts*. `answer_schema` may be built per record, so it is accessed as a callable or property closed over the record — a profile whose answer space depends on the record returns a schema for that record. Registries map name → implementation; resolution records `name@version` for both axes into `record.producer` and the release manifest. A profile declares its modality; a mismatched pair is a hard stop, not a coercion.

**Acceptance criteria.**
- Adding a fifth `Modality` method or an eighth `Profile` member fails a test that asserts the member sets.
- A run naming a profile whose declared modality differs from `--modality` hard-stops before any stage.
- Every artifact carries `producer.modality` and `producer.profile` as `name@version`.
- An unregistered name produces a clear error listing what is registered.

**Source.** core requirements 1, 2, 7; core § Error Behavior (profile/modality disagreement).

**Verify.** `uv run pytest tests/unit/test_registries.py tests/unit/test_protocols.py`

**Out of scope.** The UI-control composition of requirement 3 — that lands with `publish` in T22.

## T5 · The five profile rules, written down

**Goal.** The properties every profile must have, stated once in the spec, with the symptom of breaking each one named beside it.

**Context.** A generic suite that checked these was built and removed — 392 lines to check five properties, 95 of them machinery for inventing sample answers out of an arbitrary JSON Schema, written for profiles that do not exist. The rules are short enough to state; each profile proves them over its own answer type, where the assertions read in that type's own terms. **What this costs is real and is the reason the symptom column exists:** nothing fails when a rule is broken, and rule 1 in particular fails silently into plausible-looking numbers.

**Relevant files.** `docs/annotation-pipeline/spec.md` § *Rules a profile must satisfy*. No source file.

**Proposed approach.** A table of five rules — `answer_distance` is a metric; `vote_consensus` is deterministic and honours unanimity; an answer survives a JSON round trip; `canonical_record` preserves every field it does not own; `training_example` reproduces the record's answer — each with what the pipeline needs it for and what a reader would see if it were broken. A profile returning `None` from `vote_consensus` for every input declares it has no defensible consensus, which is a declaration rather than a broken rule 2.

**Acceptance criteria.**
- Each of the five rules names the pipeline behaviour that depends on it and the symptom when it is broken.
- The cost of not enforcing them is stated in the spec's Decisions, not implied.
- Every profile task in this plan lists its own rule tests under *Verify*.

**Source.** core requirement 6; core invariant 9; core § Rules a profile must satisfy; core Decisions.

**Verify.** Not a code task. The check is that T9 and T31 each carry rule tests for their own profile.

## T6 · Guard tests: toolkit boundary, import graph, no re-implementation

**Goal.** Three tests that keep shared decisions 1–3 true as the codebase grows.

**Context.** These properties degrade silently. A helper added under deadline is how a codebase acquires a second JSONL writer, and how `pipeline/` acquires an import of `tool_decision`.

**Relevant files.** `tests/unit/test_import_graph.py`, `tests/unit/test_no_reimplementation.py`, `tests/integration/test_toolkit_boundary.py`.

**Proposed approach.** Import graph: walk the AST of every module under `pipeline/` and `shared/`, fail on any import naming a concrete profile or modality. No re-implementation: fail on a module defining a hash helper, JSONL reader/writer, atomic-write context manager, JSON-from-text extractor, template filler, or retry wrapper, and on any import of `openai`, `tenacity`, `tiktoken`, `jsonschema`. Toolkit boundary: `tests/consumer_smoke.py` is **not in the wheel** — the library builds `packages = ["src/agent_toolkit"]` — so CI fetches it with `git clone --depth 1 -b v0.1.0` and runs it against the installed environment.

**Acceptance criteria.**
- Adding `from dataforce.profiles.tool_decision import ...` to any `pipeline/` module fails the import-graph test.
- Adding a local `def sha256(...)` fails the re-implementation test.
- A broken git-dependency resolution fails the toolkit boundary test rather than surfacing at the first jury run.

**Source.** core invariants 16, 17; core § Testing Strategy (Import graph, Toolkit boundary).

**Verify.** `uv run pytest tests/unit/test_import_graph.py tests/unit/test_no_reimplementation.py tests/integration/test_toolkit_boundary.py`

---

# Phase 2 — First modality and profile

**Goal:** one raw record from `fc_train_final.json` becomes a canonical record and comes back out through `training_example`, with `answer_distance` and `vote_consensus` proved against profile rules 1 and 2. No LLM, no Label Studio, no DVC stage yet.

## T7 · `text` modality: loader, embedder, display control

**Goal.** Three of the modality's four methods, so a text corpus can be loaded, embedded and displayed.

**Context.** Privacy detectors are the fourth method and are substantial enough to be their own task (T13). This task delivers the rest.

**Blocked by.** T4.

**Relevant files.** `src/dataforce/modalities/text/`.

**Proposed approach.** `content_parts` turns system / user / assistant turns into text parts carrying `role`. `embedding` uses `model2vec` `potion-multilingual-128M` over the concatenated text parts. `display_control` emits an escaped `HyperText` control — corpus text is never interpolated into markup unescaped. `privacy_detectors()` returns an empty list until T13, which the seam test in T16 tolerates and `pii_check` does not.

**Acceptance criteria.**
- A record with three turns loads into three text parts, roles preserved, text byte-identical.
- Embeddings are deterministic across two runs on the same input.
- A record whose text contains `<script>` renders escaped; a test asserts the raw tag never appears in the emitted control.
- A retrieval sanity test over 200 hand-paired records confirms `potion-multilingual-128M` separates Vietnamese near-duplicates from unrelated records; if it does not, the sentence-transformer fallback is taken and recorded.

**Source.** core requirements 1, 47; profile § pieces table; profile Assumption (`potion-multilingual-128M`).

**Verify.** `uv run pytest tests/unit/test_text_modality.py`

**Out of scope.** Privacy detectors (T13). Any non-text modality.

## T8 · `tool_decision` adapter

**Goal.** Parse the `TOOLS:` block into a structured catalog with every marker token preserved byte-identically.

**Context.** This is the highest-risk task in the plan. The marker DSL is simultaneously the deterministic rule source, the annotator's only evidence, and the thing most easily destroyed in passing — a parser that strips markers passes every other test while making the annotation task unanswerable. The task also settles a parsing convention: `label_not_in_catalog` reads 722 with the spec's parser and 588 with an independent regex over `^\s*\[Name\]`, on both the current file and a July backup, so the difference is convention, not corpus. Whatever this adapter counts becomes the declared number.

**Blocked by.** T2, T7.

**Relevant files.** `src/dataforce/profiles/tool_decision/adapter.py`, `tests/fixtures/tool_decision/`.

**Proposed approach.** Parse each catalog entry into name, purpose, `call_when`, `hold_when`, required parameters and per-parameter constraints. `rid = compute_hash(system ‖ user ‖ assistant)[:16]`, so identity is position-independent. `group_key` is the catalog fingerprint, **never** `source_index` — which is unique per record and therefore gives no leakage protection, a measurement not an assumption. `answer_space` is the list of catalog tool names. Preserve `meta` verbatim.

**Acceptance criteria.**
- Every `{trigger}`, `{hold_other}`, `{hold_missing}`, `{constraint}`, `{turn_trigger}` token in a source system message is present byte-identically in the adapter's output. — profile invariant 1
- Fixtures cover all 13 observed `meta` key-sets, answer cardinalities 0/1/2/3, catalog sizes 0/1/8/20, and malformed `TOOLS:` blocks.
- A malformed block produces `empty_catalog`, not an exception and not a partial catalog.
- `group_key` collides for records sharing a catalog; the largest such group is 112 records and is a named fixture.
- Running the adapter over the full file reproduces a count for each validity check, and those counts are written into `params.yaml` as the declared numbers.

**Source.** profile requirements 1, 2, 3, 4; profile invariant 1; profile § Error Behavior (adapter rows).

**Verify.** `uv run pytest tests/unit/test_tool_decision_adapter.py -v`

**Out of scope.** Running the checks as a pipeline stage (T12). Question templates (T23).

## T9 · `tool_decision` answer contract: schema, distance, consensus, validity checks, training example

**Goal.** The remaining profile members, with the five profile rules proved in this profile's own tests.

**Context.** `δ(∅,∅) = 0` is load-bearing on 35.4% of this corpus. A Jaccard returning `0/0 → NaN`, or treating two empty sets as maximally distant, would make the zero-label population — the part carrying the corpus's real difficulty — look like the part with least agreement.

**Blocked by.** T5, T8.

**Relevant files.** `src/dataforce/profiles/tool_decision/answers.py`, `tests/unit/test_tool_decision_answers.py`.

**Proposed approach.** `answer_schema` per record is `{"type":"array","items":{"type":"string","enum":[t.name for t in record.catalog]}}` — the `enum` is the catalog constraint, enforced inside the library, which is why there is no answer-validation code in the jury. `delta(a,b) = 1 − |a∩b|/|a∪b|` with `delta(∅,∅) = 0.0` returned before the division. `consensus` is the set a strict majority of valid votes included, and may be a set no individual juror proposed. `validity_checks()` returns four named predicates: `label_assistant_mismatch`, `label_not_in_catalog`, `empty_catalog`, `label_cardinality_anomaly`. `export` emits SFT JSONL in the source `messages` shape with the curated label in both the assistant message and `meta.label`, asserted equal.

**Acceptance criteria.**
- This profile's own tests prove all five rules, including the empty-answer case of the metric axioms — rule 1.
- A property test over random set pairs asserts symmetry, identity including `δ(∅,∅)=0`, range `[0,1]`, no `NaN`. — profile invariant 2
- Consensus matches hand-worked vote sets, including a case where consensus differs from every individual vote.
- The four checks, run over the full corpus, reproduce the counts T8 wrote to `params.yaml`.
- Export round-trips: `meta.label` equals the parsed assistant message on every exported record. — profile invariant 4

**Source.** profile requirements 2, 5, 6, 7, 8, 26; profile invariants 2, 3, 4; core requirement 25.

**Verify.** `uv run pytest tests/unit/test_tool_decision_answers.py tests/unit/test_delta.py -v`

## T10 · `dataforce profile` — corpus profiler with CI drift detection

**Goal.** One command that reproduces every count in the profile spec's Context section from the file named in `params.yaml`, and fails CI when a count drifts.

**Context.** The source file changed three times in four weeks. `label_assistant_mismatch` was 48 in the 2026-08-17 backup and is 0 now, and that was discovered by accident. This command is how the next change is noticed the day it happens instead of four weeks later.

**Blocked by.** T8, T9.

**Relevant files.** `src/dataforce/cli.py`, `src/dataforce/profiles/tool_decision/profiler.py`.

**Proposed approach.** Stream the file with `iter_json_array_file` — never load it whole. Emit every measured property: record count, file size, answer cardinality distribution, distinct tool names, catalog size range, distinct catalog fingerprints and group sizes, `meta` key-sets, labelling-model share, `orig_label` counts, duplicate turns, prompt-size percentiles, total characters, the five privacy signal counts, and the four validity-check counts. Write to `metrics/corpus_profile.json` alongside the file's SHA-256. CI compares against the committed profile and fails on any drift, reporting which counts moved.

**Acceptance criteria.**
- Reproduces 21,172 records, cardinality 7,498 / 10,596 / 2,757 / 321, 17,596 catalog fingerprints with largest non-empty group 112, 13 `meta` key-sets, 14,241 `gemma-4-31B-it`, 100,557,307 total prompt characters.
- Every emitted figure is stamped with the source SHA-256; the current file is `6f7d2a40…`.
- Peak memory stays well under the 126 MiB file size, proving it streams.
- A test pointing the profiler at the 2026-08-17 backup reports `label_assistant_mismatch = 48` and the run fails the drift check with that count named.

**Source.** profile § What the corpus contains; profile § Testing Strategy (Corpus profile); core requirement 13.

**Verify.** `uv run dataforce profile && uv run pytest tests/integration/test_corpus_profile.py`

---

# Phase 2R — Revision: names, file grouping, and one deletion

**Goal:** the code that exists becomes readable by someone who did not write it — every member named for what it returns, every module a step of the workflow, and 392 lines of generic checking replaced by a table in the spec.

**Why here and not later.** All three changes get more expensive with every stage added. Today two implementations and no stages call these names; after Phase 3 there are five stages, after Phase 4 seven. The rename is a mechanical diff now and a coordinated one later. Nothing in this phase changes behaviour: every test that passed before must pass after, which is what makes it safe to do in one pass.

**Blocked by.** T10. **Blocks.** T11 — no stage should be written against the old names.

## R1 · Rename every contract member

**Goal.** No member of either contract is named for an activity, and no member shares a name with a stage.

**Context.** Two defects, one of them objective. `load` and `export` were also the names of stages 0 and 13, so a sentence mentioning either was ambiguous — and `load` appears ten times in the core spec, most of them the stage. The rest named activities so general they excluded nothing: a reviewer reading `adapt(raw, parts)` learns only that something is adapted. The replacement is a rule rather than a list of preferences: **a member is named for what it returns**, which makes a wrong name visible — `content_parts` returning something that is not content parts is a legible defect.

**Relevant files.** `src/dataforce/modalities/base.py`, `src/dataforce/profiles/base.py`, both registries, `modalities/text/`, `profiles/tool_decision/`, `cli.py`, every test module, `docs/profiles/tool-decision/spec.md`, `README.md`.

**Proposed approach.** One rename per member, with no signature change:

| Contract | Was | Is | Returns |
|---|---|---|---|
| Modality | `load` | `content_parts` | `list[Part]` |
| Modality | `embed` | `embedding` | `Sequence[float]` |
| Modality | `privacy_detectors` | `personal_data_detectors` | `list[Detector]` |
| Modality | `display_control` | `display_config` | `UIControl` |
| Profile | `adapt` | `canonical_record` | `Record` |
| Profile | `delta` | `answer_distance` | `float` |
| Profile | `consensus` | `vote_consensus` | `Answer \| None` |
| Profile | `question` | `question_text` | `str` |
| Profile | `answer_control` | `answer_config` | `UIControl` |
| Profile | `export` | `training_example` | `dict[str, Any]` |

`validity_checks`, `group_key`, `answer_schema`, `name`, `version` and `modality` are unchanged: each already names what it returns. `δ` survives as the symbol in the α formulas of core requirements 52–53, where it is standard notation; the *member* is `answer_distance`. The parameter of `vote_consensus` is `votes`, not `answers`, because that is what answers "whose consensus".

**Acceptance criteria.**
- `Modality.__protocol_attrs__` and `Profile.__protocol_attrs__` contain none of the ten old names, and `tests/unit/test_protocols.py` pins the new sets as literals.
- No member name equals a stage name. A test asserts the two sets are disjoint, reading the stage names from `dvc.yaml` and the spec's stage table.
- The full suite passes with no behavioural change: same test count, same assertions, same corpus counts in `metrics/corpus_profile.json`.
- No old name survives anywhere in `src/`, `tests/`, or the three spec documents.

**Source.** core requirements 1, 2; core § The two contracts; core Decisions (*Every contract member is named for what it returns*); shared decision 10.

**Verify.** `make check && uv run dataforce profile --profile tool_decision && grep -rE '\b(load|adapt|delta|consensus|export|embed|question|answer_control|display_control|privacy_detectors)\s*\(' src/dataforce/profiles src/dataforce/modalities`

**Out of scope.** Record field names. `group_key`, `label`, `answer_space` and `meta` stay as they are — renaming a field means rewriting artifacts, and no artifact exists yet to make it free.

## R2 · Group modules by workflow step, within the consumer boundary

**Goal.** Following one record from the source file to a training example crosses four modules, not ten. `src/` goes from 49 files to 30 — and no module gains a consumer that does not use all of it.

**Context.** Two complaints, and the second corrects the first. A file per concern produced a profile of nine modules where four are under ninety lines, and fourteen schema modules of which eleven describe stages that do not exist; following one step costs ten navigations. But the flat fix — one `shared/artifacts.py` holding all twelve artifact schemas — is worse architecture, not better: fifteen stages import from `shared/`, so a single module means `data_quality/load.py` and `release/document.py` depend on the same file and editing the release schema puts every stage in the blast radius. The rule is therefore **group what changes together, and stop where the consumers differ.**

**Relevant files.** `src/dataforce/shared/schemas/`, `src/dataforce/profiles/tool_decision/`, `src/dataforce/pipeline/`.

**Proposed approach.** Merge only where one consumer uses the whole module. Move no logic between functions; delete nothing but empty packages.

| From | To | Why this boundary |
|---|---|---|
| `shared/schemas/` — 14 modules | **stays a package**, 6 modules: `base.py` plus one per pipeline phase — `data_quality.py` (loaded, usable, pii_findings, deduped), `ai_review.py` (votes, queue), `human_review.py` (questions, published, responses, aggregated, curated), `release.py` (split) | a stage imports its own phase and nothing else. Phase is also the boundary along which these schemas actually change |
| `tool_decision/{source,adapter,checks}.py` | `tool_decision/ingest.py` — stages 0–1: the source contract, `canonical_record`, `validity_checks`, `group_key` | all three read the source, all three changed together every time the source shape changed, and the profile object is their only consumer |
| `tool_decision/profile.py` | split by step: the profile object into `__init__.py`, `question_text` + `answer_config` into `annotate.py`, the answer delegations into `answers.py` | the front door becomes the index and nothing else |
| `pipeline/**/__init__.py` — 8 empty modules | deleted; each stage task creates its own package | an empty package is a promise, not a boundary |

**Not merged, deliberately:**

- `shared/manifest.py` and `shared/prompts.py` stay apart. Both read `config/`, but a stage that wants a prompt has no business importing manifest loading.
- `tool_decision/catalog.py` stays its own module. A *format* is used by `ingest.py` and `annotate.py`, and copying it into either would be two sources of truth for one grammar — the byte-identical round trip over 21,172 corpus catalogs is the proof they agree, and it only reads as one proof while the format is one module.
- `tool_decision/export.py` stays its own module at 37 lines. It changes when a trainer's format changes, which is not when anything else in the profile changes.
- `tool_decision/schemas/` stays a folder of JSON Schema files. They are the input contract, versioned per input shape, and read by tests rather than imported.
- `shared/gates/runner.py` keeps its package, and `modalities/text/` keeps its package: `text` gains the Vietnamese personal-data detectors at T13, and flattening a package that is about to grow is churn for one fewer directory.

**Acceptance criteria.**
- `find src -name '*.py' | wc -l` reports 30, down from 49.
- No stage-facing module in `shared/` is imported by a stage that uses less than all of it. Checked by reading, not by a test — but the phase split is what makes it checkable at a glance.
- `schema_for(name)` still resolves all twelve artifacts by name, and `tests/unit/test_artifact_schemas.py` still iterates every one.
- Every merged module opens with a comment naming the workflow step it holds and the stages that call it.
- The full suite passes unchanged, `tests/unit/test_import_graph.py` still finds no concrete axis imported from `shared/` or `pipeline/`, and `dvc repro` still reports up to date.

**Source.** core § Repository layout; core Decisions (*A module holds one step of the workflow — and merging stops where the consumers differ*); shared decision 11.

**Out of scope.** Deleting the eleven artifact schemas whose stages do not exist yet. They are written and tested; grouping them by phase is enough, and each becomes live when its stage arrives.

## R3 · Delete the conformance suite

**Goal.** `profiles/conformance.py` is gone, `register()` resolves a name and nothing else, and the five rules live in the spec.

**Context.** The suite was built to make "generic" a checked claim, and 95 of its 392 lines were machinery for inventing sample answers out of an arbitrary JSON Schema — written for profiles that do not exist. The review decision is that a rule the author is told to follow is the author's responsibility. **What this costs, stated once:** nothing now fails when `answer_distance` stops being a metric, and the symptom is cohesion numbers that look fine and mean nothing. `tool_decision` keeps that guarantee because `tests/unit/test_delta.py` already proves the metric axioms over random pairs directly — what is lost is the guarantee for the *next* profile, which is why T32 names its absence as the trigger to rebuild the suite.

**Relevant files.** `src/dataforce/profiles/conformance.py`, `src/dataforce/profiles/registry.py`, `src/dataforce/profiles/base.py`, `src/dataforce/shared/errors.py`, `tests/conformance/`, `cli.py`.

**Proposed approach.** Delete `conformance.py` (392) and `tests/conformance/test_suite.py` (198). `register(profile)` becomes an isinstance check and a dict write, returning nothing; `Registration` and `report_for` go with it, and importing a profile no longer runs anything — which also stops a hand-edited manifest from failing at import time. Move `tests/conformance/test_tool_decision.py` to `tests/unit/`, dropping its five suite-driven tests and keeping the 38 that test this profile directly. Rename `ConformanceError` to `InvariantError`: it survives because `training_example` raises it when the two statements of an answer disagree, which is invariant 4 and not conformance.

**Acceptance criteria.**
- No module imports `conformance`, and `tests/conformance/` no longer exists.
- `register()` is under 20 lines and runs no check beyond `isinstance`.
- The five rules are in the spec with their symptoms, and `tool_decision`'s own tests still prove all five.
- The suite's test count drops by exactly the tests that tested the suite — 198 lines, 15 tests — and no test of the profile itself is lost.

**Source.** core requirement 6; core Decisions (*Profile rules are stated for the author, not enforced by a shared suite*); shared decision 12.

**Out of scope.** Removing `tests/unit/test_delta.py`. It is now the only thing proving rule 1 for this profile, so it grows rather than shrinks: the metric axioms move into it from the deleted suite.

---

# Phase 3 — `data_quality` over the real corpus

**Goal:** 21,172 records become a usable corpus. 1,563 quarantined with reasons, personal data found and reported, near-duplicates grouped, and nothing downstream matching a personal-data pattern. Five DVC stages, five gates.

## T11 · `load` stage

**Goal.** Stage 0: raw source → canonical records, with the source file version pinned.

**Blocked by.** T3, T7, T8.

**Relevant files.** `src/dataforce/pipeline/data_quality/load.py`, `dvc.yaml`.

**Proposed approach.** Stream via `iter_json_array_file` or the modality's loader; never load whole. Record per-record provenance: source file SHA-256, byte offset, the raw record verbatim, modality and profile `name@version`, ingest timestamp. Unparsable records are carried with `parse_status = "unparsed"` and their raw text — nothing is dropped. Add the stage to `dvc.yaml` with declared deps and outs.

**Acceptance criteria.**
- Gate: `parsed + unparsed == source count`, and the source SHA-256 matches `params.yaml`.
- A source SHA-256 differing from `params.yaml` is a hard stop, not a warning — a changed source is a new dataset version decided by a human.
- Every output record carries all five provenance fields.
- `dvc repro load` is a no-op on an unchanged source.

**Source.** core requirements 13, 14, 17; core § Error Behavior (source SHA-256).

**Verify.** `uv run dvc repro load && uv run pytest tests/integration/test_load.py`

## T12 · `remove_invalid` stage and `dataforce requeue`

**Goal.** Stage 1: records that fail a provable check leave the main path into `quarantine/invalid/<check>.jsonl`, and can be re-admitted by an explicit command.

**Context.** This is what makes the rest affordable — 1,563 of 21,172 records, 7.4%, found by arithmetic in seconds. Left in, they would consume 7.4% of the jury's ~121M estimated tokens, take annotator hours, and then teach the model something false. Nothing is deleted: "remove" is scoped to the main path.

**Blocked by.** T9, T11.

**Relevant files.** `src/dataforce/pipeline/data_quality/remove_invalid.py`, `src/dataforce/cli.py`.

**Proposed approach.** Run the profile's `validity_checks()`; each failure writes the record to `quarantine/invalid/<check>.jsonl` naming the check it failed and removes it from the main path. Expected counts per check come from `params.yaml`, populated by T8. `dataforce requeue --check <name>` re-admits a class and versions the pipeline.

**Acceptance criteria.**
- Gate: each check's count is within ±10% of its declared number; outside that is a hard stop reporting the delta.
- `label_assistant_mismatch` rising above 0 is a hard stop — upstream drove it to zero, and a return means a curation step wrote one field and not the other.
- A fixture with one record failing each check asserts each lands in the right quarantine file with the right label, and that the main path count drops by exactly the expected number.
- No record is silently deleted and none silently kept: quarantined + kept == input.
- `dataforce requeue --check empty_catalog` returns those records to the main path and changes `dvc.lock`.

**Source.** core requirements 15, 16; core invariant 1; profile § Error Behavior; profile § Testing Strategy (Validity gate).

**Verify.** `uv run dvc repro remove_invalid && uv run pytest tests/integration/test_remove_invalid.py`

## T13 · `text` privacy detectors — Vietnamese, literal and spoken form

**Goal.** The modality's fourth method: detectors that find personal data in Vietnamese call-centre transcripts, where it appears in spoken form that no off-the-shelf scrubber detects.

**Context.** Vietnam's Personal Data Protection Law 91/2025/QH15 has been in force since 1 January 2026, with Decree 356/2025/ND-CP as implementing guidance. Redaction here is a legal requirement, not a nicety. The digit-word signal fires on 3,485 records (16.46%) and is a **superset** — it also matches prices, dates and reference codes — so it bounds the population needing review rather than counting personal data.

**Blocked by.** T7.

**Relevant files.** `src/dataforce/modalities/text/privacy.py`.

**Proposed approach.** Detect phone numbers, email addresses, national ID numbers, bank account numbers and full personal names in the customer turn, in both literal and spoken form: digit words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), spoken `@` (`a còng`), spoken punctuation (`chấm`, `gạch dưới`). Run against both the raw text and `string_utils.normalize_text(text, remove_tone_marks=True)`, so a transcript spelling `khong` or `chin` is not missed while patterns stay written in correct Vietnamese. Offsets resolve back onto the original; the normalized form is a matching aid and is never stored. Return the uniform span shape — a list of typed spans over a named part — so the redaction stage, its report, its vault and its gate are written once.

**Acceptance criteria.**
- A hand-built fixture of spoken phone numbers, spoken emails and national IDs asserts recall on all three.
- The same fixture's prices, dates and order references assert **no** detection — the LLM layer of T14 is what separates these, but the regex layer must not itself be the only filter.
- A tone-stripped variant asserts `normalize_text` matching catches `khong chin khong mot`.
- Every returned span's offsets index the original text, verified by slicing.
- Run over the full corpus, the detectors reproduce the five signal counts: 3,485 / 770 / 435 / 238 / 97.

**Source.** profile requirements 9, 10; core requirement 11; profile § Personal data in the corpus; profile § Testing Strategy (Vietnamese privacy).

**Verify.** `uv run pytest tests/unit/test_text_privacy.py -v`

## T14 · `pii_check` stage, vault, and `enable_redact`

**Goal.** Stage 2: find personal data, always report it, and replace it only when `enable_redact` says so.

**Context.** The two layers have separate jobs — the regex layer sets recall and is allowed to be noisy, the LLM layer sets precision. Replacement rather than deletion is load-bearing: the ground truth of this corpus turns on whether a required value was *supplied*, so deleting a phone number converts a correct call into what looks like a correct `{hold_missing}`, silently inverting the label on ~2% of records.

**Blocked by.** T13, T12.

**Relevant files.** `src/dataforce/pipeline/data_quality/pii_check.py`.

**Proposed approach.** Layer 1 is the modality's detectors. Layer 2 verifies each candidate through `llm.complete_structured` over a ±80-character window against a fixed classification schema, deciding personal data versus price, date or reference code. **Always** write `pii_findings.jsonl` — every candidate span with its class, its window and the verifier's verdict. A verification response failing its schema leaves the span **unverified, not negative**, and the record is quarantined. With `enable_redact: true`, verified spans become stable typed placeholders scoped per record (`<PHONE_1>`, `<EMAIL_1>`), so a value referenced twice stays co-referent. The placeholder-to-original mapping goes to `data/raw/pii_vault.jsonl`, outside DVC. Reports record per-class counts and a sample of 20 *placeholders in context* — never original values. Checkpoint so an LLM outage resumes with verified spans kept.

**Acceptance criteria.**
- Gate: every high-recall hit is verified or the record is quarantined; zero literal personal-data matches in any release-tier artifact. — core invariant 3
- With `enable_redact: false` the stage reports and leaves content untouched, and the downstream personal-data scan then fails so nothing ships — the default cannot silently release personal data.
- A record mentioning one phone number twice yields `<PHONE_1>` both times.
- A modality with no redactor for a part fails closed: the record is quarantined to `quarantine/pii/`, never advanced.
- A repo test asserts the vault is in `.gitignore`, in no `.dvc` file, in no `dvc.yaml` output, and that `data/raw/` is absent from DVC entirely.
- An LLM outage mid-stage resumes from checkpoint without re-verifying settled spans.

**Source.** core requirements 18, 19, 20, 21, 12; core invariant 3; profile requirements 11, 12; core § Error Behavior (privacy rows).

**Verify.** `uv run dvc repro pii_check && uv run pytest tests/integration/test_pii_check.py tests/unit/test_vault_hygiene.py`

**Human step inside this task.** Run with `enable_redact: false` over the full corpus, read `pii_findings.jsonl` — the digit-word signal fires on 3,485 records — tune the patterns and the verification prompt against what it shows, and only then set `enable_redact: true` in `params.yaml`. That flip is a committed change to a declared DVC dependency, so the decision is attributable and `dvc repro` stays reproducible.

## T15 · `embed` and `dedup` stages

**Goal.** Stages 3 and 4: vectors for every record, and near-duplicates grouped so variants of one scenario cannot straddle a split.

**Blocked by.** T7, T14.

**Relevant files.** `src/dataforce/pipeline/data_quality/{embed,dedup}.py`.

**Proposed approach.** `embed` calls the modality's embedder and writes `embeddings.npy`. `dedup` removes exact duplicates on `compute_hash` of the content digest, keeping the record with richer metadata, then finds near-duplicates with SemHash over the embeddings. Cluster members are **not deleted**: they get a shared `dup_cluster_id` and one is marked `is_representative`. Deletion happens at export from an explicit filter. `group_key` is the profile's, unioned with `dup_cluster_id`.

**Acceptance criteria.**
- Gates: embedding row count matches record count; exact duplicates 0; a cluster report is emitted.
- Known duplicate pairs from the corpus land in one cluster — 491 duplicate user turns, 1 duplicate (system, user) pair.
- No record is deleted by `dedup`; the count out equals the count in, with cluster fields added.
- `source_index` is rejected as a group key by an explicit test, since it is unique per record and gives no leakage protection.
- The 112-record catalog group shares one `group_key`.

**Source.** core requirements 22, 23, 24; profile § Dedup and grouping tests; profile Decisions (group split).

**Verify.** `uv run dvc repro embed dedup && uv run pytest tests/integration/test_dedup.py`

## T16 · Stub audio modality — the seam test

**Goal.** Prove the modality seam holds without building an audio modality.

**Context.** Typed content parts, media by reference, and the uniform privacy-span shape could not be retrofitted without touching all fifteen stages, so they are in now. This is the seam's only test until a real audio modality exists, and it is what stops the seam rotting.

**Blocked by.** T15.

**Relevant files.** `tests/integration/test_modality_seam.py`, `tests/fixtures/stub_audio/`.

**Proposed approach.** A stub modality returning one audio part with a `uri` and `sha256` and no inline bytes, paired with a trivial profile. Run `load` → `remove_invalid` → `pii_check` → `embed` and assert the stages neither inline the media nor crash. The stub's `privacy_detectors()` returns nothing for the audio part, which must make `pii_check` fail closed rather than pass the record through.

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

**Context.** The answer schema *is* the constraint, enforced inside the library — `info.ok is False` is the abstention, and there is no path where a malformed response becomes a truncated set. The panel must be family-diverse and clean: `model_family` collapses every unrecognised name to `"unknown"`, so a panel containing one is not proved diverse, it is unmeasured.

**Blocked by.** T9, T15, T17.

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

**Verify.** `uv run dvc repro jury && uv run pytest tests/integration/test_jury.py -v`

**Out of scope.** Juror weight calibration (needs the gold set — T25). The consensus tier of requirement 34.

## T19 · `agreement.py` — α over any δ, cohesion, plurality

**Goal.** The agreement statistics the jury and the aggregation stages both need, computed over an arbitrary distance.

**Context.** The `krippendorff` package covers nominal, ordinal, interval and ratio scales only, so α over a set-valued distance is written here. Its nominal degenerate case is tested against the library so the implementation is anchored.

**Blocked by.** T9.

**Relevant files.** `src/dataforce/shared/agreement.py`.

**Proposed approach.** α with a pluggable distance — the profile's `answer_distance`, δ in the formulas; cohesion as `1 − mean pairwise δ`; plurality. Nominal α delegates to the `krippendorff` package.

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

**Proposed approach.** Bucket on the two axes into `agreed`, `ambiguous_agreed`, `likely_label_error`, `hard_record`, with thresholds from `params.yaml`. Fill the queue from declared strata with declared quotas, always including a uniform random audit sample and the entire test split. This profile's strata are `likely_label_error`, `hard_record`, zero-label (deliberately oversampled, because it carries the corpus's real difficulty), the audit sample and the test split. Size the audit sample as `n = z²·p(1−p)/e²`, recomputing and requesting more if the observed rate exceeds the assumed `p`. Records with fewer than the minimum valid votes are excluded from triage rather than bucketed on thin evidence.

**Acceptance criteria.**
- Gate: every stratum met its quota; audit `n` ≥ computed.
- Bucket assignment matches a hand-built (cohesion, conflict) grid including boundary values.
- Audit sizing reproduces worked values: `p=0.05, e=0.02 → 457`; the profile default is `n = 500`.
- Every queued record records which stratum selected it and with what probability; the residual-error estimator refuses to run when any lacks one. — core invariant 15
- A record with one valid vote is excluded, not bucketed.

**Source.** core requirements 39–44; core invariant 15; profile requirements 20, 21, 22.

**Verify.** `uv run dvc repro rank_for_review && uv run pytest tests/integration/test_rank_for_review.py -v`

## T21 · Cross-border transfer review — blocking, not code

**Goal.** A written determination of where the corpus and each juror endpoint sit, completed before the first jury run against any offshore endpoint.

**Context.** The jury sends Vietnamese call-centre transcripts to several external LLM endpoints. Both specs name this as a prerequisite rather than a stage, and it is sharper here than in the core because of what the content is. Vietnam's PDPL 91/2025/QH15 and Decree 356/2025/ND-CP are in force.

**Blocked by.** T14 (so the review can state whether content is redacted at the point of transfer).

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

**Blocked by.** T4, T7.

**Relevant files.** `src/dataforce/pipeline/human_review/labelstudio/{config,client}.py`, `deploy/docker-compose.yml`.

**Proposed approach.** Compose the config from `modality.display_control(record)` and `profile.answer_control(record)`. For this profile the correction control is a dynamic `<Choices value="$tool_choices" choice="multiple">` populated from that record's own catalog plus an explicit "no tool" option, so a correction is a set drawn from the catalog by construction. All content and glossary HTML is built by the pipeline and **escaped**. The published payload's key set must equal an explicit **allowlist** — an allowlist, not a denylist, so a new field cannot leak by being forgotten.

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

**Proposed approach.** Follow `guided-validation`: focus chosen **by rule**, not by the LLM; batch pre-generation; token budget as a hard ceiling; idempotence on `(rid, prompt_version, model)`. For this profile the focus rule is the marker DSL. Prompts are files read with `read_txt` and filled with `slot_filling`; output comes from `complete_structured`.

**Acceptance criteria.**
- Gate: schema-valid ≥ 98%, measured from `ValidationInfo.ok`; estimated tokens ≤ budget.
- Re-running with the same `(rid, prompt_version, model)` produces byte-identical questions and makes no LLM call.
- A template whose fill values contain `{trigger}` and `{hold_missing}` returns them untouched; an uncovered `{{placeholder}}` is left in place rather than blanked.
- The generator's proposed answer is stored in the pipeline and appears in no published payload.

**Source.** core requirement 45; profile requirements 24, 25; profile invariant 1; [`guided-validation`](../guided-validation/spec.md) spec.

**Verify.** `uv run dvc repro generate_questions && uv run pytest tests/integration/test_generate_questions.py -v`

## T24 · `publish` and `pull` stages

**Goal.** Stages 8 and 9: questions reach annotators carrying nothing a model produced, and answers come back normalized.

**Blocked by.** T22, T23.

**Relevant files.** `src/dataforce/pipeline/human_review/{publish,pull}.py`.

**Proposed approach.** `publish` creates the project from the generated config, pushes the allowlisted payload, and is idempotent on `rid`. A gold set of ≥50 expert-labelled records is mixed in as ordinary tasks, visually indistinguishable. `pull` normalizes responses and **rejects, rather than repairs**, any response marked incorrect that carries no correction — rejected responses return to the queue with the reason attached. Corrections are asserted inside the profile's answer space at pull time, because a structural guarantee in someone else's UI is not one of ours.

**Acceptance criteria.**
- Gate: every incorrect verdict has a correction; the payload key set equals the allowlist.
- No vote, reasoning trace, consensus, cohesion, conflict, bucket, stratum, or generator answer appears in any published payload. All of it joins back on `rid` after pull. — core requirement 33, invariant 10
- Label Studio unreachable on publish retries with backoff five times, then fails with pushed tasks recorded; a re-run pushes no duplicate.
- A correction outside the answer space is rejected at pull time. — core invariant 11
- Gold records are indistinguishable from ordinary tasks in the payload.

**Source.** core requirements 33, 46, 48, 50, 51; core invariants 10, 11; core § Error Behavior (Label Studio, incorrect verdict).

**Verify.** `uv run dvc repro publish pull && uv run pytest tests/integration/test_publish_pull.py -v`

## T25 · `aggregate` stage and the pilot gate

**Goal.** Stage 10: two annotators become one verdict weighted by demonstrated reliability, and the five pilot thresholds are measured.

**Context.** This gate is the project's decision point. α below 0.667 means the guideline is broken, not the annotators, and the remedy is a guideline revision and a re-pilot — never a lower threshold. α above 0.95 on a subtle task means the questions dodge the hard cases.

**Blocked by.** T19, T24.

**Relevant files.** `src/dataforce/pipeline/human_review/aggregate.py`, `lib/{alpha,gold}.py`.

**Proposed approach.** Krippendorff's α on the verdict (nominal) across all overlapped records, per question focus and overall. Agreement on corrections as α with the profile's `delta`. Where overlap ≥ 2, aggregate verdicts with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote; aggregate corrections with the profile's `consensus`. Score each annotator continuously against the gold set, and use the same gold set to calibrate juror weights as mean set-F1 against human-validated labels.

**Acceptance criteria.**
- Gate: α on verdict ≥ 0.667; α ≤ 0.95 or a recorded investigation; question flag rate ≤ 10%; per-annotator gold accuracy ≥ 0.85; `likely_label_error` bucket precision ≥ 0.30.
- α below 0.667 hard-stops with the per-focus breakdown.
- α above 0.95 warns and requires a written review note carried into the datasheet.
- Bucket precision below its floor hard-stops; the panel or the thresholds change before the full corpus depends on them.
- An annotator below 0.85 on gold has work held pending review, with submitted answers re-queued for a second opinion rather than discarded.
- Each juror's gold-calibrated weight is reported, and a juror below the declared floor is dropped for that release with the drop recorded.

**Source.** core requirements 36, 50, 52, 53, 54, 64; profile requirements 15, 20; core § Error Behavior (α, bucket precision, annotator gold).

**Verify.** `uv run dvc repro aggregate && uv run pytest tests/integration/test_aggregate.py -v`

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

**Verify.** `uv run dvc repro curate && uv run pytest tests/integration/test_curate.py -v`

## T27 · Marker-DSL glossary confirmed in writing — blocking, not code

**Goal.** A written, agreed glossary of `{trigger}`, `{hold_other}`, `{hold_missing}`, `{constraint}`, `{turn_trigger}`, `{or}`, obtained before questions are generated.

**Context.** `guided-validation` declares this a blocking prerequisite, and the profile spec confirms the pilot is where it is obtained. The marker language is the annotator's only evidence; if two annotators read `{hold_other}` differently, α measures the glossary's ambiguity rather than the records' difficulty, and no threshold change fixes that.

**Blocks.** T23.

**Proposed approach.** Not a pipeline task. Write one definition per marker with a worked example from the corpus, have it reviewed by whoever owns the tool catalogs, and commit it under `config/templates/` so it ships in the annotation surface and in the datasheet.

**Acceptance criteria.**
- Every marker token the adapter can emit has a definition and a corpus example.
- The glossary is referenced by the generated Label Studio config, not pasted into it.
- A plausible-but-wrong question has no automated detector — the flag rate is the only signal, which is why 10% is a gate. The glossary is what makes the flag rate interpretable.

**Source.** profile § The marker DSL; [`guided-validation`](../guided-validation/spec.md) (blocking prerequisite); core § Error Behavior (final paragraph).

**Verify.** The glossary exists, covers every marker the adapter emits (asserted by a test comparing the two lists), and predates the first `generate_questions` run.

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

**Verify.** `uv run dvc repro` completes for both rungs; `metrics.json` carries α per focus, gold accuracy per annotator, flag rate, and bucket precision.

---

# Phase 6 — Release

**Goal:** a DVC-tracked `release/v1` reproducible from one git commit, with a fully human-validated test split, zero leakage, and documentation that states how the dataset was made.

## T29 · `split` stage and decontamination

**Goal.** Stage 12: train / validation / test where no scenario appears on both sides.

**Context.** Records sharing a catalog are near-variants of one scenario — the largest such group is 112 records — and a random split puts variants on both sides, inflating every metric. Every metric produced before such a fix would be void.

**Blocked by.** T26.

**Relevant files.** `src/dataforce/pipeline/release/split.py`, `lib/decontaminate.py`.

**Proposed approach.** Group-based on `group_key`, never random. A group is wholly in one split, and the same holds for any training subsample. The test split is **100% human-validated**: a record that has not been annotated cannot enter test at any budget, and `jury_consensus` records are barred permanently. Decontamination verifies zero n-gram overlap between test and train and zero shared `group_key`.

**Acceptance criteria.**
- Gate: zero group leakage; zero n-gram overlap. Either is a hard stop.
- A planted group spanning what would be a random split is caught, and so is a planted n-gram overlap.
- The 112-record catalog group is wholly in one split, as a named fixture. — profile invariant 5
- No test record has `validation.status` outside `{original, corrected}`. — core invariant 13

**Source.** core requirements 57, 58, 59; core invariants 12, 13; profile invariant 5; profile Decisions (group split).

**Verify.** `uv run dvc repro split && uv run pytest tests/integration/test_split.py -v`

## T30 · `export` stage, provenance, and training subsamples

**Goal.** Stage 13: training files in the shape a trainer expects, each record carrying where it came from.

**Blocked by.** T29.

**Relevant files.** `src/dataforce/pipeline/release/export.py`, `lib/manifest.py`.

**Proposed approach.** Emit the profile's training format — for `tool_decision`, SFT JSONL in the source `messages` shape with the curated label in both the assistant message and `meta.label`, asserted equal on the way out. Every exported record carries source SHA-256, pipeline version, modality and profile versions, `agent-toolkit` version, validation status, validator, dedup cluster, split, stratum, and the panel version where the jury touched it. Emit deterministic 25% / 50% / 100% subsamples of the training split, group-disjoint and recorded in the manifest. Dedup deletion happens here, from an explicit filter. Write `MANIFEST.sha256` listing every file's digest.

**Acceptance criteria.**
- Gate: test is 100% human-validated; counts reconcile against the stage inputs.
- `meta.label` equals the parsed assistant message on every exported record. — profile invariant 4
- Every exported record carries all eleven provenance fields.
- The three subsamples are group-disjoint, deterministic across runs, and listed in the manifest.
- Every answer in every exported artifact validates against `profile.answer_schema`. — core invariant 5

**Source.** core requirements 23, 60, 61; core invariant 5; profile requirements 18, 26; profile invariant 4.

**Verify.** `uv run dvc repro export && uv run pytest tests/integration/test_export.py -v`

## T31 · `document` stage: datasheet, data statement, Croissant

**Goal.** Stage 14: a consumer can judge this dataset without reading the pipeline.

**Context.** A corpus that is two-thirds machine-labelled must be documented as such, and the human-validated test split is the mitigation that makes the release measurable at all.

**Blocked by.** T30.

**Relevant files.** `src/dataforce/pipeline/release/document.py`, `lib/{datasheet,croissant}.py`.

**Proposed approach.** A datasheet (Gebru et al.), a data statement (Bender & Friedman), and a Croissant file validated by `mlcroissant`. The datasheet states the machine-labelled share explicitly — 14,241 of 21,172, 67.3%, by `gemma-4-31B-it`, and 1,358 records already relabelled once — and names the jury panel with each juror's family and gold-calibrated weight. It carries the residual-error estimate from the audit sample, any α-above-0.95 review note, the `enable_redact` setting, and the cross-border determination reference. Documentation is a gated stage: a missing required field fails the release.

**Acceptance criteria.**
- Gate: all required fields present; the Croissant file validates under `mlcroissant`.
- The datasheet names every juror with family and weight, and states the machine-labelled share.
- The residual-error estimate is present, with the stratum and selection probability of every record it was computed from. — core invariant 15
- A deliberately omitted required field fails the stage.

**Source.** core requirement 62; core requirement 65; profile requirement 27.

**Verify.** `uv run dvc repro document && uv run pytest tests/integration/test_document.py -v`

## T32 · Second profile — the genericity guard

**Goal.** A deliberately trivial single-label classification profile runs the whole graph end to end.

**Context.** Two profiles is the cheapest proof that the core is not secretly one profile's code. Everything before this task could pass while `pipeline/` quietly assumed set-valued answers.

**Blocked by.** T31.

**Relevant files.** `src/dataforce/profiles/simple_classification/`, `tests/e2e/test_second_profile.py`.

**Proposed approach.** Single-label classification over a 30-record text fixture: answer is one class, `answer_distance` is `0` if equal else `1`, `vote_consensus` is the mode. Run all fifteen stages with stubbed jurors, a stubbed generator and a containerized Label Studio.

**Acceptance criteria.**
- All fifteen stages complete for the second profile with no change to any module under `pipeline/` or `shared/`.
- Its own tests prove the five profile rules for a single-label answer. **If this profile arrives without them, that is the signal to build the suite after all** — see core Decisions.
- Any change required in `pipeline/` to make this pass is itself a defect report against the core, recorded before the change is made.

**Source.** core § Testing Strategy (Genericity); core invariant 16.

**Verify.** `uv run pytest tests/e2e/test_second_profile.py -v`

## T33 · End-to-end reproducibility in CI

**Goal.** `dvc repro` from a clean checkout reproduces every artifact's SHA-256. This passing is the definition of the pipeline being done.

**Blocked by.** T32.

**Relevant files.** `tests/e2e/test_smoke_reproducible.py`, `deploy/` CI config.

**Proposed approach.** The smoke rung *is* the integration test: `dvc repro` from raw to release against stubbed jurors, a stubbed generator and a containerized Label Studio, asserting a byte-identical `MANIFEST.sha256` on a second run.

**Acceptance criteria.**
- Two cold runs from a clean checkout produce identical `MANIFEST.sha256`. — core invariant 14
- The run is reproducible from one git commit plus `dvc repro`.
- CI runs it on every push.

**Source.** core requirement 61; core invariant 14; core § Testing Strategy (End to end).

**Verify.** `uv run pytest tests/e2e/test_smoke_reproducible.py`

---

## What this plan deliberately leaves out

Taken from the specs' own Out of Scope sections, restated so no task quietly picks them up: real image / audio / video modalities beyond the T16 stub; model training and evaluation; actual-token accounting, which needs `usage` on `agent-toolkit`'s `Completion`; local patches to `agent-toolkit`, since gaps there are fixed by a release there; Confident Learning; synthetic data generation; active learning; fine-tuning a juror; our own annotation service, which the T28 pilot gate decides; and automatic write-back to `fc_train_final.json`.
