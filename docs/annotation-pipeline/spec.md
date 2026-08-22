# DataForce — Implementation Spec

**Status:** awaiting review · **Reads from:** [`objective.md`](objective.md) · **Style reference:**
the internal `agent-evaluation` service, which `agent-toolkit` was extracted from

---

## What

DataForce turns a raw, model-labelled corpus into a training-ready dataset plus the evidence for
trusting it. This spec fixes the buildable surface of that pipeline: **two axes** (a *modality* —
`text2text`, `speech2text`, … — and a *profile* — function calling), **four main endpoints**
(`load_data`, `data_quality`, `ai_review`, `human_review`) each exposing its services as sub-endpoints,
and **fifteen services** that all have one signature — records in, records out — driven two ways from
one implementation: over HTTP, and in-process.

`objective.md` says *why* and *what one record looks like*. This document says *what to build*: the
flow, the two protocols, the package layout, the request and response shapes, the question store, and
what fails a run.

---

## Context

**The tree is empty on purpose.** `src/` was deleted in `da50d46` so the build could restart from
`objective.md` without two answers available for any question, and `tests/` is deleted in this pass for
the same reason: it described the deleted package, and a spec written to keep it green would inherit a
design nobody chose. **Nothing in this document is shaped by a file that used to exist.** `config/`,
`params.yaml`, `dvc.yaml`, the `Makefile` and `pyproject.toml` are still the old package's and are
replaced by the rebuild, not inherited.

**No corpus is declared.** `fc_train_final.json` is out of use, and everything derived from it goes with
it: `metrics/corpus_profile.json`, `params.source.path` and `params.source.sha256`, the measured
`params.invalid_counts`, `params.gold.records`, `params.max_answer_cardinality`, and the symlinks under
`data/raw/`. **No number in this document is inherited from it.** The input is what `objective.md` §2
documents and nothing else: standard OpenAI chat-completion records carrying the tool catalog as data.
`params.yaml` keeps the *shape* of those keys — a declared source digest, and a declared expected count
per label check — populated by the first run over whatever corpus is declared, which is what makes a
later drift a decision rather than a surprise.

**The style reference is a real codebase, not a preference.**
`/mnt/e/FCI_PROJECT/agent-evaluation-dev` is the internal service this project's `agent-toolkit` was
extracted from, and it settles four things this spec would otherwise invent:

- `api/main.py` holds a `create_app()` factory; `api/routers/<domain>/<feature>.py` holds one
  `APIRouter(tags=[…])` per feature; `main.py` mounts each with a URL prefix.
- **URLs are kebab-case** (`/evaluate-function-calling`), module names snake_case.
- **Every field of every request, response and record model carries `Field(..., description=…)`**, and
  related fields are grouped under `# --- Section ---` comments. This is Requirement 1 below.
- A router handler is thin: call the service, map `ValueError` → `400` and anything else → `500`.

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
    """One input→output pair: how its content is read, embedded, scanned and shown."""

    name: str      # "text2text" — comes from the manifest filename, never a class body
    version: str   # stamped into every record's provenance, so it is a string, not a number

    def content_parts(self, item: Mapping[str, Any]) -> list[Part]:
        """One source item's turns, as ordered parts. Text verbatim, media by reference."""

    def embedding(self, parts: Sequence[Part]) -> list[float]:
        """A static vector for near-duplicate grouping. Same input, same vector, every run."""

    def personal_data_detectors(self) -> list[Detector]:
        """The high-recall pattern layer, in this modality's terms."""

    def display_config(self, record: Record) -> DisplayConfig:
        """The *display* half of the annotation config. Never the capture half."""
```

Six members, closed.

### Profile — what an answer is

**A profile is the dataset's own task.** One exists: `tool_decision` (function calling). A profile
declares the modality it composes with, and a run naming a different one hard-stops.

```python
class Profile(Protocol):
    """One dataset task: what an answer is, how two answers differ, what makes one invalid."""

    name: str       # "tool_decision" — from the manifest filename
    version: str
    modality: str   # "text2text" — the pair this profile composes with; a mismatch hard-stops

    def answer_schema(self, record: Record) -> dict:
        """The permitted answers, materialised from *this record's* catalog. Never persisted."""

    def answer_config(self) -> AnswerConfig:
        """How an answer is controlled: cardinality ceiling, argument handling."""

    def build_record(self, item: Mapping[str, Any], parts: Sequence[Part]) -> Record:
        """One source item into one record. The only place a source shape is read."""

    def label_checks(self) -> list[LabelCheck]:
        """The checks that need no opinion, each named for the defect it finds."""

    def answer_distance(self, a: Answer, b: Answer) -> float:
        """0.0 identical, 1.0 unrelated. What `cohesion` averages over."""

    def vote_consensus(self, votes: Sequence[Answer]) -> Answer | None:
        """The panel's answer, or None where this profile has no defensible consensus."""

    def question_text(self, record: Record) -> str:
        """What an annotator is asked, in their language. No model output may appear in it."""

    def scenario_hash(self, record: Record) -> str:
        """What must not straddle a split — two records of one scenario share it."""

    def training_example(self, record: Record) -> Mapping[str, Any]:
        """The record in the shape a trainer expects."""
