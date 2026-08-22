# DataForce — Implementation Spec

**Status:** awaiting review · **Reads from:** [`objective.md`](objective.md) · **Replaces:** the spec deleted in `da50d46`

---

## What

DataForce turns a raw, model-labelled corpus into a training-ready dataset plus the evidence for
trusting it. This spec fixes the buildable surface of that pipeline: **two axes** (a *modality* —
`text2text`, `speech2text`, … — and a *profile* — function calling), **four main endpoints** (`load`,
`data_quality`, `ai_review`, `human_review`) each exposing its services as sub-endpoints, and **fifteen
services** that all have one signature — records in, records out — driven three ways from one
implementation: in-process, over HTTP, and from the command line.

`objective.md` says *why* and *what one record looks like*. This document says *what to build*: the
stage table, the two protocols, the package layout, the request and response shapes, the question
store, and what fails a run.

---

## Context

**What exists today.** `src/` was deleted in `da50d46` so the build could restart from `objective.md`
without two answers available for any question. What survives is deliberate: `tests/`, `config/`,
`params.yaml`, `dvc.yaml`, the `Makefile` and `pyproject.toml` all still describe the deleted package
and are here to be replaced or removed, not inherited.

Two things from the deleted tree are load-bearing and carried forward, because each is a guard rather
than a design opinion:

- **The guard tests.** `tests/unit/test_layout.py`, `test_layering.py`, `test_import_graph.py`,
  `test_no_reimplementation.py`, `test_manifests.py`, `test_naming.py`, `test_gate_runner.py`,
  `test_protocols.py`, `test_registries.py`, `test_flow.py`. They enforce §10 of the objective and are
  updated, not rewritten.
- **`tests/conftest.py` parses this file.** `CORE_SPEC = docs/annotation-pipeline/spec.md`, and
  `stage_table()` reads the *Stage table* below with the regex
  ``^\|\s*(\d+)\s*\|\s*([a-z_]+)\s*\|\s*`(\w+)`\s*\|``. Code is checked against that table, so the
  table's format is a contract, not decoration.

**No corpus is declared, and the one the deleted tree measured is not this project's.**
`fc_train_final.json` is out of use. Everything derived from it goes with it:
`metrics/corpus_profile.json`, `params.source.path` and `params.source.sha256`, the measured
`params.invalid_counts`, `params.gold.records`, `params.max_answer_cardinality`, and the symlinks under
`data/raw/`. **No number in this spec is inherited from it.**

The input is therefore what `objective.md` §2 documents and nothing else: standard OpenAI
chat-completion records carrying the tool catalog as data. `params.yaml` keeps the *shape* of those
keys — a declared source digest, and a declared expected count per validity check — and they are
populated by the first run over whatever corpus is declared, which is what makes a later drift a
decision rather than a surprise.

**What `agent-toolkit` already owns** and must not be re-implemented: `compute_hash`, `normalize_text`
(including `remove_tone_marks`, which the PII layer needs), `slot_filling`, `extract_json_from_text`,
atomic `read_jsonlines` / `write_jsonlines` / `read_yaml`, and the whole LLM client — `complete`,
`complete_structured`, `count_tokens`, retries, rate limiting.

---

## The two axes

Everything downstream is a composition of exactly two named things, and neither may do the other's job.

### Modality — how content is read and shown

**A modality is an input→output pair, named as one string.** `text2text`, `speech2text`, `image2text`,
`video2text`. `text`, `audio`, `image` and `video` are the vocabulary those names are built from; they
are not themselves registrable. This is what `objective.md` §3 writes on the record:
`branch.modality == "text2text"`.

```python
class Modality(Protocol):
    name: str                 # "text2text" — from the manifest filename, never a class body
    version: str
    def content_parts(self, item: Mapping[str, Any]) -> list[Part]: ...
    def embedding(self, parts: Sequence[Part]) -> list[float]: ...
    def personal_data_detectors(self) -> list[Detector]: ...
    def display_config(self, record: Record) -> UIControl: ...
```

Six members, closed. The modality owns the **display half** of the annotation config and nothing of the
capture half.

### Profile — what an answer is

**A profile is the dataset's own task.** One exists: `tool_decision` (function calling). A profile
declares the modality it composes with, and a run naming a different one hard-stops.

```python
class Profile(Protocol):
    name: str; version: str
    modality: str                                            # "text2text"
    def answer_schema(self, record: Record) -> dict: ...     # materialised, never persisted
    def answer_config(self) -> AnswerConfig: ...
    def build_record(self, item, parts, contract) -> Record: ...
    def validity_checks(self) -> list[ValidityCheck]: ...
    def answer_distance(self, a: Answer, b: Answer) -> float: ...
    def vote_consensus(self, votes: Sequence[Answer]) -> Answer | None: ...
    def question_text(self, record: Record) -> str: ...
    def scenario_hash(self, record: Record) -> str: ...
    def training_example(self, record: Record) -> Mapping[str, Any]: ...
```

Twelve members, closed. `MODALITY_MEMBERS & PROFILE_MEMBERS == {"name", "version"}` — neither axis may
drift into the other's job (`tests/unit/test_protocols.py`).

---

## The surface: four main endpoints, fifteen services

