# SFT Dataset Pipeline — Raw Corpus to Released Training Set

## What

A reproducible, gated pipeline that turns the raw Tool-Decision corpus (`fc_train_final.json`) into a versioned, documented, SFT-ready dataset. It is twelve DVC stages, each producing a checksummed artifact and each guarded by a machine-checked **gate** that fails the run rather than passing bad data downstream. Existing open-source carries the annotation UI, deduplication, label-error detection, annotator aggregation, agreement statistics, and data versioning; this spec builds only the four things that do not exist for this corpus — a marker-preserving adapter, the validation-question generator, a Vietnamese spoken-form PII scrubber, and the gate runner.

Scope is **text SFT only**. Image annotation is out. The pipeline is proven end to end on 50 records, then on a 500-record pilot behind a numeric gate, and only then scaled — and at scale it deliberately human-validates a designed subset rather than all 21,172 records, because validating all of them costs ~44 person-days and buys less than the subset does.

## Context

### Why a pipeline rather than more annotation

The handbook this spec implements makes three claims that decide the architecture: aggressive filtering beats collecting more (10× token efficiency, FineWeb-Edu); weak supervision is the largest speed lever (2.8×, Snorkel/VLDB 2017); and even curated benchmarks carry ≥3.3% label errors (Northcutt et al., NeurIPS 2021). It also reports that 92% of ML teams hit a data cascade — an upstream data defect amplifying downstream (Sambasivan et al., CHI 2021). Every stage below exists to make one of those failures visible early and cheap.

### What the corpus actually contains

Measured over the whole file (21,172 records, 126 MiB) rather than sampled:

| Property | Value |
|---|---:|
| Records | 21,172 |
| `meta.label` cardinality 0 / 1 / 2 / 3 | 7,498 (35.4%) / 10,596 (50.0%) / 2,757 (13.0%) / 321 (1.5%) |
| Distinct tool names appearing in labels | 14,411 |
| Most frequent single tool | 35 occurrences |
| (record, tool) decision pairs | 98,766 |
| Catalog size per record | 0–20 tools |
| Distinct tool-catalog fingerprints | 17,596 (16,293 singletons; largest group 112) |
| Distinct `meta` key-sets | 13 |
| Records labelled by `gemma-4-31B-it` | 14,241 (67.3%) |
| Records carrying `orig_label` (already relabelled once) | 1,358, of which 1,346 changed |
| Exact-duplicate user turns | 491 records (2.32%) |
| Exact-duplicate (system, user) pairs | 1 |

Four defects are already detectable without a single human judgment:

| Defect | Count | Why it is fatal for SFT |
|---|---:|---|
| `meta.label` disagrees with the assistant message | **48** (0.227%) | The assistant message *is* the training target. Two sources of truth disagree; one of them trains the model. |
| Label names a tool absent from that record's own catalog | **722** (3.41%) | The target tells the model to call something it was never offered. Unlearnable, and it teaches hallucination. |
| Catalog parser finds no `[ToolName]` block | **841** (3.97%) | Either genuinely toolless prompts or a parser miss — the two must be distinguished before either is trusted. |
| `source_index` is unique per record (13,366 distinct over 13,366 records) | — | It looks like a grouping key and is not one. Splitting on it gives no leakage protection. |

The 48-record contradiction also explains a discrepancy inside our own documents: [`guided-validation`](../guided-validation/spec.md) reports 7,486 zero-label records, counted from the assistant message; counting from `meta.label` gives 7,498. The 12-record net difference is the arithmetic of those 48 disagreements. That is exactly the class of quiet defect this pipeline exists to surface, and it survived a careful read of the corpus.

### Personal data in the corpus

The records are call-centre transcripts, and PII is present in **spoken form**, which no off-the-shelf scrubber detects:

| Signal on the user turn | Records | Share |
|---|---:|---:|
| Run of ≥6 consecutive Vietnamese number words | 3,485 | 16.46% |
| Literal 9–12 digit run | 770 | 3.64% |
| Literal Vietnamese phone number | 435 | 2.05% |
| `@` or the spoken form of it | 238 | 1.12% |
| Literal email address | 97 | 0.46% |

The digit-word signal is a **superset** — it also matches prices, dates, and reference codes — so it bounds the population needing review, it is not a count of PII. The literal signals are not a superset: they are PII. Vietnam's Personal Data Protection Law 91/2025/QH15 has been in force since 1 January 2026, with Decree 356/2025/ND-CP as implementing guidance replacing Decree 13/2023. A scrubbing stage is therefore a requirement, not a nicety, and it must run before any artifact leaves the raw tier.

### What already exists, and what is missing

Use existing repositories first. What follows is the survey behind that instruction, with the one negative result stated plainly.

| Need | Use | Status checked |
|---|---|---|
| Annotation UI, users, task serving, locking, multi-annotator | **Label Studio** (Community, Docker) + `label-studio-sdk` | 1.23.0 (2026-03-13); SDK 2.1.1 (2026-08-10); repo active |
| Semantic + near-duplicate removal | **SemHash** (`model2vec` static embeddings) | 0.4.1 (2026-01-20) |
| Label-error detection (Confident Learning) | **Cleanlab** | 2.9.0 (2026-01-13) |
| Annotator aggregation (Dawid-Skene, MACE, majority) | **crowd-kit** | 1.4.2 (2025-10-13) |
| Krippendorff's alpha | **krippendorff** | 0.8.2 (2025-11-03) |
| Artifact schema validation | **pandera** | 0.32.1 (2026-06-29) |
| Data versioning and the stage DAG | **DVC** | 3.67.1 (2026-03-31) |
| Machine-readable dataset metadata | **mlcroissant** | 1.1.0 (2026-04-16) |
| LLM access, streaming JSON, slot filling, JSON extraction | **[`agent-toolkit`](../agent-toolkit/spec.md)** | specified, built first |