```

Twelve members, closed. The two contracts overlap on `name` and `version` and nothing else — neither
axis may drift into the other's job.

---

## The surface: four main endpoints, fifteen services

**A main endpoint is a phase; a sub-endpoint is one service.** `POST /data-quality` runs that phase's
three services in flow order over the posted records. `POST /data-quality/pii-check` runs exactly one.
Both take and return the same body, so they compose.

### The flow

`src/dataforce/pipeline/__init__.py` is the one place this table exists in code.

| # | phase | stage | what it does |
|---|---|---|---|
| 0 | load_data | `load_data` | every source item becomes one record with identity, content and provenance |
| 1 | data_quality | `label_check` | the five checks on the label that need no opinion |
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

**Stages 0–11 are in scope.** `release` is declared here so the flow is complete and the record's
`release` key has an owner, and is specified in a follow-up — see *Out of Scope*.

**`load_data`, not `load`.** AGENTS.md §5 forbids a bare operation that names no object: *load what?* The
stage reads a source item and returns record data, and its name says so.

**`label_check`, not `validity`.** "Validity" names no object and no defect — everything in the pipeline
is a validity check of something. These five check **the label**, against the record's own catalog and
its own turns, and the name says which thing is being checked. It also makes the phase read as one
family: `label_check`, `pii_check`, `duplicate_check`.

### Routes

Kebab-case, matching the style reference.

```
POST /load-data                          -> LoadDataResponse
POST /data-quality                       -> RecordsResponse   # label_check -> pii_check -> duplicate_check
POST /data-quality/label-check           -> RecordsResponse
POST /data-quality/pii-check             -> RecordsResponse
POST /data-quality/duplicate-check       -> RecordsResponse
POST /ai-review                          -> RecordsResponse   # jury -> cohesion -> triage
POST /ai-review/jury                     -> RecordsResponse
POST /ai-review/cohesion                 -> RecordsResponse
POST /ai-review/triage                   -> RecordsResponse
POST /human-review                       -> RecordsResponse   # question_generate -> publish
POST /human-review/question-generate     -> RecordsResponse
POST /human-review/publish               -> RecordsResponse
POST /human-review/annotator-answers     -> RecordsResponse
POST /human-review/aggregate             -> RecordsResponse
POST /human-review/curate                -> RecordsResponse

POST /human-review/publish/sync          -> SyncResponse      # not a record-bus service
GET  /branches                           -> registered modalities and profiles, with versions
GET  /healthz                            -> liveness; no engine, no store
```

`POST /human-review` stops after `publish` on purpose: stages 9–11 cannot run until people have
answered, so a phase endpoint that ran all five would either block or silently produce empty verdicts.

---

## Requirements

Each is a statement a test can be pointed at.

### Code shape

1. **Every field of every data class carries a one-line description of what the key is and what it is
   used for**, in the code: `Field(..., description="…")` on a pydantic model, a trailing comment on a
   plain dataclass attribute. Related fields are grouped under `# --- Section ---` comments. This is not
   decoration — for a request or response model it is the OpenAPI text a caller reads, and for the
   record it is the only place a key's meaning is written down next to the key.
2. Every module opens with a docstring whose first word declares its kind: `DEFINITION ·` one noun and
   its shape, `LOGIC ·` conversions over that noun, `STEP ·` serves exactly one stage of the flow,
   `TOOL ·` not in the flow at all.
3. A service module's docstring names its stage and number: `STEP · pii_check (stage 2) · …`.
4. A name states what it returns, not the operation that produced it, and no function shares a name
   with a stage.

### The record

5. Every service reads records and returns records. A service adds **exactly one key** and changes
   nothing else — except `pii_check`, which also rewrites `content` and bumps `content_version`
   (Requirement 17).
6. `record_id` is 16 lowercase hex over the canonicalised `content` parts. It does not depend on the
   record's position in the source file, and a shuffled re-ingest produces the same set of ids.
7. Order *within* a record is content; order *between* records is not.
8. A media part contributes its `sha256`, never its bytes, to `record_id`. Moving a file does not change
   an id; changing its content does.
9. `meta` is kept **verbatim**. Every key-set the source presents survives load unchanged, including
   keys no code recognises — what looks like noise now is what a later question turns out to need.
10. No record stores an answer space. `Record` has no such field, and constructing one with it raises.
11. Every key a service writes is written by exactly one service. The per-phase `<phase>_config` key is
    the single exception and is written by the **edge**, never by a service (Decision 5).
12. A record carries `provenance` written by `load_data`: source digest, offset, ingest time, both axis
    versions, and the run id (Decision 4).

### load_data

13. The input is one shape: standard OpenAI chat-completion records with `tools` carried as data. A
    record with no `tools` key is an **empty catalog**, which is a quarantine for triage — not an
    invitation to parse a catalog out of the prose.
14. Which key holds the answer is **declared**, not assumed: the manifest's `label.at` names it, so a
    source calling it `target` or `gold` needs a manifest line and no code. An undeclared key raises,
    naming the manifest and what *is* declared.
15. One tool call spelled three ways — arguments as a JSON string, the same string with keys reordered
    and whitespace added, and the object form — is one part and one `record_id`.
16. Text content is loaded byte-identical to the source; no normalisation at load. For a media modality,
    `load_data` resolves each item's URI through a resolver supplied at the edge, records `uri` +
    `sha256` + modality metadata, and never opens a file from engine code. A media part without a
    reference cannot be constructed.

### data_quality

17. `pii_check` replaces detected values with **stable typed placeholders** scoped per record
    (`<CUSTOMER_ID_1>`), never deletes them, and a value used twice keeps one placeholder.