**A main endpoint is a phase; a sub-endpoint is one service.** `POST /data_quality` runs that phase's
three services in table order over the posted records. `POST /data_quality/pii_check` runs exactly one.
Both take and return the same body, so they compose.

### Stage table

The one copy of the flow. `src/dataforce/core/flow.py`, `src/dataforce/pipeline/<phase>/<stage>.py`,
`core/artifacts/<phase>.py` and every implementation's `<phase>.py` are checked against these rows.

| # | phase | stage | one line |
|---|---|---|---|
| 0 | load | `load` | every source item becomes one record with identity, content and provenance |
| 1 | data_quality | `validity` | the five checks that need no opinion, against declared counts |
| 2 | data_quality | `pii_check` | two-layer detection, typed placeholders, `content` rewritten |
| 3 | data_quality | `duplicate_check` | exact and near-duplicate groups, split by label agreement |
| 4 | ai_review | `jury` | N independent models answer the record's own task |
| 5 | ai_review | `cohesion` | how much the jury agrees with itself, and with the existing label |
| 6 | ai_review | `triage` | the two numbers become a bucket, a stratum and a review quota |
| 7 | human_review | `question_generate` | one answerable question per flagged record, with its evidence |
| 8 | human_review | `publish` | questions written to the question store, ready for the annotation tool |
| 9 | human_review | `annotator_answers` | responses read back out of the store onto the record |
| 10 | human_review | `aggregate` | overlap becomes one verdict with a confidence and an agreement statistic |
| 11 | human_review | `curate` | the verdict becomes the record's final label, or an adjudication |
| 12 | release | `split` | train / validation / test, with no scenario on both sides |
| 13 | release | `export` | the trainer-shaped artifact, per profile |
| 14 | release | `datasheet` | one document stating how the dataset was made |

**Phases 0–11 are in scope for this spec.** `release` (12–14) is declared here so the flow is complete
and the record's `release` key has an owner, and is specified in a follow-up — see *Out of Scope*.

### Routes

```
POST /load                              -> LoadResponse
POST /data_quality                      -> RecordsResponse     # validity -> pii_check -> duplicate_check
POST /data_quality/validity             -> RecordsResponse
POST /data_quality/pii_check            -> RecordsResponse
POST /data_quality/duplicate_check      -> RecordsResponse
POST /ai_review                         -> RecordsResponse     # jury -> cohesion -> triage
POST /ai_review/jury                    -> RecordsResponse
POST /ai_review/cohesion                -> RecordsResponse
POST /ai_review/triage                  -> RecordsResponse
POST /human_review                      -> RecordsResponse     # question_generate -> publish
POST /human_review/question_generate    -> RecordsResponse
POST /human_review/publish              -> RecordsResponse
POST /human_review/annotator_answers    -> RecordsResponse
POST /human_review/aggregate            -> RecordsResponse
POST /human_review/curate               -> RecordsResponse

GET  /branches                          -> registered modalities and profiles, with versions
GET  /healthz                           -> liveness, no engine, no store
```

`POST /human_review` stops after `publish` on purpose: stages 9–11 cannot run until people have
answered, so a phase endpoint that ran all five would either block or silently produce empty verdicts.

**`POST /human_review/publish/sync`** moves stored questions into Label Studio and stored answers back.
It is not a record-bus service: it takes no records, writes no record key, and is documented separately
under *The question store*.

---

## Requirements

Each is a statement a test can be pointed at.

### The record

1. Every service reads records and returns records. A service adds **exactly one key** and changes
   nothing else — except `pii_check`, which also rewrites `content` and bumps `content_version`
   (Requirement 14).
2. `record_id` is 16 lowercase hex over the canonicalised `content` parts. It does not depend on the
   record's position in the source file, and a shuffled re-ingest produces the same set of ids.
3. Order *within* a record is content; order *between* records is not.
4. A media part contributes its `sha256`, never its bytes, to `record_id`. Moving a file does not
   change an id; changing its content does.
5. `meta` is kept **verbatim**. Every key-set the source presents survives load unchanged, including
   keys no code recognises — what looks like noise now is what a later question turns out to need.
6. No record stores an answer space. `Record` has no such field, and constructing one with it raises.
7. Every key a service writes is written by exactly one service. The per-phase `<phase>_config` key is
   the single exception and is written by the **edge**, never by a service (Decision 5).
8. A record carries `provenance` written by `load`: source digest, offset, ingest time, both axis
   versions, and the run id (Decision 4).

### Load

9. The input is one shape: standard OpenAI chat-completion records with `tools` carried as data. A
   record with no `tools` key is an **empty catalog**, which is a quarantine for triage — not an
   invitation to parse a catalog out of the prose.
10. Which key holds the answer is **declared**, not assumed: the manifest's `label.at` names it, so a
    source calling it `target` or `gold` needs a manifest line and no code. An undeclared key raises,
    naming the manifest and what *is* declared.
11. One tool call spelled three ways — arguments as a JSON string, the same string with keys reordered
    and whitespace added, and the object form — is one part and one `record_id`.
12. Text content is loaded byte-identical to the source. No normalisation at load.
13. For a media modality, `load` resolves each item's URI through a resolver supplied at the edge,
    records `uri` + `sha256` + modality metadata, and never opens a file from engine code. A
    `MediaPart` without a reference cannot be constructed.