**Argilla was the obvious candidate and is rejected.** It is the closest fit on paper — LLM-data-native, Python-first, records with typed questions and built-in distribution. But its last release is 2.8.0 on 2025-03-10, and every commit to `main` since that date is a README or project-status edit: seventeen months with no functional change. Betting an annotation pipeline on a library that has stopped shipping is a cost that lands later and cannot be undone cheaply. Label Studio is heavier and its XML labeling config is the thing [`dataforce-platform`](../dataforce-platform/spec.md) deliberately rejected for the platform's *own* schema — but it is maintained, and here we only *generate* that XML, never author it by hand.

What no existing repository provides, and this spec therefore builds:

1. **The `fc_tool_decision` adapter** — parsing the `TOOLS:` block into a structured catalog while preserving the marker DSL (`{trigger}`, `{hold_missing}`, …) verbatim, per [`guided-validation`](../guided-validation/spec.md).
2. **The question generator** — focus-by-rule selection, batch generation with a token budget, caching.
3. **The Vietnamese spoken-form PII scrubber** — number words, spoken `@`, spoken punctuation.
4. **The gate runner** — declarative assertions between stages, the mechanism that makes "reliable" mean something checkable.

### Relationship to the existing specs

This spec sits **above** the other three and narrows two of them. Applying it requires these amendments, which are proposed here and not yet made:

- **[`dataforce-platform`](../dataforce-platform/spec.md):** drop image modality from v1 — requirement 7's `bbox`/`polygon`, requirement 27's IoU comparators, requirement 31's COCO/YOLO exporters, and the images in the E2E scenario. Defer the whole FastAPI + React annotation service behind a Label Studio-based v0 until the pilot gate passes. What Label Studio does *not* give us — a review workflow, agreement metrics, the catalog, subscriptions — is precisely what remains of the platform's justification, and the pilot is what establishes whether that is worth a quarter of engineering.
- **[`guided-validation`](../guided-validation/spec.md):** unchanged in substance. The question model, focus rules, glossary, correction shape, and flag taxonomy are all retained; only the rendering surface changes from a bespoke React card to a generated Label Studio config. Its invariant 1 (the generator's answer never reaches the annotator) gets *stronger*: the proposed answer is never sent to Label Studio at all, so it cannot leak through a response schema.
- **[`agent-toolkit`](../agent-toolkit/spec.md):** unchanged. It is the first thing built.

## Requirements

### Acceptance criteria, fixed before any data moves (Step 1)

1. The release's primary metric is **exact-set-match accuracy** of the predicted tool set against the gold set, measured on the human-validated test split only. Secondary metrics: abstention (zero-label) precision and recall, and per-decision-pair binary F1. All three are declared in `params.yaml` before the first stage runs and are not changed afterwards without a new release version.
2. The pipeline produces a **learning curve** on the pilot — the primary metric at 25%, 50%, and 100% of available training data — so the question "more data or better data?" is answered with a measurement rather than an opinion.

### Ingest and source integrity (Steps 2, 3)

3. Ingest streams the source via `agent_toolkit.file_utils.iter_json_array_file`. The 126 MiB file must never be loaded whole.
4. Every record gets a stable `rid = sha256(system ‖ user ‖ assistant)[:16]`, independent of position, so artifacts are diffable across re-ingests and re-ordering is not a change.
5. Ingest records source provenance per record: source file SHA-256, byte offset, `meta` verbatim, and the ingest timestamp. Nothing is dropped; unparsable records are carried with `parse_status = "unparsed"` and their raw text.
6. The **source-integrity gate** detects and quarantines, as separate named defect classes: `label_assistant_mismatch` (48 expected), `label_not_in_catalog` (722 expected), `empty_catalog` (841 expected), and `label_cardinality_anomaly`. Quarantined records leave the main path into `data/quarantine/<defect>.jsonl` with the defect recorded; they are never silently deleted and never silently kept.
7. Expected defect counts are declared in `params.yaml`. A count that moves by more than ±10% fails the gate — the source changed, and that must be a decision rather than a surprise.

### PII (Step 9, legal)

8. A scrub stage detects and replaces, in every message, both literal and Vietnamese spoken-form personal data: phone numbers, email addresses, national ID numbers, bank account numbers, and full personal names in the customer turn. Spoken-form detection covers digit words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), spoken `@` (`a còng`), and spoken punctuation (`chấm`, `gạch dưới`).
9. Replacement is a **stable typed placeholder** (`<PHONE_1>`, `<EMAIL_1>`) scoped per record, so a value referenced twice in one conversation stays co-referent and the tool-calling semantics survive scrubbing. Replacement is never deletion.
10. Every regex hit above a configured recall threshold is verified by an LLM pass over the surrounding window, using `agent-toolkit`, to cut false positives on prices and dates. The regex layer sets recall; the LLM layer sets precision.
11. A scrubbing report records, per class, the number of spans replaced and a sample of 20 *placeholders in context* (never the original values). The mapping from placeholder to original value is written to `data/00_raw/pii_vault.jsonl`, which is `.gitignore`d, not DVC-tracked, and never leaves the raw tier.
12. The scrub gate fails if any release-tier artifact matches a literal PII pattern.

### Deduplication and grouping (Step 3)