18. Detection runs two layers: patterns tuned for recall (and permitted to be noisy), then a model pass
    over a bounded window that sets precision. Patterns run against the raw text **and** against a
    tone-stripped normalisation, so `khong chin` is caught while patterns stay written in correct
    Vietnamese.
19. Spans are recorded against the content they were found in — `content_version` *before* the rewrite —
    and each names `part`, `start`, `end`, `class`, `verified`, `placeholder`.
20. The placeholder→original map is returned to the edge, written outside version control, and read by
    no service.
21. With `enable_redact: false` (the default), `pii_check` reports and leaves `content` untouched; the
    downstream personal-data scan then fails, so nothing ships. Turning it on is an edit to
    `params.yaml`, which makes the decision attributable.
22. `label_check` runs the five declared checks, and each check's count is compared against
    `params.invalid_counts[<check>]`; a count that moves fails the run. Those numbers are populated by
    the first run over a declared source. Until one is declared the key is empty, and the gate reports
    its counts rather than comparing them.
23. `duplicate_check` reports two groups per record: `duplicate_content_same_label` and
    `duplicate_content_diff_label`. Near-duplicates use the modality's `embedding`, which is static, so
    two runs give identical groups.

### ai_review

24. `jury` records one vote per model: the model name, whether the existing label is right, the model's
    own answer, and its reasoning. A vote that does not validate against the record's materialised
    answer schema is an **invalid vote**, counted and never silently dropped.
25. `cohesion` computes two numbers and makes no model call: agreement of the jury with itself, and
    agreement of the jury with the existing label. Re-running it costs nothing.
26. `triage` turns those numbers into a bucket, a stratum and a quota using thresholds from
    `params.thresholds.triage`. Re-tuning thresholds re-runs `triage` alone (Decision 3).
27. Thresholds live in configuration. `gates.py` and the triage logic contain no numeric literal other
    than `0` and a display cap.
28. No jury call is made to an offshore endpoint before the cross-border data-transfer review is
    recorded in the run manifest. The gate reads a declared field; it does not perform the review.

### human_review

29. `question_generate` produces one question at a time about one record, carrying the evidence and the
    glossary, with an enumerated answer set. Answering *incorrect* requires the corrected value.
30. **No model output may reach an annotator.** The generated annotation config and question payload
    contain no vote, no cohesion number, no bucket.
31. The annotation config is composed from the modality's display half and the profile's capture half,
    and **neither may emit the other's**.
32. `publish` writes questions to the question store through a port supplied at the edge and records the
    receipt on the record. It does not talk to Label Studio.
33. `annotator_answers` reads responses out of the store. It does not talk to Label Studio either.
34. `aggregate` produces one verdict per record with a method name, a confidence, and the overlap it was
    computed from; incomplete overlap uses Krippendorff's α.
35. `curate` writes the final label with `status`, the validators who produced it, and — where they
    disagreed — who adjudicated.

### Running it

36. No engine module opens a file, names a path, or imports the edge. `api/` and `cli.py` are the edge;
    **everything else is the engine**, and the arrow points one way.
37. Importing `dataforce.modalities.text2text` and `dataforce.profiles.tool_decision` from a directory
    holding no `config/` succeeds and writes nothing.
38. No module under `pipeline/` imports a concrete modality or profile. Both axes arrive through a
    registry.
39. A registry is instance state. Two registries in one process hold different implementations, and
    registering a second implementation of one name is refused.
40. Identity is never assigned in a class body. `name`, `version` and `modality` come from
    `config/<axis>/<name>.yaml`, whose **filename is its identity**, and `version` must be a string.
41. Every stage runs the `conservation` gate: `output + quarantined + deduped_out == input`, exactly, no
    tolerance. A failing gate writes `GATE_FAILED.json` with assertion, observed, expected and a capped
    list of offending ids, and exits non-zero.
42. No stage consumes an input whose upstream gate did not pass.
43. A run records every policy file it read with its digest, both axis versions, and every artifact
    digest. Two runs of one unchanged configuration produce byte-identical run manifests; a changed
    policy file changes the manifest.
44. HTTP and an in-process caller reach the same function, and produce the same record.

---

## Design

### Package layout

`core/` is gone. It held five things and only `errors.py` earned the package: `flow.py` existed to be
compared against a document by a test that no longer exists, `artifacts/` was the previous design's
per-phase file shapes, and `record.py`, `manifest.py` and `gates.py` are used by every layer — which
makes them the package's own top level, not a sub-package. A package with one useful module is that
module (AGENTS.md §6).

```
src/dataforce/
  errors.py          DEFINITION · ConfigError, GateFailed — the two every layer may raise
  record.py          DEFINITION · Record and its parts — the bus
  manifest.py        DEFINITION · Manifest — one axis's declaration, already parsed
  gates.py           LOGIC      · GateResult, conservation, assert_gates. No thresholds.

  pipeline/
    __init__.py      DEFINITION · PHASES and STAGES — the flow table, in code, once
    load_data.py     STEP · load_data (stage 0)
    data_quality/    STEP modules: label_check.py, pii_check.py, duplicate_check.py
    ai_review/       STEP modules: jury.py, cohesion.py, triage.py
    human_review/    STEP modules: question_generate.py … curate.py

  modalities/
    base.py          DEFINITION · the Modality protocol
    text2text/       __init__.py, schema.py, utils.py
    speech2text/     declared seam; not built

  profiles/
    base.py          DEFINITION · the Profile protocol
    tool_decision/   __init__.py, schema.py, utils.py

  api/                                    # the edge: everything that touches a file, a socket, a clock
    main.py          TOOL · create_app(), CORS, one include_router per main endpoint
    routers/         load_data.py, data_quality.py, ai_review.py, human_review.py
    schemas.py       DEFINITION · request and response bodies, every field described
    engine.py        LOGIC · Engine, Registry, open_engine — the composition root
    policy.py        LOGIC · config/<axis>/*.yaml, config/gates.yaml, params.yaml, prompts -> declarations
    artifacts.py     TOOL · the one place a record file, a metrics file or a run manifest is read/written
    store/           models.py, repository.py, session.py — the question store
  cli.py             TOOL · one subcommand per stage, JSONL in, JSONL out
```