### Data quality

14. `pii_check` replaces detected values with **stable typed placeholders** scoped per record
    (`<CUSTOMER_ID_1>`), never deletes them, and a value used twice keeps one placeholder.
15. Detection runs two layers: patterns tuned for recall (and permitted to be noisy), then a model pass
    over a bounded window that sets precision. Patterns run against the raw text **and** against a
    tone-stripped normalisation, so `khong chin` is caught while patterns stay written in correct
    Vietnamese.
16. Spans are recorded against the content they were found in — `content_version` *before* the rewrite
    — and each names `part`, `start`, `end`, `class`, `verified`, `placeholder`.
17. The placeholder→original map is returned to the edge, is written outside version control, and no
    service may read it. A test asserts no module under `src/` reads it.
18. With `enable_redact: false` (the default), `pii_check` reports and leaves `content` untouched; the
    downstream personal-data scan then fails, so nothing ships. Turning it on is an edit to
    `params.yaml`, which makes the decision attributable.
19. `validity` runs the five declared checks, and each check's count is compared against
    `params.invalid_counts[<check>]`; a count that moves fails the run. Those numbers are populated by
    the first run over a declared source. Until one is declared the key is empty, and the gate reports
    its counts rather than comparing them.
20. `duplicate_check` reports two groups per record: `duplicate_content_same_label` and
    `duplicate_content_diff_label`. Near-duplicates use the modality's `embedding`, which is static, so
    two runs give identical groups.

### AI review

21. `jury` records one vote per model: the model name, whether the existing label is right, the model's
    own answer, and its reasoning. A vote that does not validate against the record's materialised
    answer schema is an **invalid vote**, counted and not silently dropped.
22. `cohesion` computes two numbers and writes no LLM call: agreement of the jury with itself, and
    agreement of the jury with the existing label. Re-running it costs nothing.
23. `triage` turns those numbers into a bucket, a stratum and a quota using thresholds from
    `params.thresholds.triage`. Re-tuning thresholds re-runs `triage` alone (Decision 3).
24. Thresholds live in configuration. `core/gates.py` and the triage logic contain no numeric literal
    other than `0` and a display cap.
25. No jury call is made to an offshore endpoint before the cross-border data-transfer review is
    recorded in the run manifest. The gate reads a declared field; it does not perform the review.

### Human review

26. `question_generate` produces one question at a time about one record, carrying the evidence and the
    glossary, with an enumerated answer set. Answering *incorrect* requires the corrected value.
27. **No model output may reach an annotator.** The generated annotation config and question payload
    contain no vote, no cohesion number, no bucket. A test asserts this on the payload, not on the UI.
28. The annotation config is composed from the modality's display half and the profile's capture half,
    and **neither may emit the other's**.
29. `publish` writes questions to the question store through a port supplied at the edge and records
    the receipt on the record. It does not talk to Label Studio.
30. `annotator_answers` reads responses out of the store. It does not talk to Label Studio either.
31. `aggregate` produces one verdict per record with a method name, a confidence, and the overlap it
    was computed from; incomplete overlap uses Krippendorff's α.
32. `curate` writes the final label with `status`, the validators who produced it, and — where they
    disagreed — who adjudicated.

### Running it

33. No module under `modalities/`, `profiles/`, `pipeline/` or `core/` opens a file, imports
    `agent_toolkit.file_utils`, imports `dataforce.api` or `dataforce.declared`, or names `config/`,
    `data/`, `metrics/` or `params.yaml` in code. A docstring saying where policy lives is prose and is
    exempt.
34. Importing `dataforce.modalities.text2text` and `dataforce.profiles.tool_decision` from a directory
    holding no `config/` succeeds and writes nothing.
35. No module under `pipeline/` or `core/` imports a concrete modality or profile. Both axes arrive
    through a registry.
36. A registry is instance state. Two registries in one process hold different implementations, and
    registering a second implementation of one name is refused.
37. Identity is never assigned in a class body. `name`, `version` and `modality` come from
    `config/<axis>/<name>.yaml`, whose **filename is its identity**, and `version` must be a string.
38. Every stage runs the `conservation` gate: `output + quarantined + deduped_out == input`, exactly, no
    tolerance. A failing gate writes `GATE_FAILED.json` with assertion, observed, expected and up to
    `MAX_OFFENDING_RIDS` offending ids, and exits non-zero.
39. No stage consumes an input whose upstream gate did not pass.
40. A run records every policy file it read with its digest, both axis versions, and every artifact
    digest. Two runs of one unchanged configuration produce byte-identical run manifests; a changed
    policy file changes the manifest.
41. The HTTP layer, the CLI and an in-process caller reach the same function. A response body from
    `POST /data_quality/pii_check` and the record written by `dataforce pii_check` are equal.

---

## Design

### Package layout