13. Exact duplicates are removed on `sha256(system ‖ user)`, keeping the record with the richer `meta`.
14. Near-duplicate and semantic duplicates are found with SemHash over the concatenated conversation. Cluster members are not deleted; they are assigned a shared `dup_cluster_id`, and one representative per cluster is marked `is_representative`. Deletion happens at export, from an explicit filter, so the decision is reversible and recorded.
15. Every record gets a `group_key` for splitting: the catalog fingerprint, unioned with its `dup_cluster_id`. `source_index` is explicitly **not** a group key (requirement measured above).

### Triage — deciding what a human looks at (Steps 3, 5)

16. The corpus is reframed into **98,766 (record, tool) binary decision pairs** — "should this tool fire in this conversation?" — because the 14,411-name label space, whose most frequent member appears 35 times, cannot support any classifier or label-error method at the tool-name level. All model-assisted quality work happens on the binary reframing; human questions stay at record level.
17. Weak supervision runs **≥8 labeling functions** over the marker DSL, each voting `CALL`, `HOLD`, or abstaining: missing required parameter, `{hold_missing}` clause satisfied, `{trigger}` keyword present in the last turn, `{constraint}` violated by the extracted argument, `{turn_trigger}` scope violation, and the three deterministic defect detectors from requirement 6.
18. LF votes are combined with crowd-kit's Dawid-Skene into a probabilistic decision label with a confidence. Disagreement between that label and the corpus label is a triage signal, not an edit.
19. Cleanlab's Confident Learning runs over the decision pairs using cross-validated out-of-sample predicted probabilities from a logistic regression on static embeddings, producing a label-quality score per pair.
20. The annotation queue is filled from four strata with declared quotas: (a) records whose pairs Cleanlab or the LF model flags, (b) the zero-label population, deliberately oversampled because it carries the corpus's real difficulty, (c) a **uniform random audit sample** whose only purpose is an unbiased residual-error estimate, and (d) the entire test split. Every stratum's selection is recorded per record so the sampling design is reconstructible.
21. The random audit sample is sized from the target confidence interval, not chosen by feel: `n = z²·p(1−p)/e²`. At `p = 0.05` and `e = ±0.02`, `n = 457`; the default is 500. If the observed rate exceeds the assumed `p`, the stage recomputes `n` and requests more.

### Question generation and annotation (Steps 4, 5)

22. Question generation follows [`guided-validation`](../guided-validation/spec.md) unchanged: focus chosen by rule, batch pre-generation, token budget as a hard ceiling, idempotence on `(rid, prompt_version, model)`.
23. Publishing creates a Label Studio project from a **generated** labeling config. The correction control is a dynamic `<Choices value="$tool_choices" choice="multiple">` populated from that record's own catalog plus an explicit "no tool" option, so a correction is structurally incapable of naming a tool outside the catalog.
24. All evidence and glossary HTML is built by the pipeline and **escaped**; corpus text is never interpolated into markup unescaped.
25. The generator's proposed answer is never written to Label Studio in any field — not data, not metadata, not a prediction. It stays in `data/06_questions/` and is joined back only after responses are pulled.
26. Overlap is achieved by project membership rather than a per-task setting: the pilot runs one project with both annotators assigned and `maximum_annotations` set to the annotator count, giving 100% overlap; at scale the flagged and audit strata keep overlap 2 and the remainder runs at overlap 1. *This depends on Label Studio Community honouring `maximum_annotations`, which the smoke stage verifies before anything else is built on it.*
27. A gold set of ≥50 expert-labelled records is mixed into every project as ordinary tasks, visually indistinguishable, and used to score each annotator continuously.
28. Pulling responses normalizes them into the canonical answer shape and **rejects, rather than repairs**, any response where `verdict = incorrect` carries no correction. Rejected responses return to the queue with the reason attached; correction-required is enforced in the pipeline because Label Studio's conditional validation cannot be relied on.

### Aggregation, adjudication, curation (Step 6)

29. Krippendorff's alpha is computed on the verdict across all overlapped records, per question focus and overall.
30. Where overlap ≥ 2, verdicts are aggregated with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote.
31. Records where annotators disagree, or where the aggregated confidence is below threshold, are published to a second **adjudication** Label Studio project showing both answers and both notes, resolved by a reviewer who did not produce either. Label Studio Community has no review workflow; this is that workflow.
32. Curation applies accepted corrections to produce the curated label, and records for every record whether its label is `original`, `corrected`, or `unvalidated`, with the validator and the decision date.

### Split, decontamination, export (Step 7)

33. Splitting is **group-based on `group_key`**, never random. A group is wholly in one split.
34. The test split is **100% human-validated**. A record that has not been through annotation cannot enter test, at any budget. This is the rule that keeps every reported number meaningful.
35. Decontamination verifies zero 13-gram overlap between the test split and train, and zero shared `group_key`. Overlap fails the gate.
36. Export emits SFT JSONL in the source `messages` shape, with the curated label in both the assistant message and `meta.label` — which, given the 48 contradictions found at ingest, must be asserted equal on the way out.
37. Every exported record carries provenance: source SHA-256, pipeline version, validation status, validator, dedup cluster, split, and stratum.
38. The release is a DVC-tracked directory with a manifest listing every file's SHA-256, and the whole release is reproducible from one git commit plus `dvc repro`.

### Documentation (Step 8)

39. Each release ships a **datasheet** (Gebru et al.) answering the handbook's six questions, a **data statement** (Bender & Friedman) covering language variety and both creator and annotator demographics, and a **Croissant** metadata file validated by `mlcroissant`.
40. The datasheet states the synthetic share explicitly. 14,241 of 21,172 records (67.3%) are machine-labelled by `gemma-4-31B-it`, and 1,358 have already been relabelled once. Given the model-collapse result (Shumailov et al., *Nature* 2024), a corpus that is two-thirds machine-labelled must be documented as such, and the human-validated test split is the mitigation that makes the release measurable at all.
41. Documentation generation is a pipeline stage with a gate, not a manual step. A missing required datasheet field fails the release.