A phase with one stage is one module (`load_data.py`); a phase with several is a directory. Nothing is
split until a second consumer needs half of it.

Every implementation of either axis is `__init__.py`, `schema.py` (`DEFINITION ·`) and `utils.py`
(`LOGIC ·`). A shape is a shape and a conversion over it is logic — they change for different reasons,
so `schema.py` does not import `utils.py`.

**Import direction, stated once in the package docstring:** `api/` and `cli.py` may import the engine;
the engine may not import them.

### The record

The bus. **Every key carries its meaning next to it** — Requirement 1, applied to the record itself.
This corrects `objective.md` §3's illustrative JSON, which uses Python `True`, leaves several values as
prose, and nests `human_review` inside `ai_review`.

```jsonc
{
  // --- Identity ---
  "record_id":  "3f9a1c0b7e4d2856",   // 16 hex over canonicalised content; the join key everywhere
  "source_id":  "s4471",              // the id the source gave this item; for tracing back, never for joining
  "branch":     { "modality": "text2text",      // which pair read this record's content
                  "profile":  "tool_decision" },// which task defines its answer

  // --- Provenance: what made this record, travelling with it ---
  "provenance": { "source_file_sha256": "a1b2c3d4…",          // which file, by content, not by name
                  "offset": 4471,                             // position in that file, for re-reading one item
                  "ingested_at": "2026-08-22T00:00:00Z",      // when load_data ran
                  "modality": "text2text@1",                  // stamped pair version; a bump is visible per record
                  "profile":  "tool_decision@1",
                  "run_id":   "r_2026-08-22T00:00:00Z_9f3c" },// joins this record to its run manifest

  // --- Content: the conversation, in order ---
  "content": [                        // ordered parts; order is content, so it is covered by record_id
    { "type": "text",                 // "text" carries `text`; media types carry `uri` + `sha256`
      "role": "user",                 // who spoke; every turn is context and none of it is an answer
      "text": "Mã của mình là <CUSTOMER_ID_1>." }
  ],
  "content_version": 2,               // bumped only by pii_check; says which text the spans point into

  // --- The answer, and everything else the source carried ---
  "label": [ { "name": "SendStatement",                        // the training target. Nothing else is.
               "arguments": { "ma_khach": "<CUSTOMER_ID_1>",   // checked against the tool's JSON Schema
                              "ky": "thang_nay" } } ],
  "meta":  { "human_checked": true }, // the source's own keys, verbatim; read only where declared

  // --- data_quality (stages 1-3) ---
  "data_quality": {
    "data_quality_config": { },       // the resolved config and its digest; written by the edge, read by services
    "label_check":     { "passed": true,          // did every check on the label hold
                         "failed_checks": [],     // which named checks did not, for triage
                         "quarantined": false },  // is this record held back from downstream stages
    "pii_check":       { "decision": "redacted",          // redacted | reported | withheld
                         "content_version_scanned": 1,    // which content the spans below index into
                         "spans": [ { "part": 3,          // index into `content`
                                      "start": 16,        // character offset, inclusive
                                      "end": 22,          // character offset, exclusive
                                      "class": "CUSTOMER_ID",       // the typed class, which picks the placeholder
                                      "verified": true,             // did layer two confirm layer one's hit
                                      "placeholder": "<CUSTOMER_ID_1>" } ],
                         "classes": ["CUSTOMER_ID"],      // distinct classes found, for the corpus-level report
                         "unverified": 0 },               // hits layer two could not confirm; the gate reads this
    "duplicate_check": { "duplicate_content_same_label": [],  // same content, same label: safe to drop one
                         "duplicate_content_diff_label": [] } // same content, different label: one of them is wrong
  },

  // --- ai_review (stages 4-6) ---
  "ai_review": {
    "ai_review_config": { },          // resolved panel config and its digest; written by the edge
    "jury":     { "panel_version": 2,               // which panel composition produced these votes
                  "prompt_version": "jury_vote.v1", // which prompt; a change invalidates comparison
                  "llm_votes": [ { "model_name": "…",       // which juror
                                   "label_is_right": true,  // its verdict on the existing label
                                   "answer": [],            // its own answer, in the profile's answer shape
                                   "reasoning": "…",        // why, for the human who reads a disagreement
                                   "valid": true } ],       // did it validate against the answer schema
                  "invalid_votes": 0,       // count of `valid: false`; the gate compares it to a ceiling
                  "plurality": [],          // the panel's most-common answer
                  "final_prediction": [] }, // what the panel is taken to have said; may differ from plurality
    "cohesion": { "self_agreement": 0.83,   // how much the jurors agree with each other
                  "label_agreement": 0.42,  // how much they agree with the existing label
                  "method": "…" },          // which distance produced both, so the pair is comparable
    "triage":   { "bucket": "…",            // which cell of the two numbers this record falls in
                  "stratum": "…",           // the sampling group the bucket belongs to
                  "selected_for_review": true, // does a human see it
                  "reason": "…" }           // which rule selected it, so a quota can be audited
  },

  // --- human_review (stages 7-11) ---
  "human_review": {
    "human_config":      { },         // annotators and the question generator; written by the edge
    "question_generate": [ { "question_id": "…",    // stable id; the join key to the store and to answers
                             "question_name": "…",  // the short label an annotator sees
                             "content": "…",        // the question itself, in the annotator's language
                             "enum": [] } ],        // the permitted answers; free text is not one of them
    "publish":           { "stored": [],            // question_ids written to the store
                           "store_run_id": "…",     // which publish run wrote them, for idempotency
                           "published_at": "…" },
    "annotator_answers": { "responses": [ { "annotator_id": "u_14",    // who answered
                                            "question_id": "…",       // which question
                                            "verdict": "…",           // one of the question's enum values
                                            "corrected_value": null,  // required when the verdict is "incorrect"
                                            "note": null,             // free text, never parsed
                                            "submitted_at": "…" } ] },
    "aggregate":         { "verdict": "…",          // the one verdict the overlap agreed on
                           "method": "majority_gold_weighted", // how it was reached, since that is arguable
                           "confidence": 0.94,      // how much to trust it downstream
                           "overlap": 2,            // how many annotators saw this record
                           "alpha": 0.81 },         // Krippendorff's α for the incomplete-overlap design
    "curate":            { "status": "original",    // original | corrected | unresolved
                           "label": [],             // the final label; this is what ships
                           "validators": [],        // who produced it
                           "adjudicated_by": null,  // who broke a tie, where there was one
                           "decided_at": "…" }
  },

  // --- release (stages 12-14; declared, not yet specified) ---
  "release": { }
}
```