```
src/dataforce/
  core/            # engine: shapes and rules, no filesystem, no axis
    record.py        DEFINITION · Record, TextPart, MediaPart, Span, Provenance, compute_rid
    flow.py          DEFINITION · PHASES, the stage table's phase column
    gates.py         LOGIC     · GateResult, conservation, assert_gates (no thresholds)
    manifest.py      DEFINITION · Manifest, require()
    errors.py        DEFINITION · ConfigError, GateFailed
    artifacts/       one module per phase: <phase>.py + base.py
  pipeline/        # engine: one module per stage, grouped by phase
    load/load.py
    data_quality/{validity,pii_check,duplicate_check}.py
    ai_review/{jury,cohesion,triage}.py
    human_review/{question_generate,publish,annotator_answers,aggregate,curate}.py
  modalities/
    base.py registry-facing protocol
    text2text/       __init__ schema utils + data_quality ai_review human_review release
    speech2text/     declared seam; not built (see Out of Scope)
  profiles/
    base.py
    tool_decision/   the same seven files
  declared/        # edge: reads config
    manifest.py thresholds.py prompts.py
  api/             # edge: composition root, artifacts, HTTP
    engine.py registry.py run.py artifacts.py
    routers/{load,data_quality,ai_review,human_review}.py
    store/{models,repository,session}.py
    app.py
  cli.py
```

**The layout is the flow.** Every implementation of either axis is the same seven files: `__init__`,
`schema` (`DEFINITION ·`), `utils` (`LOGIC ·`), and one module per record-bearing phase —
`data_quality`, `ai_review`, `human_review`, `release` — each opening
`STEP · <phase> (stages N-M) · …`. No phase module imports a sibling phase module; anything two phases
need lives in `schema.py` or `utils.py`; `schema.py` does not import `utils.py`.

`load` has no per-implementation phase module: it calls the modality's `content_parts` and the
profile's `build_record`, both of which live in `utils.py`/`schema.py`. Its stage module is
`pipeline/load/load.py`, opening `STEP · load (stage 0) · …`.

**Import direction, declared once in the package docstring and enforced by test:** `api/`, `declared/`
and `cli.py` may import the engine. The engine may not import them.

### The record

The bus, with the corrections `objective.md` §3's illustrative JSON needs (its example uses Python
`True`, leaves several values as prose, and its brace nesting puts `human_review` inside `ai_review`):

```jsonc
{
  "record_id": "3f9a1c0b7e4d2856",          // 16 hex over canonicalised content
  "source_id": "s4471",
  "branch":     { "modality": "text2text", "profile": "tool_decision" },
  "provenance": { "source_file_sha256": "a1b2c3d4…", "offset": 4471,
                  "ingested_at": "2026-08-22T00:00:00Z",
                  "modality": "text2text@1", "profile": "tool_decision@1",
                  "run_id": "r_2026-08-22T00:00:00Z_9f3c" },

  "content": [ { "type": "text", "role": "user", "text": "Mã của mình là <CUSTOMER_ID_1>." } ],
  "content_version": 2,

  "label": [ { "name": "SendStatement", "arguments": { "ma_khach": "<CUSTOMER_ID_1>", "ky": "thang_nay" } } ],
  "meta":  { "human_checked": true },       // verbatim, every key

  "data_quality": {
    "data_quality_config": { "…": "resolved config + digest, written by the edge" },
    "validity":        { "passed": true, "failed_checks": [], "quarantined": false },
    "pii_check":       { "decision": "redacted", "content_version_scanned": 1,
                         "spans": [ { "part": 3, "start": 16, "end": 22, "class": "CUSTOMER_ID",
                                      "verified": true, "placeholder": "<CUSTOMER_ID_1>" } ],
                         "classes": ["CUSTOMER_ID"], "unverified": 0 },
    "duplicate_check": { "duplicate_content_same_label": ["…"],
                         "duplicate_content_diff_label": ["…"] }
  },

  "ai_review": {
    "ai_review_config": { "judge_llm_models": [ { "model_name": "…", "max_tokens": 4096, "temperature": 0.1 } ] },
    "jury":     { "panel_version": 2, "prompt_version": "jury_vote.v1",
                  "llm_votes": [ { "model_name": "…", "label_is_right": true,
                                   "answer": [], "reasoning": "…", "valid": true } ],
                  "invalid_votes": 0, "plurality": [], "final_prediction": [] },
    "cohesion": { "self_agreement": 0.83, "label_agreement": 0.42, "method": "…" },
    "triage":   { "bucket": "…", "stratum": "…", "selected_for_review": true, "reason": "…" }
  },

  "human_review": {
    "human_config":      { "annotators": [], "question_generator": { "model_name": "…" } },
    "question_generate": [ { "question_id": "…", "question_name": "…", "content": "…", "enum": [] } ],
    "publish":           { "stored": ["question_id"], "store_run_id": "…", "published_at": "…" },
    "annotator_answers": { "responses": [ { "annotator_id": "u_14", "question_id": "…",
                                            "verdict": "…", "note": null, "submitted_at": "…" } ] },
    "aggregate":         { "verdict": "…", "method": "majority_gold_weighted",
                           "confidence": 0.94, "overlap": 2, "alpha": 0.81 },
    "curate":            { "status": "original", "label": [], "validators": ["u_14", "u_09"],
                           "adjudicated_by": null, "decided_at": "…" }
  },

  "release": {}
}
```

### Per-service contracts