## Design

### Stage graph

Each stage is one DVC stage: declared inputs, declared outputs, a gate. `dvc repro` runs only what changed.

| # | Stage | Handbook step | Output | Gate |
|---|---|---|---|---|
| 0 | `ingest` | 2 Collection | `01_ingested/records.jsonl` | parsed + unparsed == source count; source SHA-256 matches params |
| 1 | `validate` | — | `02_validated/`, `quarantine/` | defect counts within ±10% of declared |
| 2 | `scrub` | 9 Legal | `03_scrubbed/` | zero literal-PII matches downstream |
| 3 | `dedup` | 3 Filtering | `04_deduped/` + clusters | exact dups 0; cluster report emitted |
| 4 | `embed` | 3 | `04_deduped/embeddings.npy` | row count matches records |
| 5 | `triage` | 3, 5 | `05_triaged/queue.jsonl` | every stratum met its quota; audit `n` ≥ computed |
| 6 | `generate` | 4 | `06_questions/` | schema-valid ≥ 98%; tokens ≤ budget |
| 7 | `publish` | 5 | Label Studio project + `06_questions/published.jsonl` | zero proposed answers in the payload |
| 8 | `pull` | 5 | `07_responses/` | every `incorrect` has a correction |
| 9 | `aggregate` | 6 QA | `07_responses/aggregated.jsonl` | α ≥ 0.667; flag ≤ 10%; gold ≥ 0.85 |
| 10 | `curate` | 6 | `08_curated/` | every correction ⊆ that record's catalog |
| 11 | `split` | 7 | `09_splits/{train,val,test}.jsonl` | zero group leakage; zero 13-gram overlap |
| 12 | `export` | 7 | `10_release/sft.jsonl` | test 100% validated; counts reconcile; label == assistant |
| 13 | `document` | 8 | `10_release/{datasheet.md,croissant.json}` | all required fields present; Croissant validates |

Stages 7–9 loop: publish → annotate → pull → aggregate → adjudicate → pull again.

### Repository layout

```
dataforce/
├── pipeline/
│   ├── dataforce_pipeline/
│   │   ├── cli.py                 dataforce <stage> ... | dataforce gate run <stage>
│   │   ├── contracts.py           pandera schemas + pydantic models, one per artifact
│   │   ├── adapters/
│   │   │   └── fc_tool_decision.py  TOOLS: parser, markers preserved verbatim
│   │   ├── pii/
│   │   │   ├── patterns.py        literal + spoken-form Vietnamese detectors
│   │   │   ├── verify.py          LLM precision pass via agent-toolkit
│   │   │   └── vault.py           placeholder ↔ original, raw tier only
│   │   ├── lf/                    labeling functions over the marker DSL
│   │   ├── triage/                cleanlab, dawid-skene, strata + sample sizing
│   │   ├── labelstudio/
│   │   │   ├── config.py          generates the labeling XML
│   │   │   ├── publish.py         project creation, task push
│   │   │   └── pull.py            response normalization
│   │   ├── quality/               krippendorff, gold scoring, adjudication sets
│   │   ├── release/               split, decontaminate, export, datasheet, croissant
│   │   └── gates/
│   │       ├── runner.py
│   │       └── definitions.yaml   every gate, declaratively
│   └── tests/
├── data/                          DVC-tracked; only .dvc pointers in git
│   ├── 00_raw/                    source + pii_vault.jsonl (never tracked, never shared)
│   ├── 01_ingested/ … 10_release/
│   └── quarantine/
├── dvc.yaml   params.yaml
└── docs/
```

### Canonical record

One shape flows through every stage; each stage adds fields and removes none.

```jsonc
{
  "rid": "9f2c…",
  "source": { "file_sha256": "…", "offset": 1043, "ingested_at": "2026-08-17T…" },
  "conversation": [ { "speaker": "A", "text": "…" }, { "speaker": "U", "text": "…" } ],
  "catalog": [ { "name": "VerifyEmail_15d", "purpose": "…",
                 "call_when": "{trigger} …", "hold_when": "{hold_other} … {or} …",
                 "require": ["email"],
                 "params": [ { "name": "email", "type": "string", "required": true,
                               "constraint": "{constraint} đúng định dạng email" } ] } ],
  "label": ["VerifyEmail_15d"],
  "assistant_raw": "[\"VerifyEmail_15d\"]",
  "meta": { "…": "verbatim from source" },

  "parse_status": "ok",
  "defects": [],
  "pii": { "spans_replaced": 2, "classes": ["PHONE", "EMAIL"] },
  "dup_cluster_id": "c_0331", "is_representative": true,
  "group_key": "g_7a1e…",
  "triage": { "strata": ["audit"], "cleanlab_score": 0.41, "lf_label": "HOLD", "lf_conf": 0.88 },
  "validation": { "status": "corrected", "verdict": "incorrect",
                  "curated_label": [], "validators": ["u12","u07"],
                  "alpha_contrib": true, "decided_at": "…" },
  "split": "test"
}
```

### Source-integrity gate

Runs on ingest output, before anything else touches the data:

```python
DEFECTS = {
  "label_assistant_mismatch": lambda r: sorted(r.label) != sorted(json.loads(r.assistant_raw)),
  "label_not_in_catalog":     lambda r: not set(r.label) <= {t.name for t in r.catalog},
  "empty_catalog":            lambda r: len(r.catalog) == 0,
  "cardinality_anomaly":      lambda r: len(r.label) > MAX_EXPECTED_CARDINALITY,
}
```

Each match writes the record to `quarantine/<defect>.jsonl` with the defect name and leaves the main path. `empty_catalog` is a **quarantine for triage, not a verdict**: 841 records is large enough that a parser miss and a genuinely toolless prompt must be told apart by hand before either is trusted, and the gate forces that to happen. Quarantined records can be re-admitted by an explicit `dataforce requeue --defect <name>` after the underlying cause is fixed, which creates a new pipeline version.

### PII scrubbing

Two layers, each doing one job. The regex layer maximizes recall and is allowed to be noisy; the LLM layer, prompted with a ±80-character window, decides whether the span is personal data or a price, date, or reference code. Only spans surviving both are replaced.

```
"số của em là không chín không một …"     ← regex hit, LLM: PHONE      → "<PHONE_1>"
"đơn hàng hai không hai bốn sáu tám"        ← regex hit, LLM: ORDER_REF → unchanged
```

Placeholders are stable within a record, so a phone given in turn 3 and confirmed in turn 7 becomes `<PHONE_1>` both times and the tool-calling logic — which turns on whether a required value was *supplied* — is preserved. This is why replacement, not deletion, is specified: deleting the value would flip the ground truth of every `{hold_missing}` judgment in the record.

### Triage and the binary reframing

The label space is the constraint that shapes this whole stage. 14,411 distinct tool names with a maximum frequency of 35 means no classifier, no confident-learning method, and no embedding-based clustering can operate on tool identity. Reframing to (record, tool) → {CALL, HOLD} gives 98,766 examples over 2 classes, and the tool's own description is available as a feature:

```
x = embed(tool.purpose ‖ tool.call_when ‖ tool.hold_when ‖ conversation)
y = tool.name in record.label
```

Static embeddings (`model2vec`, `potion-multilingual-128M`) are used because they are CPU-only and take seconds over 98k rows. Vietnamese coverage is not assumed: the pilot runs a retrieval sanity check — nearest-neighbour agreement on 200 hand-paired records — and falls back to a multilingual sentence-transformer if it fails.

Cleanlab consumes 5-fold cross-validated `predict_proba` from a logistic regression on those embeddings. A low label-quality score does not mean the label is wrong; it means a human should look, which is the only claim triage makes.

### Annotation via Label Studio

The config is generated, one per project, never hand-written:

```xml
<View>
  <Header value="$question"/>
  <HyperText name="evidence" value="$evidence_html" inline="true"/>

  <Choices name="verdict" toName="evidence" choice="single-radio" required="true">
    <Choice value="correct"   hotkey="1"/>
    <Choice value="incorrect" hotkey="2"/>
    <Choice value="unsure"    hotkey="3"/>
  </Choices>

  <View visibleWhen="choice-selected" whenTagName="verdict" whenChoiceValue="incorrect">
    <Choices name="correction" toName="evidence" value="$tool_choices" choice="multiple"/>
    <Choices name="clause" toName="evidence" choice="single">
      <Choice value="trigger"/><Choice value="hold_other"/>
      <Choice value="hold_missing"/><Choice value="constraint"/><Choice value="other"/>
    </Choices>
  </View>

  <TextArea name="note" toName="evidence" rows="2" maxSubmissions="1"/>
  <Choices name="flag" toName="evidence" choice="single">
    <Choice value="not_answerable"/><Choice value="wrong_evidence"/>
    <Choice value="nonsensical"/><Choice value="duplicate"/>
  </Choices>
</View>
```

`$tool_choices` is per-record task data — `[{"value": "VerifyEmail_15d", "html": "<b>VerifyEmail_15d</b><br><small>…</small>"}, …, {"value": "__none__", "html": "Không gọi tool nào"}]` — which is how a correction becomes structurally unable to name a tool outside the catalog. `$evidence_html` carries the question's evidence, the referenced turn highlighted, and the glossary entries for the markers in that record, all escaped at build time.

Note what the pipeline holds rather than Label Studio: the proposed answer, the stratum, the LF and Cleanlab scores, the gold flag. Label Studio sees a question and a set of choices. Everything that could bias an annotator or leak a design detail stays on our side of the wire, joined back on `rid` at pull time.

### The scale ladder

Three rungs, each with an exit gate. You do not climb without passing.

| Rung | Records | Questions | Annotators | Overlap | Purpose |
|---|---:|---:|---:|---:|---|
| **S0 smoke** | 50 | ~70 | 1 | 1 | Prove the plumbing: ingest → publish → pull → export runs end to end in one sitting. Verify `maximum_annotations` behaves as requirement 26 assumes. |
| **S1 pilot** | 500 | ~700 | 2 | 2 (100%) | Prove the *instrument*: is the question answerable, is the glossary right, do two people agree? |
| **S2 scale** | ~3,500 annotated of 21,172 | ~4,500 | 3–5 | mixed | Produce the release. |

**S1 → S2 gate**, all four required:

| Criterion | Threshold | Why |
|---|---|---|
| Krippendorff's α on verdict | **≥ 0.667** | The handbook's tentative-conclusion floor. Below it, the guideline is broken, not the annotators. |
| α upper check | **≤ 0.95**, else investigate | Near-perfect agreement on a task this subtle means the questions dodge the hard cases or the annotators are working mechanically. This is a review trigger, not a hard fail. |
| Question flag rate | **≤ 10%** | Inherited from [`guided-validation`](../guided-validation/spec.md). Above it, the prompt or glossary is wrong. |
| Gold-set accuracy, per annotator | **≥ 0.85** | An annotator below this is retrained before their work counts. |