### Per-service contracts

**Reads** is the set of keys a service may look at; anything else is none of its business. **Writes** is
the one key it owns. **Gate** fails the run rather than passing bad data on. `conservation` runs on
every stage and is not repeated below.

#### `load_data` — stage 0

| # | stage | reads | writes | gate |
|---|---|---|---|---|
| 0 | `load_data` | the raw item, under the declared label key | the whole record: identity, `branch`, `provenance`, `content`, `content_version = 1`, `label`, `meta` | source digest matches `params.source.sha256`; record count matches; no two distinct contents share a `record_id` |

The catalog is **not** copied onto the record as an answer space; `answer_schema` materialises it from
the record when asked and never persists it. A stored space is a second thing that can disagree with the
first, and it is the copy that goes stale.

#### `data_quality` — stages 1–3

| # | stage | reads | writes | gate |
|---|---|---|---|---|
| 1 | `label_check` | `content`, `label`, `meta` | `data_quality.label_check` | each check's count equals `params.invalid_counts[<check>]`, once declared |
| 2 | `pii_check` | `content` | `data_quality.pii_check`, **and rewrites `content`, bumping `content_version`** | every high-recall hit verified or `decision == "withheld"`; zero literal personal data in `content` afterwards |
| 3 | `duplicate_check` | `content`, `label` | `data_quality.duplicate_check` | group membership is symmetric and transitively closed |

The five label checks are the profile's, not the engine's — `label_checks()` is a profile member:
`label_assistant_mismatch` (the label contradicts the turn that restates it), `label_not_in_catalog`
(it names a tool this record does not offer), `empty_catalog` (there was nothing to choose from),
`label_cardinality_anomaly` (it names more tools than the profile permits), `label_names_one_tool_twice`
(a target of `["X", "X"]` trains a model to call X twice). Each carries a declared expected count in
`params.invalid_counts`, and a check reading 0 is what tells you when it stops reading 0.

**PII, in two layers.** Layer one is patterns over the raw text and over
`normalize_text(text, remove_tone_marks=True)`, covering the Vietnamese spoken forms an off-the-shelf
scrubber misses: digits as words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), `@` as `a còng`, `.` as
`chấm`. It is tuned for recall and is *allowed* to be noisy — a digit run is also a price, a date, an
order reference. Layer two is a model pass over a bounded window that marks each hit verified or not.
The placeholder→original map is returned to the edge and written to a path the edge chooses, which
`.gitignore` covers.

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
| 7 | `question_generate` | `content`, `label`, `ai_review.triage` (selection only) | `human_review.question_generate` | the payload holds no vote, no cohesion number, no bucket; the glossary exists |
| 8 | `publish` | `human_review.question_generate`, modality display half, profile capture half | `human_review.publish` | every question stored exactly once; the generated config validates |
| 9 | `annotator_answers` | the store | `human_review.annotator_answers` | every response names a question that was published |
| 10 | `aggregate` | `human_review.annotator_answers` | `human_review.aggregate` | overlap ≥ the rung's floor; α ≥ the declared floor |
| 11 | `curate` | `human_review.aggregate`, `label` | `human_review.curate` | an `incorrect` verdict carries a corrected value |

Stage 7 reads `triage` **only to decide which records get a question**. Nothing it reads from `ai_review`
reaches the payload, which is what Requirement 30 asserts.

### Engine and edge

The engine computes; the edge supplies everything that came from a file, a socket or a clock.

```python
engine = open_engine(profile="tool_decision", modality="text2text",
                     config_root=Path("config"), params=Path("params.yaml"))
```