**Reads** is the set of keys a service may look at; anything else is none of its business. **Writes** is
the one key it owns. **Gate** fails the run rather than passing bad data on. `conservation` runs on
every stage and is not repeated in the table.

#### `load` — stage 0

| # | stage | reads | writes | gate |
|---|---|---|---|---|
| 0 | `load` | the raw item, under the declared contract | the whole record: `record_id`, `source_id`, `branch`, `provenance`, `content`, `content_version = 1`, `label`, `meta` | source digest matches `params.source.sha256`; record count matches; no duplicate `record_id` from distinct content |

Load resolves the declared `shape`, reads the label from the declared key (`label.at`), maps declared
`meta` keys, and derives nothing it can read. The catalog is **not** copied onto the record as an answer
space; `answer_schema` materialises it from the record when asked and never persists it.

#### `data_quality` — stages 1–3

| # | stage | reads | writes | gate |
|---|---|---|---|---|
| 1 | `validity` | `content`, `label`, `meta` | `data_quality.validity` | each check's count equals `params.invalid_counts[<check>]`, once declared |
| 2 | `pii_check` | `content` | `data_quality.pii_check`, **and rewrites `content`, bumping `content_version`** | every high-recall hit verified or `decision == "withheld"`; zero literal personal data in `content` afterwards |
| 3 | `duplicate_check` | `content`, `label` | `data_quality.duplicate_check` | group membership is symmetric and transitively closed |

The five validity checks are the profile's, not the engine's — `validity_checks()` is a profile
member: `label_assistant_mismatch`, `label_not_in_catalog`, `empty_catalog`,
`label_cardinality_anomaly`, `label_names_one_tool_twice`. Each carries a declared expected count in
`params.invalid_counts`, and a check reading 0 is what tells you when it stops reading 0.

**PII, in two layers.** Layer one is patterns over the raw text and over
`normalize_text(text, remove_tone_marks=True)`, covering the Vietnamese spoken forms an off-the-shelf
scrubber misses: digits as words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), `@` as `a còng`, `.` as
`chấm`. It is tuned for recall and is *allowed* to be noisy — a digit run is also a price, a date, an
order reference. Layer two is a model pass over a bounded window that marks each hit `verified` or not.
The placeholder→original map is returned to the edge alongside the records and written to a path the
edge chooses, which `.gitignore` covers.

#### `ai_review` — stages 4–6

| # | stage | reads | writes | gate |
|---|---|---|---|---|
| 4 | `jury` | `content`, `label`, materialised answer schema | `ai_review.jury` | panel size ≥ floor; invalid-vote rate ≤ ceiling; estimated tokens ≤ ceiling; cross-border review recorded |
| 5 | `cohesion` | `ai_review.jury`, `label` | `ai_review.cohesion` | every record with a jury has both numbers |
| 6 | `triage` | `ai_review.cohesion`, `data_quality` | `ai_review.triage` | every record lands in exactly one bucket; quotas sum to the declared review budget |

Three stages rather than one, because they fail and re-run for different reasons: `jury` costs money and
is cached, `cohesion` is pure arithmetic, and `triage` is re-run on **exactly one** threshold re-tuning
pass after the pilot. A bucket whose precision the pilot cannot establish gets **no quota**.

#### `human_review` — stages 7–11

| # | stage | reads | writes | gate |
|---|---|---|---|---|
| 7 | `question_generate` | `content`, `label`, `ai_review.triage` (selection only) | `human_review.question_generate` | the payload contains no vote, no cohesion number, no bucket; the glossary exists |
| 8 | `publish` | `human_review.question_generate`, modality display half, profile capture half | `human_review.publish` | every question stored exactly once; the generated config validates |
| 9 | `annotator_answers` | the store | `human_review.annotator_answers` | every response names a question that was published |
| 10 | `aggregate` | `human_review.annotator_answers` | `human_review.aggregate` | overlap ≥ the rung's floor; α ≥ the declared floor |
| 11 | `curate` | `human_review.aggregate`, `label` | `human_review.curate` | an `incorrect` verdict carries a corrected value |

Stage 7 reads `triage` **only to decide which records get a question**. Nothing it reads from `ai_review`
reaches the payload, which is what Requirement 27 asserts.

### Engine and edge

The engine computes; the edge supplies everything that came from a file, a socket or a clock.

```python
# api/engine.py — the composition root every caller enters by
engine = api.open_engine(profile="tool_decision", modality="text2text",
                         config_root=Path("config"), params=Path("params.yaml"))
```

`open_engine` reads the two manifests, the thresholds and the prompt templates, registers both axes,
and returns an `Engine` holding the resolved pair, the registry, and the tuple of policy files it read.
Naming no modality takes the profile at its word; naming a different one raises `ConfigError` saying
which modality the profile composes with.

An engine can also be built with **no filesystem anywhere** — both axes handed `Manifest` objects, a
template string and an integer — which is what makes a web handler, a notebook and a test the same
caller.

Every service is:

```python
def pii_check(engine: Engine, records: Iterable[Record], *,
              detectors: Sequence[Detector] | None = None) -> ServiceResult: ...
```

`ServiceResult` carries `records`, `gates: list[GateResult]`, and any **side output** the edge must
persist (for `pii_check`, the placeholder map; for `publish`, the rows to store). The engine returns
side output; it never writes it.