The pilot also produces the one revision pass on the prompt and the glossary. Confirming the marker glossary remains the blocking prerequisite [`guided-validation`](../guided-validation/spec.md) declares it to be; S1 is where that confirmation is obtained in writing.

**Why S2 does not annotate everything.** 21,172 questions at one minute each is 353 hours, ~44 person-days. The designed subset — 1,000 test + 500 audit + ~2,000 triage-flagged — is ~58 hours, ~7 person-days, and it buys more: a fully-validated test split, an unbiased residual-error estimate on everything untouched, and human attention concentrated where the models say it is needed. The remainder ships as `unvalidated` with a measured error bar, which is an honest artifact. Full manual validation would ship the same corpus six weeks later with no error bar at all, because nothing would have been sampled to estimate one from.

### Release artifact

```
10_release/v1/
├── sft_train.jsonl        messages format, curated labels
├── sft_val.jsonl
├── sft_test.jsonl         100% human-validated, group-disjoint, decontaminated
├── quarantine.jsonl       every excluded record with its defect
├── datasheet.md
├── data_statement.md
├── croissant.json
├── metrics.json           counts, α, flag rate, gold accuracy, residual error ± CI
└── MANIFEST.sha256
```

## Decisions

**Label Studio, not Argilla, and not the DataForce annotation service yet.** *Alternatives:* Argilla (best conceptual fit); build the platform's own UI now; Doccano; Prodigy (commercial). *Why:* Argilla has shipped no functional change in seventeen months, which is a dependency risk that surfaces exactly when you need a fix. Building our own UI first inverts the order of risk — it spends a quarter before anyone has answered whether the *questions* are answerable, which is the actual unknown. Label Studio is maintained, its dynamic-choices feature happens to fit the per-record tool catalog precisely, and generating its XML is a file we own rather than a format we adopt. *Reversible:* yes, and cheaply — Label Studio is touched only by `labelstudio/`, three modules behind the canonical record. Migrating to the DataForce service later is a re-implementation of `publish.py` and `pull.py`.

**The pipeline is DVC stages, not a service.** *Alternatives:* Airflow/Prefect; Celery jobs in the platform API; a shell script. *Why:* every stage is a pure function from artifact to artifact, which is what DVC models natively — and data lineage plus reproducibility from a commit hash is the requirement, not scheduling. An orchestrator would add a scheduler, a database, and a UI to a pipeline that runs a handful of times per release. *Reversible:* yes; each stage is a CLI command an orchestrator could call unchanged.

**Model-assisted quality work happens on binary (record, tool) pairs.** *Alternatives:* multi-label classification over tool names; per-record clustering. *Why:* forced by the measurement — 14,411 classes with a modal frequency of 35 supports no supervised method at all. The reframing yields 98,766 examples over 2 classes with the tool description available as a feature, and it maps cleanly onto how the marker DSL is written (per-tool call/hold conditions). *Reversible:* no, in practice — the LFs, the Cleanlab run, and the triage scores are all defined at pair granularity.

**Dawid-Skene from crowd-kit for both LF votes and annotator votes; Snorkel is optional.** *Alternatives:* Snorkel's `LabelModel` (the handbook's 2.8× result); majority vote. *Why:* both problems are "combine unreliable voters of unknown quality", crowd-kit is already required for annotator aggregation, and Snorkel pulls torch and tensorboard for eight labeling functions. Majority vote throws away the reliability estimate, which is the whole point when one LF is much better than the others. *Reversible:* yes — Snorkel behind an optional extra, swappable at the aggregation call.

**Defects are quarantined, never auto-repaired.** The 48 contradictions could be resolved by preferring the assistant message; the 722 out-of-catalog labels could be truncated to the catalog. *Alternatives:* exactly that, silently. *Why:* both "fixes" are guesses about which of two disagreeing sources is right, applied at scale, invisibly. A quarantine file with 722 records is a morning's work for someone who knows the corpus and a permanent record of what was decided; an auto-repair is a data cascade with a clean-looking count. *Reversible:* re-admission is an explicit command that versions the pipeline.

**PII is replaced with stable placeholders, not deleted or hashed.** *Alternatives:* delete the span; hash it; drop the record. *Why:* the ground truth of this corpus turns on whether a required value was supplied. Deleting a phone number converts a correct `CALL` into what now looks like a correct `{hold_missing}`, silently inverting the label on ~2% of records. A stable typed placeholder preserves suppliedness and co-reference while carrying no personal data. *Reversible:* only from the vault, which never leaves the raw tier — so getting this right the first time matters.

**The test split is 100% human-validated, at any budget.** *Alternatives:* validate a sample of test; validate proportionally. *Why:* every number the release reports is computed on test. A test split that is two-thirds machine-labelled measures agreement with `gemma-4-31B-it`, not correctness, and no amount of downstream care recovers from that. It is the single most load-bearing rule here. *Reversible:* no.

**Group split on catalog fingerprint ∪ dedup cluster.** *Alternatives:* random split; split on `source_index`. *Why:* `source_index` is unique per record and provides no protection — measured, not assumed. Records sharing a tool catalog are near-variants of one scenario (largest such group: 112 records), and a random split puts variants of the same scenario on both sides, inflating every metric. *Reversible:* yes, but every metric produced before the fix would be void.