`open_engine` reads the two manifests, the thresholds and the prompt templates through `api/policy.py`,
registers both axes, and returns an `Engine` holding the resolved pair, the registry, and the tuple of
policy files it read. Naming no modality takes the profile at its word; naming a different one raises
`ConfigError` saying which modality the profile composes with.

An engine can also be built with **no filesystem anywhere** — both axes handed `Manifest` objects and a
template string — which is what makes a web handler and an in-process caller the same caller.

Every service has one signature:

```python
def pii_check(engine: Engine, records: Iterable[Record]) -> ServiceResult: ...
```

`ServiceResult` carries `records`, `gates: list[GateResult]`, and any **side output** the edge must
persist — for `pii_check` the placeholder map, for `publish` the rows to store. The engine returns side
output; it never writes it.

### Request and response models

`api/schemas.py`, in the style reference's shape. Every field described, because that description is
what a caller reads in `/docs`.

```python
class RecordsRequest(BaseModel):
    """Body for every service route except /load-data. Records in, records out."""

    # --- Which pair to run under ---
    branch: Branch = Field(
        ...,
        description=(
            "Which modality and profile to resolve. Must match the records' own `branch`; "
            "a mismatch is a 400 rather than a silently different run."
        ),
    )

    # --- Optional per-call configuration ---
    config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Overrides for this phase's resolved config. Recorded verbatim into the "
            "record's <phase>_config key, so a run is reproducible from the record alone."
        ),
    )

    # --- The bus ---
    records: list[Record] = Field(
        ...,
        description="The records to run this service over, unchanged except for the key it owns.",
    )
```

`POST /load-data` is the one route that takes no records, and the one place the modality axis changes
the shape of the request:

```jsonc
{
  "branch": { "modality": "text2text", "profile": "tool_decision" },
  "items":  [ ],                                       // source items inline — the normal case for text2text
  "source": { "uri": "data/raw/<declared source>.json",// or a reference, for a file too large to post
              "sha256": "a1b2c3d4…" }                  // checked before a record is read
}
```

`items` and `source` are mutually exclusive and one is required. **For `text2text`, `items` inline is
the normal case** — the content is already in the body and nothing needs reading. For `speech2text`,
`image2text` and `video2text`, each item references its media by URI; `load_data` resolves it through a
`MediaResolver` supplied at the edge, records `uri` + `sha256` + duration or dimensions, and the engine
never opens it.

**Response:**

```jsonc
{
  "records": [ ],                                    // the bus, one key richer
  "gates":   [ { "gate": "conservation", "ok": true, // which gate, and whether it held
                 "assertion": "…",                   // the rule in words, so a failure explains itself
                 "observed": { }, "expected": { } } ],
  "run":     { "run_id": "…",                        // joins to every record's provenance
               "producer": { },                      // both axis versions
               "policy":   { } }                     // every policy file read, by digest
}
```

**A failing gate is `422`**, body `{"error": "gate_failed", "gate": …, "assertion": …, "observed": …,
"expected": …, "offending_record_ids": [...]}`, and the response carries **no records** — the point of a
gate is that bad data does not pass on. `ConfigError` is `400`; an unknown profile or modality is `400`
naming the ones that exist; anything else is `500`.

### The question store

`publish` writes to a database we own; a separate sync moves questions into Label Studio and answers
back out. Three tables, owned by `api/store/`, every column carrying its purpose in the model.

| table | columns |
|---|---|
| `question` | `question_id` pk · `record_id` · `run_id` · `modality` · `profile` · `payload` json · `config_digest` · `created_at` |
| `publication` | `question_id` fk · `external_system` · `external_project_id` · `external_task_id` · `status` · `pushed_at` · unique (`question_id`, `external_system`) |
| `annotator_answer` | `answer_id` pk · `question_id` fk · `annotator_id` · `verdict` · `corrected_value` json · `note` · `submitted_at` · `external_annotation_id` unique |

- The engine knows none of this. `publish` returns rows; `api/store/repository.py` writes them behind a
  `QuestionStore` port, and the DSN is read at the edge from `DATAFORCE_DATABASE_URL`.
- **SQLite by default, Postgres by URL.** SQLAlchemy 2.0 declarative models, Alembic migrations.
- `POST /human-review/publish/sync` pushes unpublished questions into Label Studio through
  `label-studio-sdk`, writes the returned task ids into `publication`, then pulls new annotations into
  `annotator_answer`. It is idempotent in both directions: the two unique constraints are what make it
  so.
- Running the sync is optional. Every other endpoint works with no Label Studio anywhere.

### Configuration

`config/<axis>/<name>.yaml` for identity and declarations, `config/gates.yaml` for what each gate
compares against, `config/prompts/…` for templates, `params.yaml` for every threshold.
`config/modalities/text.yaml` becomes `config/modalities/text2text.yaml` — the filename is the identity,
so the rename *is* the change. `params.invalid_counts` is re-keyed to the five label-check names and
left empty until a corpus is declared.

---

## Decisions

**1 · HTTP is the surface; the engine is the same one function.**
Four routers, one route per service, over the record-in/record-out functions an in-process caller uses.
*Alternative:* functions and a CLI only, with HTTP later — which `objective.md` §9 leans toward when it
calls the web view "a later task". *Why this:* §9 defers the *view*, not the API, and §8 already requires
two shells over one implementation. *Reversible:* yes — deleting `api/routers/` and `main.py` leaves the
engine intact.