### HTTP surface

One FastAPI app, one router per main endpoint, one route per service. Handlers are thin: resolve the
engine, call the service, record gates, return.

**Request** (every service route):

```jsonc
{
  "branch":  { "modality": "text2text", "profile": "tool_decision" },
  "config":  { "…": "phase config overriding the resolved defaults; optional" },
  "records": [ { "record_id": "…", "…": "…" } ]
}
```

**Request to `POST /load`** — this is the one route that does not take records, and the one place the
modality axis changes the shape of the request:

```jsonc
{
  "branch": { "modality": "text2text", "profile": "tool_decision" },
  "items":  [ { "id": "s4471", "messages": [ ], "tools": [ ], "meta": { } } ],
  "source": { "uri": "data/raw/<the declared source>.json", "sha256": "a1b2c3d4…" }
}
```

`items` and `source` are mutually exclusive and one is required. **For `text2text`, `items` inline is
the normal case** — the content is already in the body and nothing needs reading. For `speech2text`,
`image2text` and `video2text`, each item references its media by URI; `load` resolves it through a
`MediaResolver` supplied at the edge, records `uri` + `sha256` + duration/dimensions, and the engine
never opens it.

**Response:**

```jsonc
{
  "records": [ ],
  "gates":   [ { "gate": "conservation", "ok": true, "assertion": "…", "observed": { }, "expected": { } } ],
  "run":     { "run_id": "…", "producer": { "modality": "text2text@1", "profile": "tool_decision@1" },
               "policy": { "config/profiles/tool_decision.yaml": "6858…" } }
}
```

**A failing gate is `422`**, body `{"error": "gate_failed", "gate": "...", "assertion": "...",
"observed": {...}, "expected": {...}, "offending_record_ids": [...]}`, and the response carries **no
records** — the point of a gate is that bad data does not pass on. `ConfigError` is `400`. An unknown
profile or modality is `400` naming the ones that exist.

### The question store

`publish` writes to a database we own; a separate sync moves questions into Label Studio and answers
back out. Three tables, owned by `api/store/`:

| table | columns |
|---|---|
| `question` | `question_id` pk, `record_id`, `run_id`, `modality`, `profile`, `payload` json, `config_digest`, `created_at` |
| `publication` | `question_id` fk, `external_system`, `external_project_id`, `external_task_id`, `status`, `pushed_at`, unique (`question_id`, `external_system`) |
| `annotator_answer` | `answer_id` pk, `question_id` fk, `annotator_id`, `verdict`, `corrected_value` json, `note`, `submitted_at`, `external_annotation_id` unique |

- The engine knows none of this. `publish` returns rows; `api/store/repository.py` writes them behind a
  `QuestionStore` port, and the DSN is read at the edge from `DATAFORCE_DATABASE_URL`.
- **SQLite by default, Postgres by URL.** SQLAlchemy 2.0 declarative models, Alembic migrations.
- `POST /human_review/publish/sync` pushes unpublished questions into Label Studio through
  `label-studio-sdk`, writes the returned task ids into `publication`, then pulls new annotations into
  `annotator_answer`. It is idempotent: a question already carrying a `publication` row for that system
  is not pushed again, and an annotation whose `external_annotation_id` is present is not re-inserted.
- Running the sync is optional. Every other endpoint works with no Label Studio anywhere, which is what
  keeps the pipeline testable and the pilot unblocked.

### Configuration

Unchanged in shape from what is committed: `config/<axis>/<name>.yaml` for identity and declarations,
`config/gates.yaml` for what each gate compares against, `config/prompts/…` for templates, and
`params.yaml` for every threshold. `config/modalities/text.yaml` is **renamed** to
`config/modalities/text2text.yaml` — the filename is the identity, so the rename *is* the change
(Decision 2). `params.thresholds` gains the keys the new stages read: `jury`, `triage`, `pilot` already
exist and are empty; `pii` and `duplicate` are added.

---

## Decisions

**1 · HTTP is the primary surface; the engine is the same one function.**
Four routers, one route per service, over the record-in/record-out functions that the CLI and
in-process callers use. *Alternative:* functions and CLI only, with HTTP as a later spec — which
`objective.md` §9 leans toward when it calls the web view "a later task". *Why this:* §9 defers the
*view*, not the API, and §8 already requires two shells over one implementation; adding a third shell
costs a thin handler per route and no logic. *Reversible:* yes — deleting `api/routers/` and `app.py`
leaves the engine and CLI intact.

**2 · A modality is the input→output pair, named as one string.**
`text2text`, `speech2text`, `image2text`, `video2text`; `text`/`audio`/`image`/`video` are the vocabulary
those names are built from and are not registrable. *Alternative:* the atomic input medium, with the
output half coming from the profile. *Why this:* `objective.md` §3 writes `branch.modality =
"text2text"` on the record, and the display half of the annotation config genuinely depends on both
halves. *Cost:* `speech2text` and `text2text` will share text-rendering code, which goes in a shared
helper rather than a base class. *Reversible:* costly — the name is stamped into every record's
`branch` and `provenance`.