**Assumption:** Label Studio Community honours `maximum_annotations` for multi-annotator overlap. The docs describe collaborative labelling as available in both editions, while review workflows and agreement analytics are Enterprise. S0 verifies the overlap behaviour empirically before S1 depends on it; if it does not hold, overlap is achieved by publishing the same tasks to one project per annotator and joining on `rid`, which costs a little bookkeeping and nothing else.

**Assumption:** `potion-multilingual-128M` embeds Vietnamese well enough for near-duplicate detection and triage. Checked by the pilot's retrieval sanity test, with a sentence-transformer fallback specified.

**Assumption:** the residual-error estimate from the audit sample is reported as a property of the release, and consumers are expected to read it. The alternative — refusing to ship anything unvalidated — is not on the table at 44 person-days.

**Assumption:** annotators are internal Vietnamese speakers on a self-hosted Label Studio inside the network boundary. No external crowd, so the handbook's annotator-compensation disclosure reduces to recording roles and time in the data statement.

## Versions

| Component | Pinned | Source |
|---|---|---|
| Python (pipeline) | 3.12.14 | [endoflife.date, released 2026-08-12](https://endoflife.date/python) — 3.12 for widest library compatibility; the platform API stays on 3.14 |
| Label Studio | 1.23.0 | PyPI, 2026-03-13 (checked live) — run as the official Docker image |
| label-studio-sdk | 2.1.1 | PyPI, 2026-08-10 (checked live) |
| cleanlab | 2.9.0 | PyPI, 2026-01-13 (checked live) |
| semhash | 0.4.1 | PyPI, 2026-01-20 (checked live) |
| model2vec | 0.9.0 | PyPI, 2026-08-12 (checked live); model `potion-multilingual-128M` |
| crowd-kit | 1.4.2 | PyPI, 2025-10-13 (checked live) |
| krippendorff | 0.8.2 | PyPI, 2025-11-03 (checked live) |
| pandera | 0.32.1 | PyPI, 2026-06-29 (checked live) |
| DVC | 3.67.1 | PyPI, 2026-03-31 (checked live) |
| mlcroissant | 1.1.0 | PyPI, 2026-04-16 (checked live) |
| scikit-learn | 1.9.0 | PyPI, 2026-06-02 (checked live) |
| agent-toolkit | `>=0.1,<0.2`, extra `[llm]` | [spec](../agent-toolkit/spec.md) |
| snorkel *(optional extra)* | 0.10.0 | PyPI, 2024-02-27 — stale; the reason it is optional |

Rejected: **Argilla** 2.8.0 — last release 2025-03-10, no functional commit since (checked on GitHub). **Great Expectations** 1.20.0 — requires `<3.14` and is heavy for artifact-shape checks; pandera covers it.

## Invariants

1. **Nothing is lost between stages.** For every stage, `output_count + quarantined + deduped_out == input_count`. *Check:* the gate runner asserts the reconciliation on every stage, not just ingest, and writes it to `metrics.json`.
2. **`rid` is stable.** Re-ingesting the same source produces byte-identical `rid` values regardless of record order. *Check:* shuffle a fixture, re-ingest, compare the `rid` set.
3. **No PII downstream of `scrub`.** No artifact in `03_scrubbed/` or later matches a literal PII pattern, and `pii_vault.jsonl` is never DVC-tracked. *Check:* a gate scanning every release-tier file; a repo test asserting the vault path appears in `.gitignore` and in no `.dvc` file.
4. **The generator's answer never reaches an annotator.** No Label Studio payload contains `proposed_answer`, `confidence`, `cleanlab_score`, `lf_label`, or `stratum`. *Check:* a contract test over the built payload asserting the key set equals an explicit allowlist — an allowlist, not a denylist, so a new field cannot leak by being forgotten.
5. **Corrections stay in the catalog.** Every stored correction is a subset of that record's own catalog, or the explicit empty set. *Check:* structurally guaranteed by dynamic choices, and asserted again at pull time, because a structural guarantee in someone else's UI is not one of ours.
6. **No group spans splits.** No `group_key` appears in more than one of train/val/test. *Check:* a set-intersection assertion in the split gate.
7. **Test is fully validated.** Every test record has `validation.status ∈ {original, corrected}` — never `unvalidated`. *Check:* export gate.
8. **Label and assistant agree on the way out.** For every exported record, `meta.label` equals the parsed assistant message. *Check:* export gate — the same assertion that found the 48 defects on the way in.
9. **Releases are reproducible.** `dvc repro` from a clean checkout at a given commit reproduces every artifact's SHA-256. *Check:* CI runs it on the S0 fixture and diffs `MANIFEST.sha256`.
10. **The sampling design is reconstructible.** Every annotated record records which stratum selected it and with what probability. *Check:* the residual-error estimator refuses to run when any annotated record lacks a stratum.

## Error Behavior

Gates fail loudly and stop the DAG. A failed gate writes `data/<stage>/GATE_FAILED.json` with the assertion, the observed value, the expected value, and the offending record IDs (capped at 100), and exits non-zero so `dvc repro` halts. No stage consumes an input whose gate did not pass.

| Situation | Behavior |
|---|---|
| Source SHA-256 differs from `params.yaml` | Hard stop. A changed source is a new dataset version, decided by a human, never merged silently. |
| Defect count moves >±10% from declared | Hard stop with the delta. The declared counts are the contract with the corpus. |
| LLM unavailable during PII verification | Stage stops; already-verified spans are kept and the stage resumes from its checkpoint. A record with unverified hits never advances — failing open on PII is the one failure this pipeline will not take. |
| LLM unavailable during generation | Per [`guided-validation`](../guided-validation/spec.md): record marked `generation_failed`, run continues, task never published without a question. |
| Token budget exhausted mid-run | Clean partial stop; generated questions retained; run status `partial`. Not an error. |
| Label Studio unreachable on publish | Retry with backoff, 5 attempts; then fail the stage with the tasks already pushed recorded, so a resume does not duplicate. Publishing is idempotent on `rid`. |
| Response has `verdict=incorrect` with no correction | Rejected, not repaired. Returned to the queue with the reason; counted in `metrics.json`. |
| α below 0.667 at the pilot gate | Hard stop with the per-focus breakdown. The remedy is a guideline revision and a re-pilot, never lowering the threshold. |
| α above 0.95 | Warning plus a mandatory written review note in the datasheet. Not a stop. |
| Annotator below 0.85 on gold | Their work is held pending review; already-submitted answers are re-queued for a second opinion rather than discarded. |
| Group leakage or n-gram overlap detected | Hard stop. Every metric computed on a leaked split is void, so there is nothing to salvage by continuing. |
| A record cannot be scrubbed with confidence | Quarantined to `quarantine/pii_uncertain.jsonl`, excluded from the release, counted in the datasheet. |

The failure mode with no automated detector is a **plausible but wrong question** — one that reads well and asks about the wrong turn. The flag rate is the only instrument, and it is why the 10% threshold is a gate rather than a metric.

## Testing Strategy

- **Contracts.** Every artifact has a pandera schema; a round-trip test writes, reads, and validates each. A schema change that is not accompanied by a stage change fails.
- **Adapter.** Fixtures covering all 13 observed `meta` key-sets, each label cardinality, catalog sizes 0 / 1 / 8 / 20, and malformed `TOOLS:` blocks. One test asserts marker tokens survive parsing **verbatim** — a parser that strips them would pass every other test while destroying the annotator's only evidence.
- **Source-integrity gate.** A fixture containing one instance of each defect class, asserting each lands in the right quarantine file with the right label, and that the main path count drops by exactly four.
- **PII.** A hand-built Vietnamese fixture of spoken phone numbers, spoken emails, national IDs, prices, dates, and order references — asserting recall on the first three and *no* replacement on the last three. Placeholder stability is tested by a record mentioning the same number twice. A test asserts the vault path is absent from `dvc.yaml` and present in `.gitignore`.
- **Dedup and grouping.** Known duplicate pairs from the corpus; assertion that `source_index` is rejected as a group key and that the largest catalog group (112 records) stays intact through splitting.
- **Triage.** Each labeling function against hand-labelled marker fixtures; Dawid-Skene against a synthetic voter set with known reliabilities; the audit sample-size formula against worked values (`p=0.05, e=0.02 → 457`).
- **Label Studio integration.** The generated config validated against a live Label Studio instance in CI via testcontainers — creating the project, pushing three tasks, and pulling back a submitted annotation. The invariant-4 allowlist test runs on the built payload without needing the server.
- **Agreement.** Krippendorff's alpha against published worked examples from the IAA literature, not only against our own data.
- **Split and decontamination.** A fixture with a deliberately planted group spanning what would be a random split, asserting the gate catches it; a planted 13-gram overlap, asserting the same.
- **End-to-end (S0 as a test).** The 50-record smoke run *is* the integration test: `dvc repro` from raw to release against a stubbed LLM and a containerized Label Studio, asserting a byte-identical `MANIFEST.sha256` on a second run. This passing is the definition of the pipeline being done.
- **Reproducibility.** CI re-runs S0 from a clean checkout and diffs the manifest, which is invariant 9.

## Out of Scope

- **Image, audio, and video.** Explicitly deferred; the platform spec's image controls go with them.
- **Model training and evaluation.** This pipeline produces a dataset and a metric definition. Running the fine-tune, the learning curve's actual training runs, and any eval harness belong to a separate spec — the learning curve is specified here as a *requirement on the release*, and whoever builds the trainer produces it.
- **Synthetic data generation.** The corpus is already two-thirds machine-labelled; generating more before the existing labels are validated is the model-collapse failure the handbook describes. Revisit after the first release measures the residual error rate, and only for the long-tail strata.
- **Active learning loops.** Triage is a one-shot ranking per release, not a model that retrains as annotations arrive.
- **The DataForce annotation service.** Deferred, not cancelled — the pilot is what decides whether it is worth building, and [`dataforce-platform`](../dataforce-platform/spec.md) remains the spec for it.
- **Automatic write-back to the source file.** Export produces an artifact; putting it anywhere is a human step.
- **Multi-language.** Vietnamese only, for the corpus, the questions, and the PII detectors.
- **Cross-border transfer review.** Flagged by the handbook and real under Data Law 60/2024, but it is a legal review of where the data and the LLM endpoint sit, not a pipeline stage. It must happen before any offshore endpoint is used for the PII verification pass.

---

**Grounded in:** measurements over the full corpus (counts in Context are reproducible with the pipeline's `dataforce profile` command) · [Label Studio](https://labelstud.io/guide/setup) · [Cleanlab](https://github.com/cleanlab/cleanlab) · [SemHash](https://github.com/MinishLab/semhash) · [crowd-kit](https://github.com/Toloka/crowd-kit) · [DVC](https://dvc.org) · [Croissant](https://github.com/mlcommons/croissant) · Gebru et al., *Datasheets for Datasets* (CACM 2021) · Bender & Friedman, *Data Statements* (TACL 2018) · Northcutt et al., *Pervasive Label Errors* (NeurIPS 2021) · Sambasivan et al., *Data Cascades* (CHI 2021) · Shumailov et al., *Model collapse* (Nature 2024) · Penedo et al., *FineWeb* (arXiv:2406.17557)