**2 · A modality is the input→output pair, named as one string.**
*Alternative:* the atomic input medium, with the output half coming from the profile. *Why this:*
`objective.md` §3 writes `branch.modality = "text2text"` on the record, and the display half of the
annotation config genuinely depends on both halves. *Cost:* `speech2text` and `text2text` will share
text-rendering code, which goes in a shared helper rather than a base class. *Reversible:* costly — the
name is stamped into every record's `branch` and `provenance`.

**3 · `ai_review` is three stages, not one.**
`jury` → `cohesion` → `triage`. *Alternative:* one stage writing votes, agreement and bucket together,
which is what `objective.md` §3's record shows. *Why this:* they fail and re-run for different reasons —
the jury costs money per record and must be cached; cohesion is arithmetic over what the jury wrote; and
triage reads thresholds `objective.md` §8 calls *provisional until the pilot measures them*. Folded
together, re-tuning a bucket boundary re-runs the panel. *Reversible:* yes, and it is the arithmetic that
puts `human_review` on stages 7–11.

**4 · The record carries a `provenance` key.**
`objective.md` §1 requires "per-record provenance for every record and every label"; §3's record example
carries only `source_id`. Those cannot both hold, so this spec adds one key written by `load_data`.
*Alternative:* keep provenance only in the run manifest. *Why this:* export produces exactly the case
where a record is separated from its run. *Reversible:* yes, one key, one writer. `Assumption:` `run_id`
is generated at the edge, because the engine has no clock.

**5 · The `<phase>_config` key is written by the edge.**
If the first service of a phase wrote it, calling a sub-endpoint alone would produce a different record
than calling the phase endpoint. Resolving config is already an edge job — no service may name a config
location — so the edge stamps the resolved config and its digest on entry, and services read it.
*Reversible:* yes.

**6 · `publish` writes to our own store; Label Studio is a separate sync.**
*Alternative:* call the Label Studio API from `publish`. *Why this:* the pipeline stays runnable and
testable with no instance, and `annotator_answers` reads one shape whatever the annotation tool is.
*Cost:* task state in two places, so the sync must be idempotent in both directions — which the two
unique constraints enforce. *Reversible:* yes; the store is behind a port.

**7 · SQLite by default, Postgres by URL, SQLAlchemy + Alembic.**
*Why this:* a developer running the pilot should not need a database server, and the schema is small
enough that the two behave identically. *Reversible:* yes — one DSN.

**8 · One input shape.**
Standard OpenAI chat-completion records with `tools` as data — what `objective.md` §2 documents, and
nothing else. *Alternative:* also read a catalog rendered as prose into the system prompt, which is what
the deleted `legacy_system_prompt` reader did for `fc_train_final.json`. *Why this:* that corpus is out
of use, so the second reader has no caller, and AGENTS.md §2 forbids flexibility nobody asked for.
*Reversible:* yes — the reader is recoverable at `ed84417^`, and re-admitting it means a declared `shape`
key and a second `catalog_from_*` function, not a change to any service.

**9 · `core/` is dissolved; `load` becomes `load_data`; `validity` becomes `label_check`.**
Three renames with one reason: a name must say what it holds or what it returns. `core` said only "not
elsewhere", and of its five modules `flow.py` existed for a deleted test and `artifacts/` for the
previous design. `load` names an operation and no object. `validity` names a property so broad that
every gate in the pipeline is one. *Cost:* `config/modalities/text.yaml` is renamed too, and
`params.invalid_counts` is re-keyed. *Reversible:* yes, but the record's `data_quality.label_check` key
would move with it, so it is cheapest to settle now.

**10 · The test suite is written fresh against this document.**
`tests/` is deleted rather than migrated. *Alternative:* keep the guard tests, which encoded
`objective.md` §10 correctly. *Why this:* they also encoded a flat record, a `core/` package, a `load`
stage and a stage-table-parsing contract against the spec file — keeping them would have let deleted
design decide live naming, which is the failure mode `da50d46` was avoiding. *Cost:* the AST guards
(no filesystem in the engine, no concrete axis in `pipeline/`, no re-implementation of the toolkit,
no identity in a class body) must be re-written before the first service, not after; each is ~40 lines
and each is recoverable at `ed84417^` as a starting point.

---

## Versions

| Thing | Version | Why / source |
|---|---|---|
| Python | 3.12 (`>=3.12,<3.13`) | unchanged; `.python-version` |
| FastAPI | `>=0.141.1` | current release, PyPI |
| Uvicorn | `>=0.52.4` | current release, PyPI |
| SQLAlchemy | `>=2.0.52,<2.1` | current 2.0.x, PyPI; 2.0 declarative style |
| Alembic | `>=1.19.1` | current release, PyPI |
| label-studio-sdk | `>=2.1.1` | current release, PyPI; used only by the sync |
| Label Studio (server) | 1.23.0 | current release; pinned in `deploy/` compose, not a Python dependency |
| pydantic | `>=2.13` | unchanged; `Field(description=…)` is Requirement 1's mechanism |
| agent-toolkit | `@v0.1.0` git tag | unchanged; the tag has moved once, so `uv.lock` is the record |
| model2vec | `>=0.9` | unchanged; static embeddings keep dedup reproducible |
| pandera / pandas | `>=0.32.1` / `>=2.2` | unchanged |

`fastapi`, `uvicorn`, `sqlalchemy` and `alembic` are runtime dependencies. `label-studio-sdk` goes in an
optional `[label-studio]` extra, so the pipeline installs without it.

---

## Invariants

Each names the check that holds it, not a file that used to.