**3 · `ai_review` is three stages, not one.**
`jury` → `cohesion` → `triage`. *Alternative:* one `jury` stage writing votes, agreement and bucket
together, which is what `objective.md` §3's record shows. *Why this:* they fail and re-run for
different reasons. The jury costs money per record and must be cached; cohesion is pure arithmetic over
what the jury wrote; triage reads thresholds that `objective.md` §8 says are *provisional until the
pilot measures them* and get one re-tuning pass. Folding them together means re-tuning a bucket
boundary re-runs the panel. *Reversible:* yes, and it is the arithmetic that makes `human_review`
stages 7–11.

**4 · The record carries a `provenance` key.**
`objective.md` §1 requires "per-record provenance for every record and every label"; §3's record
example carries only `source_id`. Those two cannot both be satisfied, so this spec adds one key written
by `load`. *Alternative:* keep provenance only in the run manifest, which is where policy and artifact
digests live. *Why this:* a record separated from its run — and export produces exactly that — would
otherwise carry no statement of what made it. *Reversible:* yes, one key, one writer.
`Assumption:` `run_id` is generated at the edge, not in the engine, because the engine has no clock.

**5 · The `<phase>_config` key is written by the edge.**
`objective.md`'s record puts `data_quality_config`, `ai_review_config` and `human_config` inside each
phase, and §10 says one writer per key. If the first service of a phase wrote it, calling a
sub-endpoint alone would produce a different record than calling the phase endpoint. *Why this:*
resolving config is already an edge job — no service may name a config location — so the edge stamps the
resolved config and its digest when it enters the phase, and services read it. *Reversible:* yes.

**6 · `publish` writes to our own store; Label Studio is a separate sync.**
Chosen over calling the Label Studio API directly from `publish`. *Why this:* the pipeline stays
runnable and testable with no Label Studio instance, and `annotator_answers` reads one shape whatever
the annotation tool is. *Cost:* task state exists in two places, so the sync must be idempotent in both
directions — the `unique (question_id, external_system)` and `unique external_annotation_id`
constraints are what enforce that. *Reversible:* yes; the store is behind a port.

**7 · SQLite by default, Postgres by URL, SQLAlchemy + Alembic.**
*Alternative:* Postgres only. *Why this:* a developer running the pilot should not need a database
server, and the schema is small enough that the two behave identically. *Reversible:* yes — one DSN.

**8 · One input shape.**
Standard OpenAI chat-completion records with `tools` as data — what `objective.md` §2 documents, and
nothing else. *Alternative:* also read a catalog rendered as prose into the system prompt, which is what
the deleted `legacy_system_prompt` reader did for `fc_train_final.json`. *Why this:* that corpus is out
of use, so the second reader has no caller, and AGENTS.md §2 forbids flexibility nobody asked for — it
was a prose parser plus a 437-line test module earning nothing. *Reversible:* yes, and cheaply — the
reader is recoverable at `ed84417^`, and re-admitting it means a declared `shape` key and a second
`catalog_from_*` function, not a change to any service.

**9 · The existing tests are updated, not restarted; the fixtures are replaced.**
The guard tests listed in *Context* encode `objective.md` §10 and are kept. The tests that assert the
old flat record — `test_record.py`, `test_data_quality.py`, `test_answers.py`, `test_answer_space.py`,
`test_artifact_schemas.py` — are rewritten against the bus. `test_catalog_format.py` and
`tests/fixtures/tool_decision/catalogs/` go with the prose reader (Decision 8), and so do `records.json`
and `test_tool_decision_corpus.py`, which are the retired corpus's shape. `canonical_records.json` and
`declared_input.json` are already `objective.md` §2's shape and are the seed for the new fixture set.
`Assumption:` new fixtures are invented, never extracted from real data (AGENTS.md §9).

---

## Versions

| Thing | Version | Why / source |
|---|---|---|
| Python | 3.12 (`>=3.12,<3.13`) | unchanged; `.python-version` |
| FastAPI | `>=0.141.1` | current release, PyPI, requires Python ≥3.10 |
| Uvicorn | `>=0.52.4` | current release, PyPI |
| SQLAlchemy | `>=2.0.52,<2.1` | current 2.0.x, PyPI; 2.0 declarative style |
| Alembic | `>=1.19.1` | current release, PyPI |
| label-studio-sdk | `>=2.1.1` | current release, PyPI; used only by the sync |
| Label Studio (server) | 1.23.0 | current release; pinned in `deploy/` compose, not a Python dependency |
| pydantic | `>=2.13` | unchanged |
| agent-toolkit | `@v0.1.0` git tag | unchanged; the tag has moved once, so `uv.lock` is the record |
| model2vec | `>=0.9` | unchanged; static embeddings keep dedup reproducible |
| pandera / pandas | `>=0.32.1` / `>=2.2` | unchanged |

`fastapi`, `uvicorn`, `sqlalchemy`, `alembic` are runtime dependencies. `label-studio-sdk` goes in an
optional `[label-studio]` extra, so the pipeline installs without it.

---

## Invariants

Each has a named check.