| # | Invariant | How it is checked |
|---|---|---|
| I1 | The engine opens no file and names no path | AST scan over every engine module, plus a subprocess import from an empty directory |
| I2 | `pipeline/` imports no concrete axis | AST scan for any import matching a registered implementation |
| I3 | Code's phase and stage names are the flow's | `pipeline/__init__.py` is the single source; module filenames and docstrings are compared to it |
| I4 | Each axis implementation is `__init__`, `schema`, `utils`, and `schema` imports no `utils` | AST scan over both axis packages |
| I5 | Identity comes from the manifest filename, never a class body | AST scan for `name`/`version`/`modality` assigned in a `ClassDef` |
| I6 | Nothing re-implements an `agent-toolkit` function or imports a dependency it owns | AST scan for the known names and the four owned roots |
| I7 | Every field of every data class has a description | model introspection: every `FieldInfo.description` is non-empty |
| I8 | One writer per record key | run every service over one record; assert each diff is exactly one key |
| I9 | `record_id` is stable across a shuffled re-ingest and sensitive to content | property test over a synthetic corpus |
| I10 | No answer space is ever stored | `Record` has no such field; constructing one raises |
| I11 | Conservation holds at every stage | the universal gate, asserted per stage |
| I12 | No model output reaches an annotator | assert on the `publish` payload and the generated config |
| I13 | The placeholder map is never read by a service and never committed | AST scan plus a `.gitignore` assertion |
| I14 | Two runs of one unchanged configuration produce identical run manifests | run twice, compare bytes |
| I15 | HTTP and in-process produce the same record | same input both ways, asserted equal |

---

## Error Behavior

| Situation | Behaviour |
|---|---|
| Source digest ≠ `params.source.sha256` | `load_data` hard-stops before reading a record |
| Undeclared label key | `ConfigError` naming the manifest, the key, and what *is* declared |
| Unknown profile or modality | `ConfigError` listing the registered ones; an empty registry says "none" |
| Profile and modality disagree | `ConfigError`: "composes with modality 'text2text'" |
| A gate fails | `GateFailed` with every result attached, passing ones included; `GATE_FAILED.json` written by the edge; exit non-zero; HTTP `422` with no records |
| Upstream `GATE_FAILED.json` present | the next stage refuses to start |
| A jury vote does not validate | counted as an invalid vote, kept with `valid: false`, never silently dropped; the invalid-vote-rate gate decides whether the run continues |
| A model call fails after retries | `agent-toolkit` owns retry and rate limiting; an exhausted call is one missing vote, and the panel-floor gate decides |
| `enable_redact: false` and personal data found | `pii_check` reports, `content` untouched, `decision: "reported"`; the downstream scan gate fails so nothing ships |
| Label Studio unreachable during sync | the sync fails; no record key changes, no `publication` row is written, every other endpoint is unaffected |
| A question is synced twice | the unique constraint makes the second a no-op |

---

## Testing Strategy

There is no test suite. It is written against this document, in this order, and `make check` (ruff,
`mypy --strict`, pytest) must pass before each step lands.

1. **The guards first (I1–I7)**, before any service. Each is an AST or introspection check proved against
   synthetic source, so the guard fails before it is ever needed. Writing them after the services is how
   a codebase acquires the thing the guard forbids.
2. **One test module per stage**, asserting that stage's reads/writes/gate row: it writes its key, writes
   nothing else, and its gate fails on the input it exists to catch.
3. **The bus property (I8)**, once: build a record, run all twelve in-scope services, and assert each
   step's diff is exactly one key.
4. **Both shells (I15)**: the same input through `pii_check(engine, records)` and
   `POST /data-quality/pii-check`, asserted equal.
5. **Fixtures are invented, never extracted from real data** (AGENTS.md §9), in `objective.md` §2's
   shape. There is no corpus-wide test until a source is declared; when one is, it asserts the label-check
   counts against `params.invalid_counts` under `-m integration` and nowhere else.
6. **PII gets adversarial fixtures**: spoken digits with and without tone marks, `a còng`, `chấm`, a value
   used twice in one record (one placeholder), and a digit run that is a price rather than an identifier
   — layer one flags it, layer two clears it.
7. **The store**: SQLite in `tmp_path`, idempotency asserted by running the sync twice against a fake
   Label Studio client.
8. **No network in `make check`.** Every jury test uses a stubbed panel; the live panel is the Smoke rung,
   under `-m integration`.

---

## Out of Scope

- **`release` — stages 12–14** (`split`, `export`, `datasheet`). Declared in the flow so it is complete
  and `record.release` has an owner; specified in a follow-up. Nothing in stages 0–11 may assume its
  shape.
- **The web view.** One Vite + TypeScript SPA over these same endpoints, on the style reference's
  pattern — `objective.md` §9 calls it a later task, and this spec keeps it one.
- **Real `speech2text`, `image2text`, `video2text`.** The seam is specified — media parts, the
  `MediaResolver` port, the pair naming — and unenforced. Only `text2text` is built.
- **Our own annotation platform.** Deferred, not cancelled; the pilot decides.
- **Model training and evaluation, synthetic data generation, active learning, fine-tuning a juror,
  Confident Learning**, and automatic write-back to any source file. Export produces an artifact; putting
  it anywhere is a human step.
- **The two blocking prerequisites that are not code**: the cross-border data-transfer review before the
  first offshore jury call, and the written glossary before the first generated question. This spec gates
  on their being *recorded*; it does not perform them.