| # | Invariant | Checked by |
|---|---|---|
| I1 | The engine opens no file and names no path | `test_layering.py`, plus a subprocess import from an empty directory |
| I2 | `pipeline/` and `core/` import no concrete axis | `test_import_graph.py` |
| I3 | Code's phase and stage names are this table's | `test_flow.py`, parsing this document |
| I4 | Every implementation is the same seven files, and no phase module imports a sibling | `test_layout.py` |
| I5 | Identity comes from the manifest filename, never a class body | `test_manifests.py` |
| I6 | Nothing re-implements an `agent-toolkit` function or imports a dependency it owns | `test_no_reimplementation.py` |
| I7 | One writer per record key | a new `test_record_bus.py`: run every service, assert each wrote only its own key |
| I8 | `record_id` is stable across a shuffled re-ingest and sensitive to content | `test_record.py` |
| I9 | No answer space is ever stored | `Record` has no such field; constructing one raises |
| I10 | Conservation holds at every stage | `test_gate_runner.py` and each stage's own test |
| I11 | No model output reaches an annotator | assert on the `publish` payload and the generated config |
| I12 | The placeholder map is never read by a service and never committed | AST scan + `.gitignore` assertion in `test_repo_hygiene.py` |
| I13 | Two runs of one unchanged configuration produce identical run manifests | `test_api.py` |
| I14 | HTTP, CLI and in-process produce the same record | a new `test_three_shells.py` |

---

## Error behavior

| Situation | Behaviour |
|---|---|
| Source digest ≠ `params.source.sha256` | `load` hard-stops before reading a record |
| Undeclared `shape`, role, or label key | `ConfigError` naming the manifest, the key, and what *is* declared |
| Unknown profile or modality | `ConfigError` listing the registered ones; empty registry says "none" |
| Profile and modality disagree | `ConfigError`: "composes with modality 'text2text'" |
| A gate fails | `GateFailed` with every result attached, passing ones included; `GATE_FAILED.json` written by the edge; exit non-zero; HTTP `422` with no records |
| Upstream `GATE_FAILED.json` present | the next stage refuses to start (`upstream_ok`) |
| A jury vote does not validate | counted as an invalid vote, kept with `valid: false`, never silently dropped; the invalid-vote-rate gate decides whether the run continues |
| A model call fails after retries | `agent-toolkit` owns retry and rate limiting; an exhausted call is one missing vote, and the panel-floor gate decides |
| `enable_redact: false` and personal data found | `pii_check` reports, `content` untouched, `decision: "reported"`; the downstream scan gate fails so nothing ships |
| Label Studio unreachable during sync | the sync fails; no record key changes, no `publication` row is written, and every other endpoint is unaffected |
| A question is synced twice | the unique constraint makes the second a no-op |

---

## Testing Strategy

**What proves it.** `make check` (ruff, `mypy --strict`, pytest excluding `integration`) must pass, and
`make integration` must pass before a release.

1. **Guard tests first.** I1–I6 above are AST and subprocess checks that already exist and each is
   proved against synthetic source, so the guard fails before it has ever been needed. They are updated
   for the new phase and stage names in one commit and must be green before any service is written.
2. **One test module per stage**, asserting the reads/writes/gate row of the table above: the service
   writes its key, writes nothing else, and its gate fails on the input it exists to catch.
3. **The bus property (I7)**, once: build a record, run all twelve in-scope services, diff the record
   after each against the record before, assert the diff is exactly one key.
4. **The three shells (I14)**: the same input through `api.pii_check(...)`, `POST
   /data_quality/pii_check`, and `dataforce pii_check`, asserted equal.
5. **Fixtures, not a corpus.** Every unit test runs against invented fixtures under
   `tests/fixtures/tool_decision/`, in `objective.md` §2's shape. There is no corpus-wide test until a
   source is declared; when one is, it asserts the validity counts against `params.invalid_counts`
   under `-m integration` and nowhere else.
6. **PII gets adversarial fixtures**: spoken digits with and without tone marks, `a còng`, `chấm`, a
   value used twice in one record (one placeholder), and a digit run that is a price rather than an
   identifier (layer one flags it, layer two clears it).
7. **The store**: SQLite in `tmp_path`, and idempotency asserted by running the sync twice against a
   fake Label Studio client.
8. **No network in `make check`.** Every jury test uses a stubbed panel; the live panel is the Smoke
   rung, under `-m integration`.

---

## Out of Scope

- **`release` — stages 12–14** (`split`, `export`, `datasheet`). Declared in the stage table so the flow
  is complete and `record.release` has an owner; specified in a follow-up. Nothing in phases 0–11 may
  assume its shape.
- **The web view.** One router and one page over the same functions, on the house FastAPI + Vite pattern
  — `objective.md` §9 calls it a later task, and this spec keeps it one.
- **Real `speech2text`, `image2text`, `video2text`.** The seam is specified — `MediaPart`, the
  `MediaResolver` port, the pair naming — and unenforced. Only `text2text` is built.
- **Our own annotation platform.** Deferred, not cancelled; the pilot decides.
- **Model training and evaluation, synthetic data generation, active learning, fine-tuning a juror,
  Confident Learning**, and automatic write-back to any source file. Export produces an artifact;
  putting it anywhere is a human step.
- **The two blocking prerequisites that are not code**: the cross-border data-transfer review before the
  first offshore jury call, and the written glossary before the first generated question. This spec
  gates on their being *recorded*; it does not perform them.
