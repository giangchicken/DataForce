# SFT Dataset Pipeline — Raw Corpus to Released Training Set

## What

A reproducible, gated pipeline that turns the raw Tool-Decision corpus (`fc_train_final.json`) into a versioned, documented, SFT-ready dataset. It is fifteen DVC stages, each producing a checksummed artifact and each guarded by a machine-checked **gate** that fails the run rather than passing bad data downstream. Existing open-source carries the annotation UI, deduplication, annotator aggregation, agreement statistics, and data versioning; this spec builds only the five things that do not exist for this corpus — a marker-preserving adapter, the validation-question generator, a Vietnamese spoken-form PII scrubber, a multi-model **LLM jury** that finds records worth human attention, and the gate runner.

The prediction task is never reformulated. Every model, every juror, and every annotator works on the corpus's own task: given a tool catalog and a conversation, name the **set** of tools that should fire — possibly the empty set.

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
| Catalog size per record | 0–20 tools |
| Distinct tool-catalog fingerprints | 17,596 (16,293 singletons; largest group 112) |
| Distinct `meta` key-sets | 13 |
| Records labelled by `gemma-4-31B-it` | 14,241 (67.3%) |
| Records carrying `orig_label` (already relabelled once) | 1,358, of which 1,346 changed |
| Exact-duplicate user turns | 491 records (2.32%) |
| Exact-duplicate (system, user) pairs | 1 |
| Prompt size (system + user) | mean 4,750 chars, p50 4,446, p90 6,310, p99 17,044 |

Four defects are already detectable without a single human judgment:

| Defect | Count | Why it is fatal for SFT |
|---|---:|---|
| `meta.label` disagrees with the assistant message | **48** (0.227%) | The assistant message *is* the training target. Two sources of truth disagree; one of them trains the model. |
| Label names a tool absent from that record's own catalog | **722** (3.41%) | The target tells the model to call something it was never offered. Unlearnable, and it teaches hallucination. |
| Catalog parser finds no `[ToolName]` block | **841** (3.97%) | Either genuinely toolless prompts or a parser miss — the two must be distinguished before either is trusted. |
| `source_index` is unique per record (13,366 distinct over 13,366 records) | — | It looks like a grouping key and is not one. Splitting on it gives no leakage protection. |

The 48-record contradiction also explains a discrepancy inside our own documents: [`guided-validation`](../guided-validation/spec.md) reports 7,486 zero-label records, counted from the assistant message; counting from `meta.label` gives 7,498. The 12-record net difference is the arithmetic of those 48 disagreements. That is exactly the class of quiet defect this pipeline exists to surface, and it survived a careful read of the corpus.

**The label space rules out classifier-based quality tooling.** 14,411 distinct tool names with a modal frequency of 35 means no fixed class space exists, so Confident Learning, label-error classifiers, and any method needing `predict_proba` over a label vocabulary cannot be applied to this corpus as it stands. The alternative is not to reshape the task until such a method fits — it is to use a method that needs no class space at all. A generative LLM asked to produce the tool set is exactly that, which is why the quality signal here comes from an LLM jury rather than from Cleanlab.

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
| Human-verdict aggregation (Dawid-Skene, MACE) | **crowd-kit** | 1.4.2 (2025-10-13) |
| Krippendorff's alpha, nominal | **krippendorff** | 0.8.2 (2025-11-03) |
| Artifact schema validation | **pandera** | 0.32.1 (2026-06-29) |
| Data versioning and the stage DAG | **DVC** | 3.67.1 (2026-03-31) |
| Machine-readable dataset metadata | **mlcroissant** | 1.1.0 (2026-04-16) |
| LLM access, retry, rate limiting, streaming JSON, slot filling, JSON extraction | **[`agent-toolkit`](../agent-toolkit/spec.md)** | specified, built first |

**Argilla was the obvious candidate and is rejected.** It is the closest fit on paper — LLM-data-native, Python-first, records with typed questions and built-in distribution. But its last release is 2.8.0 on 2025-03-10, and every commit to `main` since that date is a README or project-status edit: seventeen months with no functional change. Betting an annotation pipeline on a library that has stopped shipping is a cost that lands later and cannot be undone cheaply. Label Studio is heavier and its XML labeling config is the thing [`dataforce-platform`](../dataforce-platform/spec.md) deliberately rejected for the platform's *own* schema — but it is maintained, and here we only *generate* that XML, never author it by hand.

**Cleanlab is deferred, not dismissed.** Confident Learning is the right tool for a fixed label space, and this corpus does not have one (above). Adopting it would mean either collapsing 14,411 tool names into a coarse proxy label — reshaping the task to fit the tool — or building a per-decision classifier whose class balance and feature pipeline are themselves a project. The LLM jury needs neither, produces a richer signal, and reuses infrastructure that already has to exist for question generation. If the jury's precision turns out to be the bottleneck after the first release, Cleanlab returns as a second opinion over whatever fixed label space the release has by then established.

What no existing repository provides, and this spec therefore builds:

1. **The `fc_tool_decision` adapter** — parsing the `TOOLS:` block into a structured catalog while preserving the marker DSL (`{trigger}`, `{hold_missing}`, …) verbatim, per [`guided-validation`](../guided-validation/spec.md).
2. **The question generator** — focus-by-rule selection, batch generation with a token budget, caching.
3. **The Vietnamese spoken-form PII scrubber** — number words, spoken `@`, spoken punctuation.
4. **The LLM jury and its key pool** — many models voting the set-valued task, aggregated with a set-aware distance, dispatched across many API keys with per-key budgets and quota failover.
5. **The gate runner** — declarative assertions between stages, the mechanism that makes "reliable" mean something checkable.

### Relationship to the existing specs

This spec sits **above** the other three and narrows two of them. Applying it requires these amendments, which are proposed here and not yet made:

- **[`dataforce-platform`](../dataforce-platform/spec.md):** drop image modality from v1 — requirement 7's `bbox`/`polygon`, requirement 27's IoU comparators, requirement 31's COCO/YOLO exporters, and the images in the E2E scenario. Defer the whole FastAPI + React annotation service behind a Label Studio-based v0 until the pilot gate passes. What Label Studio does *not* give us — a review workflow, agreement metrics, the catalog, subscriptions — is precisely what remains of the platform's justification, and the pilot is what establishes whether that is worth a quarter of engineering.
- **[`guided-validation`](../guided-validation/spec.md):** unchanged in substance. The question model, focus rules, glossary, correction shape, and flag taxonomy are all retained; only the rendering surface changes from a bespoke React card to a generated Label Studio config. Its invariant 1 (the generator's answer never reaches the annotator) gets *stronger*: neither the generator's proposed answer nor any juror's vote is sent to Label Studio at all, so nothing can leak through a response schema.
- **[`agent-toolkit`](../agent-toolkit/spec.md):** unchanged. It is the first thing built. The jury's key pool stays in this pipeline; it graduates into the library only when a second consumer needs it.

## Requirements

### Acceptance criteria, fixed before any data moves (Step 1)

1. The release's primary metric is **exact-set-match accuracy** of the predicted tool set against the gold set, measured on the human-validated test split only. Secondary metrics: abstention (zero-label) precision and recall, and macro set-F1. All three are declared in `params.yaml` before the first stage runs and are not changed afterwards without a new release version.
2. The pipeline produces a **learning curve** on the pilot — the primary metric at 25%, 50%, and 100% of available training data — so the question "more data or better data?" is answered with a measurement rather than an opinion.
3. The task representation is fixed for the whole pipeline: input is (tool catalog, conversation), output is a **set of tool names drawn from that record's own catalog**, and the empty set is a first-class answer, not a missing value. No stage may substitute a per-tool binary, a coarse proxy class, or a cardinality bucket for the set.

### Ingest and source integrity (Steps 2, 3)

4. Ingest streams the source via `agent_toolkit.file_utils.iter_json_array_file`. The 126 MiB file must never be loaded whole.
5. Every record gets a stable `rid = sha256(system ‖ user ‖ assistant)[:16]`, independent of position, so artifacts are diffable across re-ingests and re-ordering is not a change.
6. Ingest records source provenance per record: source file SHA-256, byte offset, `meta` verbatim, and the ingest timestamp. Nothing is dropped; unparsable records are carried with `parse_status = "unparsed"` and their raw text.
7. The **source-integrity gate** detects and quarantines, as separate named defect classes: `label_assistant_mismatch` (48 expected), `label_not_in_catalog` (722 expected), `empty_catalog` (841 expected), and `label_cardinality_anomaly`. Quarantined records leave the main path into `data/quarantine/<defect>.jsonl` with the defect recorded; they are never silently deleted and never silently kept.
8. Expected defect counts are declared in `params.yaml`. A count that moves by more than ±10% fails the gate — the source changed, and that must be a decision rather than a surprise.

### PII (Step 9, legal)

9. A scrub stage detects and replaces, in every message, both literal and Vietnamese spoken-form personal data: phone numbers, email addresses, national ID numbers, bank account numbers, and full personal names in the customer turn. Spoken-form detection covers digit words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), spoken `@` (`a còng`), and spoken punctuation (`chấm`, `gạch dưới`).
10. Replacement is a **stable typed placeholder** (`<PHONE_1>`, `<EMAIL_1>`) scoped per record, so a value referenced twice in one conversation stays co-referent and the tool-calling semantics survive scrubbing. Replacement is never deletion.
11. Every regex hit above a configured recall threshold is verified by an LLM pass over the surrounding window, using `agent-toolkit`, to cut false positives on prices and dates. The regex layer sets recall; the LLM layer sets precision.
12. A scrubbing report records, per class, the number of spans replaced and a sample of 20 *placeholders in context* (never the original values). The mapping from placeholder to original value is written to `data/00_raw/pii_vault.jsonl`, which is `.gitignore`d, not DVC-tracked, and never leaves the raw tier.
13. The scrub gate fails if any release-tier artifact matches a literal PII pattern.

### Deduplication and grouping (Step 3)

14. Exact duplicates are removed on `sha256(system ‖ user)`, keeping the record with the richer `meta`.
15. Near-duplicate and semantic duplicates are found with SemHash over the concatenated conversation. Cluster members are not deleted; they are assigned a shared `dup_cluster_id`, and one representative per cluster is marked `is_representative`. Deletion happens at export, from an explicit filter, so the decision is reversible and recorded.
16. Every record gets a `group_key` for splitting: the catalog fingerprint, unioned with its `dup_cluster_id`. `source_index` is explicitly **not** a group key (requirement measured above).

### The LLM jury (Steps 3, 5)

17. A **jury** of independent LLMs predicts the tool set for each record, from the record's own system message and conversation, returning a JSON array of tool names. Each juror answers the corpus's task exactly as stated in requirement 3 — no reformulation, no per-tool questioning, no auxiliary labels.
18. A juror vote naming a tool outside the record's catalog, or failing to parse as an array of strings, is **invalid**: it is discarded, retried once at temperature 0, and then recorded as an abstention. An invalid vote never becomes a partial vote by truncation.
19. The panel must be **family-diverse**: at least three jurors drawn from at least three distinct model families. Repeated sampling of one model at temperature > 0 does not count as a panel, because correlated jurors agree on their shared errors and the disagreement signal collapses.
20. No juror in the primary panel may come from the model family that labelled the corpus. 14,241 records (67.3%) were labelled by `gemma-4-31B-it`; a `gemma` juror measures family agreement, not correctness. A same-family juror may be run as an explicitly-labelled **control** whose only output is an estimate of how much of the corpus label is family-specific.
21. Votes are cast at temperature 0 and cached on `(rid, model, prompt_version)`. The cache key excludes the API key: which key served a call must not be able to change the vote.
22. Jury dispatch runs over a **key pool**. Each entry carries its own request and token budget; the pool round-robins, backs off per key on 429, quarantines a key that exhausts quota for a cooldown, and continues on the remaining keys. A single exhausted key never stalls a run. Per-key and per-juror consumption is reported on the run.
23. Set-valued agreement everywhere uses one distance, `δ(A,B) = 1 − |A ∩ B| / |A ∪ B|`, with `δ(∅, ∅) = 0` by definition. That convention is load-bearing: 35.4% of the corpus is the empty set, and treating two agreeing abstentions as maximally distant would invert the signal on a third of the data.
24. Per record the jury stage stores: every individual vote, the **majority-consensus set** (tools included by a strict majority of valid jurors), the **plurality set** (most frequent exact set), an `exact_unanimity` flag, `jury_cohesion = 1 − mean pairwise δ`, and `corpus_conflict = δ(consensus, corpus_label)`.
25. Juror weights are calibrated on the gold set as mean set-F1 against human-validated labels, and are reported per juror. A juror whose gold F1 falls below a declared floor is dropped from the panel for that release, and the drop is recorded.
26. The jury runs in **staged escalation**: a 3-juror pass over the corpus, then an expanded panel only on records showing conflict or low cohesion. The stage reports estimated cost before starting and treats the token budget as a hard ceiling, stopping cleanly with a partial result.
27. The jury's consensus accuracy on the human-validated test split — and each juror's individually — is reported in `metrics.json`. It is the zero-shot baseline the fine-tune has to beat, and it comes free with the triage pass.
28. **No jury vote ever becomes a training label without human confirmation.** The jury selects and ranks records for human attention; it does not relabel. A corpus that is already two-thirds machine-labelled cannot be improved by overwriting it with more machine labels — that is the recursion the model-collapse literature describes (Shumailov et al., *Nature* 2024).
29. Optionally and explicitly, the unvalidated remainder may carry jury consensus as a **separate tier**: `validation.status = "jury_consensus"`, permanently barred from the test split, reported in the datasheet with its own error bar measured against the human-validated audit sample. This is opt-in per release and off by default.
30. Deterministic marker-DSL rules — missing required parameter, `{hold_missing}` clause satisfied, `{trigger}` keyword in the last turn, `{constraint}` violated, `{turn_trigger}` scope violation — act as hard validity constraints on juror votes and as the defect detectors of requirement 7. They may additionally be admitted as one **rule juror** producing a set, but only if their gold set-F1 clears the same floor as any other juror.

### Triage — deciding what a human looks at

31. Records are bucketed on two axes, cohesion and conflict, and the buckets carry different meanings and different destinations:

| | Jury agrees with itself | Jury split |
|---|---|---|
| **Agrees with corpus** | `agreed` — audit sample only | `ambiguous_agreed` — glossary review candidate |
| **Disagrees with corpus** | `likely_label_error` — top of queue | `hard_record` — expert plus guideline fix |

32. Bucket thresholds live in `params.yaml` and are **provisional until the pilot measures them**. The pilot reports each bucket's precision — the fraction of `likely_label_error` records the annotators actually judged incorrect — and the thresholds get exactly one re-tuning pass from that measurement. Shipping thresholds that were never checked against a human verdict is the failure this requirement exists to prevent.
33. The annotation queue is filled from five strata with declared quotas: (a) `likely_label_error`, (b) `hard_record`, (c) the zero-label population, deliberately oversampled because it carries the corpus's real difficulty, (d) a **uniform random audit sample** whose only purpose is an unbiased residual-error estimate, and (e) the entire test split. Every stratum's selection is recorded per record so the sampling design is reconstructible.
34. The random audit sample is sized from the target confidence interval, not chosen by feel: `n = z²·p(1−p)/e²`. At `p = 0.05` and `e = ±0.02`, `n = 457`; the default is 500. If the observed rate exceeds the assumed `p`, the stage recomputes `n` and requests more.

### Question generation and annotation (Steps 4, 5)

35. Question generation follows [`guided-validation`](../guided-validation/spec.md) unchanged: focus chosen by rule, batch pre-generation, token budget as a hard ceiling, idempotence on `(rid, prompt_version, model)`.
36. Publishing creates a Label Studio project from a **generated** labeling config. The correction control is a dynamic `<Choices value="$tool_choices" choice="multiple">` populated from that record's own catalog plus an explicit "no tool" option, so a correction is a set drawn from the catalog by construction.
37. All evidence and glossary HTML is built by the pipeline and **escaped**; corpus text is never interpolated into markup unescaped.
38. Nothing from the generator or the jury is written to Label Studio in any field — not data, not metadata, not a prediction. Proposed answers, juror votes, cohesion, conflict, and stratum stay in the pipeline and are joined back on `rid` after responses are pulled.
39. Overlap is achieved by project membership rather than a per-task setting: the pilot runs one project with both annotators assigned and `maximum_annotations` set to the annotator count, giving 100% overlap; at scale the flagged and audit strata keep overlap 2 and the remainder runs at overlap 1. *This depends on Label Studio Community honouring `maximum_annotations`, which the smoke stage verifies before anything else is built on it.*
40. A gold set of ≥50 expert-labelled records is mixed into every project as ordinary tasks, visually indistinguishable, and used both to score each annotator continuously and to calibrate juror weights per requirement 25.
41. Pulling responses normalizes them into the canonical answer shape and **rejects, rather than repairs**, any response where `verdict = incorrect` carries no correction. Rejected responses return to the queue with the reason attached; correction-required is enforced in the pipeline because Label Studio's conditional validation cannot be relied on.

### Aggregation, adjudication, curation (Step 6)

42. Krippendorff's alpha on the **verdict** (nominal: correct / incorrect / unsure) is computed across all overlapped records, per question focus and overall, with the `krippendorff` package.
43. Agreement on **corrections** — which are sets — is computed as α with the `δ` of requirement 23, implemented in this pipeline because the library covers only nominal, ordinal, interval, and ratio scales. Its nominal degenerate case is tested against the library's output.
44. Where overlap ≥ 2, verdicts are aggregated with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote. Corrections are aggregated as the majority-consensus set under the same rule the jury uses.
45. Records where annotators disagree, or where the aggregated confidence is below threshold, are published to a second **adjudication** Label Studio project showing both answers and both notes, resolved by a reviewer who did not produce either. Label Studio Community has no review workflow; this is that workflow.
46. Curation applies accepted corrections to produce the curated label, and records for every record whether its label is `original`, `corrected`, `jury_consensus`, or `unvalidated`, with the validator and the decision date.

### Split, decontamination, export (Step 7)

47. Splitting is **group-based on `group_key`**, never random. A group is wholly in one split.
48. The test split is **100% human-validated**. A record that has not been through annotation cannot enter test, at any budget, and `jury_consensus` records are barred permanently. This is the rule that keeps every reported number meaningful.
49. Decontamination verifies zero 13-gram overlap between the test split and train, and zero shared `group_key`. Overlap fails the gate.
50. Export emits SFT JSONL in the source `messages` shape, with the curated label in both the assistant message and `meta.label` — which, given the 48 contradictions found at ingest, must be asserted equal on the way out.
51. Every exported record carries provenance: source SHA-256, pipeline version, validation status, validator, dedup cluster, split, stratum, and — where the jury touched it — the panel version and the consensus it produced.
52. The release is a DVC-tracked directory with a manifest listing every file's SHA-256, and the whole release is reproducible from one git commit plus `dvc repro`.

### Documentation (Step 8)

53. Each release ships a **datasheet** (Gebru et al.) answering the handbook's six questions, a **data statement** (Bender & Friedman) covering language variety and both creator and annotator demographics, and a **Croissant** metadata file validated by `mlcroissant`.
54. The datasheet states the synthetic share explicitly. 14,241 of 21,172 records (67.3%) are machine-labelled by `gemma-4-31B-it`, and 1,358 have already been relabelled once. Given the model-collapse result, a corpus that is two-thirds machine-labelled must be documented as such, and the human-validated test split is the mitigation that makes the release measurable at all.
55. The datasheet names the jury panel — every juror's model, version, and gold-calibrated weight — because the selection of which records humans looked at is part of how the dataset was made.
56. Documentation generation is a pipeline stage with a gate, not a manual step. A missing required datasheet field fails the release.

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
| 5 | `jury` | 3, 5 | `05_jury/votes.jsonl`, `consensus.jsonl` | ≥3 families; no corpus-family juror in panel; tokens ≤ budget; invalid-vote rate ≤ 5% |
| 6 | `triage` | 3, 5 | `06_triaged/queue.jsonl` | every stratum met its quota; audit `n` ≥ computed |
| 7 | `generate` | 4 | `07_questions/` | schema-valid ≥ 98%; tokens ≤ budget |
| 8 | `publish` | 5 | Label Studio project + `07_questions/published.jsonl` | payload key set equals the allowlist |
| 9 | `pull` | 5 | `08_responses/` | every `incorrect` has a correction |
| 10 | `aggregate` | 6 QA | `08_responses/aggregated.jsonl` | α ≥ 0.667; flag ≤ 10%; gold ≥ 0.85 |
| 11 | `curate` | 6 | `09_curated/` | every correction ⊆ that record's catalog |
| 12 | `split` | 7 | `10_splits/{train,val,test}.jsonl` | zero group leakage; zero 13-gram overlap |
| 13 | `export` | 7 | `11_release/sft.jsonl` | test 100% human-validated; counts reconcile; label == assistant |
| 14 | `document` | 8 | `11_release/{datasheet.md,croissant.json}` | all required fields present; Croissant validates |

Stages 8–10 loop: publish → annotate → pull → aggregate → adjudicate → pull again. Stage 5 re-runs when the panel changes, and its cache makes an unchanged juror free.

### Repository layout

```
dataforce/
├── pipeline/
│   ├── dataforce_pipeline/
│   │   ├── cli.py                 dataforce <stage> ... | dataforce gate run <stage>
│   │   ├── contracts.py           pandera schemas + pydantic models, one per artifact
│   │   ├── setops.py              δ, majority consensus, plurality, cohesion, α_set
│   │   ├── adapters/
│   │   │   └── fc_tool_decision.py  TOOLS: parser, markers preserved verbatim
│   │   ├── pii/
│   │   │   ├── patterns.py        literal + spoken-form Vietnamese detectors
│   │   │   ├── verify.py          LLM precision pass via agent-toolkit
│   │   │   └── vault.py           placeholder ↔ original, raw tier only
│   │   ├── rules/                 marker-DSL constraints; validity + optional rule juror
│   │   ├── jury/
│   │   │   ├── panel.py           juror definitions, family tagging, diversity check
│   │   │   ├── keypool.py         per-key budgets, round-robin, quota failover
│   │   │   ├── vote.py            one cached call per (rid, juror), temperature 0
│   │   │   ├── consensus.py       set aggregation, cohesion, conflict, gold weights
│   │   │   └── escalate.py        staged panel expansion
│   │   ├── triage/                buckets, strata, audit sample sizing
│   │   ├── labelstudio/
│   │   │   ├── config.py          generates the labeling XML
│   │   │   ├── publish.py         project creation, task push, payload allowlist
│   │   │   └── pull.py            response normalization
│   │   ├── quality/               α (nominal + set), gold scoring, adjudication sets
│   │   ├── release/               split, decontaminate, export, datasheet, croissant
│   │   └── gates/
│   │       ├── runner.py
│   │       └── definitions.yaml   every gate, declaratively
│   └── tests/
├── data/                          DVC-tracked; only .dvc pointers in git
│   ├── 00_raw/                    source + pii_vault.jsonl (never tracked, never shared)
│   ├── 01_ingested/ … 11_release/
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

  "jury": {
    "panel_version": 2,
    "votes": [ { "juror": "j1", "set": ["VerifyEmail_15d"], "valid": true },
               { "juror": "j2", "set": [], "valid": true },
               { "juror": "j3", "set": ["VerifyEmail_15d"], "valid": true } ],
    "consensus": ["VerifyEmail_15d"], "plurality": ["VerifyEmail_15d"],
    "exact_unanimity": false, "cohesion": 0.67, "corpus_conflict": 0.0
  },
  "triage": { "bucket": "agreed", "strata": ["audit"] },

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

### The LLM jury

Each juror gets the record's own system message and conversation, and is asked for the task as the corpus states it:

```
<the record's system message, TOOLS: block and markers verbatim>
<the conversation>

Trả về DUY NHẤT một JSON array gồm tên các tool cần gọi, theo đúng thứ tự gọi.
Nếu không cần gọi tool nào, trả về [].
Chỉ được dùng tên tool xuất hiện trong danh sách trên.
```

The response is parsed with `agent_toolkit.string_utils.extract_json_from_text`, then validated: an array of strings, every element in the record's catalog. Anything else is retried once and then recorded as an abstention — never truncated into a partial vote, because a silently-truncated vote reads as a confident disagreement and would poison the signal it is supposed to produce.

**Aggregation is set-valued throughout.** One distance does all the work:

```python
def delta(a: set[str], b: set[str]) -> float:
    if not a and not b: return 0.0          # two abstentions agree perfectly
    return 1.0 - len(a & b) / len(a | b)
```

That `δ(∅,∅) = 0` line is not a detail. 35.4% of this corpus is the empty set; a Jaccard implementation returning `0/0 → nan` or treating two empty sets as maximally distant would make the zero-label population — the part carrying the corpus's real difficulty — look like the part with the least jury agreement.

From the votes: `consensus` is the set of tools a strict majority of valid jurors included; `plurality` is the most frequent exact set; `cohesion = 1 − mean pairwise δ`; `corpus_conflict = δ(consensus, corpus_label)`. Consensus can be a set no individual juror proposed, which is acceptable for a ranking signal and is exactly why requirement 28 forbids it from becoming a label on its own.

**Panel composition.** Three jurors minimum, three distinct families minimum, and no juror from the `gemma` family in the primary panel — that family labelled 67.3% of the corpus, so its agreement measures lineage rather than correctness. Running one `gemma` juror as a declared control is worth doing once: the gap between the control's agreement with the corpus and the panel's agreement with the corpus is a direct estimate of how much of this dataset is one model's opinion.

**Cost, measured rather than guessed.** The corpus is 100,557,307 prompt characters. At 3 characters per token — stated as an assumption, since Vietnamese diacritics tokenize unevenly — one full pass is ~34M input tokens and ~0.8M output:

| Pass | Records | Input tokens |
|---|---:|---:|
| 3-juror sweep, whole corpus | 21,172 | ~101M |
| escalate to 7 jurors on ~15% | ~3,200 | ~+20M |
| **staged total** | | **~121M in, ~3M out** |

Against a flat 7-juror sweep at ~235M, staging saves about half, and the cache makes a re-run after a panel change cost only the new juror. The p99 prompt is ~17,000 characters (~5.7k tokens) from the 20-tool catalogs — no context-window concern on any current model.

**Key pool.** Jurors are `(family, model, base_url, key_group)`; keys are pooled per group with their own request and token budgets. The pool dispatches round-robin, backs off per key on 429, quarantines an exhausted key for a cooldown, and keeps going on the rest — so a run's throughput degrades with key exhaustion instead of stopping. Concurrency and rate limiting come from `agent-toolkit`'s `TrafficController`; the pool sits above it, one controller per key group. Consumption is reported per key and per juror so the next run can be budgeted from evidence.

### Triage

Two axes, four buckets, four different meanings:

```
                    cohesion high              cohesion low
conflict = 0    │ agreed                  │ ambiguous_agreed
                │ → audit sample only     │ → glossary review candidate
                ├─────────────────────────┼──────────────────────────────
conflict > 0    │ likely_label_error      │ hard_record
                │ → top of the queue      │ → expert + guideline fix
```

The distinction that a single score cannot express: a confidently-unanimous jury disagreeing with the corpus is probably a **label** problem, while a split jury disagreeing with the corpus is probably a **guideline** problem — the record may be genuinely underdetermined by the tool descriptions. Those need different people and produce different fixes, and collapsing them into one priority number sends both to the same queue.

Thresholds separating the quadrants start as guesses in `params.yaml` and are re-tuned exactly once, from the pilot's measurement of each bucket's precision against human verdicts. A bucket whose precision the pilot cannot establish does not get a quota at scale.

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

`$tool_choices` is per-record task data — `[{"value": "VerifyEmail_15d", "html": "<b>VerifyEmail_15d</b><br><small>…</small>"}, …, {"value": "__none__", "html": "Không gọi tool nào"}]` — which is how a correction becomes a set drawn from the record's own catalog by construction.

Note what the pipeline holds rather than Label Studio: the generator's proposed answer, every juror vote, cohesion, conflict, bucket, stratum, and the gold flag. Label Studio sees a question and a set of choices. Showing an annotator that three models said `[]` would turn an independent judgment into a ratification, which is the same argument [`guided-validation`](../guided-validation/spec.md) makes about the generator's answer, now applying to a larger set of fields.

### The scale ladder

Three rungs, each with an exit gate. You do not climb without passing.

| Rung | Records | Questions | Annotators | Jury | Purpose |
|---|---:|---:|---:|---|---|
| **S0 smoke** | 50 | ~70 | 1 | 3 jurors, stubbed and live | Prove the plumbing end to end in one sitting. Verify `maximum_annotations`, the key pool's failover, and cache determinism. |
| **S1 pilot** | 500 | ~700 | 2 at 100% overlap | 3 jurors, real | Prove the *instruments*: is the question answerable, is the glossary right, do two people agree — and does each triage bucket predict what the humans actually find? |
| **S2 scale** | ~3,500 annotated of 21,172 | ~4,500 | 3–5, mixed overlap | staged 3 → 7 | Produce the release. |

**S1 → S2 gate**, all five required:

| Criterion | Threshold | Why |
|---|---|---|
| Krippendorff's α on verdict | **≥ 0.667** | The handbook's tentative-conclusion floor. Below it, the guideline is broken, not the annotators. |
| α upper check | **≤ 0.95**, else investigate | Near-perfect agreement on a task this subtle means the questions dodge the hard cases or the annotators are working mechanically. A review trigger, not a hard fail. |
| Question flag rate | **≤ 10%** | Inherited from [`guided-validation`](../guided-validation/spec.md). Above it, the prompt or glossary is wrong. |
| Gold-set accuracy, per annotator | **≥ 0.85** | An annotator below this is retrained before their work counts. |
| `likely_label_error` bucket precision | **≥ 0.30** | If fewer than three in ten records the jury flags are actually wrong, the jury is sending humans on a walk and the panel needs changing before 21k records depend on it. |

The pilot also produces the one revision pass on the prompt, the glossary, and the bucket thresholds. Confirming the marker glossary remains the blocking prerequisite [`guided-validation`](../guided-validation/spec.md) declares it to be; S1 is where that confirmation is obtained in writing.

**Why S2 does not annotate everything.** 21,172 questions at one minute each is 353 hours, ~44 person-days. The designed subset — 1,000 test + 500 audit + ~2,000 jury-flagged — is ~58 hours, ~7 person-days, and it buys more: a fully-validated test split, an unbiased residual-error estimate on everything untouched, and human attention concentrated where the jury says it is needed. The remainder ships as `unvalidated` with a measured error bar, which is an honest artifact. Full manual validation would ship the same corpus six weeks later with no error bar at all, because nothing would have been sampled to estimate one from.

### Release artifact

```
11_release/v1/
├── sft_train.jsonl        messages format, curated labels
├── sft_val.jsonl
├── sft_test.jsonl         100% human-validated, group-disjoint, decontaminated
├── quarantine.jsonl       every excluded record with its defect
├── jury_report.json       panel, per-juror gold weights, bucket precision, zero-shot baseline
├── datasheet.md
├── data_statement.md
├── croissant.json
├── metrics.json           counts, α, flag rate, gold accuracy, residual error ± CI
└── MANIFEST.sha256
```

## Decisions

**The task is never reformulated.** Every juror, every question, and every training target is the set-valued task the corpus already states. *Alternatives:* recast as per-(record, tool) binary "call or not", which would have made 98,766 two-class examples and unlocked classifier-based tooling; recast as cardinality buckets. *Why:* the reformulation buys access to methods that need a fixed class space, and pays for it by measuring something the model will never be asked to do — a per-tool decision made in isolation, without the set-level interactions (`{hold_other}` means *another tool covers this*, which is a statement about the set) that the marker DSL is largely about. A jury that answers the real task needs no reformulation, and its errors are the errors that matter. *Reversible:* the binary view can be reconstructed from jury votes at any time as a diagnostic, so nothing is lost by not adopting it as the primary representation.

**An LLM jury, not Confident Learning.** *Alternatives:* Cleanlab over a proxy label space; a trained multi-label classifier; a single strong LLM as judge. *Why:* Cleanlab needs a fixed class space and this corpus has 14,411 tool names with a modal frequency of 35, so adopting it requires reshaping the task — see the decision above. A generative jury needs no class space at all: it answers the task directly, and its disagreement with the corpus is a signal in the corpus's own units. One judge would be cheaper and is rejected because a single model's agreement is indistinguishable from a single model's bias, and this corpus was already labelled by a single model. *Reversible:* yes, and cheaply — the jury is confined to `jury/`, its output is three numbers and a set per record, and Cleanlab can be added later over whatever label space the first release establishes.

**Panel diversity is a requirement, and the corpus's own labeller is excluded from it.** *Alternatives:* N samples from one model at temperature > 0; include every available model including `gemma`. *Why:* temperature sampling from one model produces correlated jurors that agree on shared errors, so cohesion stops meaning confidence. And 67.3% of the corpus was labelled by `gemma-4-31B-it` — a `gemma` juror would ratify exactly the errors this exercise exists to find. Running it as a labelled control turns that liability into a measurement of how much of the corpus is one model's opinion. *Reversible:* yes, panel config.

**Jury votes never become labels without a human.** *Alternatives:* auto-apply consensus where the jury is unanimous; auto-apply everywhere and human-check a sample. *Why:* the corpus is already two-thirds machine-labelled and has been relabelled once. Overwriting machine labels with other machine labels is the accumulation-versus-replacement distinction the model-collapse literature turns on, and replacement is the losing side of it. The opt-in `jury_consensus` tier exists for teams that need volume, kept in a separate tier with its own error bar and barred from test, so the choice is visible in the artifact instead of buried in it. *Reversible:* the tier is a flag; but data shipped as human-validated when it was not cannot be un-shipped.

**One set distance, with `δ(∅,∅) = 0`.** *Alternatives:* exact-set-match only; per-tool micro-averaging; treating the empty set as a distinct class. *Why:* exact match throws away the difference between "one tool too many" and "completely wrong", which is most of the useful gradient. The empty-set convention is load-bearing on 35.4% of the corpus. *Reversible:* no, in practice — cohesion and conflict computed under a different convention are not comparable across releases.

**Two triage axes, not one score.** *Alternatives:* a single priority number, as a Cleanlab score would give. *Why:* a unanimous jury disagreeing with the corpus is a label problem; a split jury disagreeing with the corpus is usually a guideline problem. They go to different people and produce different fixes. *Reversible:* yes.

**Bucket thresholds are provisional until the pilot measures them.** *Why:* every threshold here is currently a guess, and a guess that decides which 3,500 of 21,172 records humans look at is worth one measurement. The pilot's bucket-precision gate is the only thing standing between "the jury found the errors" and "the jury found something". *Reversible:* yes, and expected to change exactly once.

**The key pool lives in the pipeline, not in `agent-toolkit`.** *Alternatives:* add it to the library's LLM client. *Why:* the library has one specified consumer for it and growing a shared library for a single caller is how libraries acquire features nobody else wants. Cost accounting per key is a pipeline concern anyway. *Reversible:* yes — it graduates when a second consumer appears, which is the right trigger.

**Defects are quarantined, never auto-repaired.** The 48 contradictions could be resolved by preferring the assistant message; the 722 out-of-catalog labels could be truncated to the catalog. *Alternatives:* exactly that, silently. *Why:* both "fixes" are guesses about which of two disagreeing sources is right, applied at scale, invisibly. A quarantine file with 722 records is a morning's work for someone who knows the corpus and a permanent record of what was decided; an auto-repair is a data cascade with a clean-looking count. *Reversible:* re-admission is an explicit command that versions the pipeline.

**PII is replaced with stable placeholders, not deleted or hashed.** *Alternatives:* delete the span; hash it; drop the record. *Why:* the ground truth of this corpus turns on whether a required value was supplied. Deleting a phone number converts a correct call into what now looks like a correct `{hold_missing}`, silently inverting the label on ~2% of records. A stable typed placeholder preserves suppliedness and co-reference while carrying no personal data. *Reversible:* only from the vault, which never leaves the raw tier — so getting this right the first time matters.

**The test split is 100% human-validated, at any budget.** *Alternatives:* validate a sample of test; let jury consensus fill it. *Why:* every number the release reports is computed on test. A test split that is machine-labelled measures agreement with a model, not correctness, and no amount of downstream care recovers from that. It is the single most load-bearing rule here. *Reversible:* no.

**Group split on catalog fingerprint ∪ dedup cluster.** *Alternatives:* random split; split on `source_index`. *Why:* `source_index` is unique per record and provides no protection — measured, not assumed. Records sharing a tool catalog are near-variants of one scenario (largest such group: 112 records), and a random split puts variants of the same scenario on both sides, inflating every metric. *Reversible:* yes, but every metric produced before the fix would be void.

**The pipeline is DVC stages, not a service.** *Alternatives:* Airflow/Prefect; Celery jobs in the platform API; a shell script. *Why:* every stage is a pure function from artifact to artifact, which is what DVC models natively — and data lineage plus reproducibility from a commit hash is the requirement, not scheduling. *Reversible:* yes; each stage is a CLI command an orchestrator could call unchanged.

**Label Studio, not Argilla, and not the DataForce annotation service yet.** *Alternatives:* Argilla; build the platform's own UI now; Doccano; Prodigy. *Why:* Argilla has shipped no functional change in seventeen months. Building our own UI first inverts the order of risk — it spends a quarter before anyone has answered whether the *questions* are answerable. Label Studio is maintained, its dynamic-choices feature fits the per-record tool catalog precisely, and generating its XML is a file we own rather than a format we adopt. *Reversible:* yes, cheaply — Label Studio is touched only by `labelstudio/`.

**Assumption:** Label Studio Community honours `maximum_annotations` for multi-annotator overlap. The docs describe collaborative labelling as available in both editions, while review workflows and agreement analytics are Enterprise. S0 verifies this empirically; if it does not hold, overlap comes from publishing the same tasks to one project per annotator and joining on `rid`.

**Assumption:** `potion-multilingual-128M` embeds Vietnamese well enough for near-duplicate detection. Checked by a retrieval sanity test on 200 hand-paired records, with a sentence-transformer fallback.

**Assumption:** 3 characters per token for Vietnamese cost estimates. The jury stage measures actual consumption and the estimate is corrected from the first real run, not carried forward on faith.

**Assumption:** enough API keys exist across ≥3 model families to run a 3-juror sweep of ~101M input tokens within the release window. If keys are concentrated in one family, requirement 19 binds and the panel — not the requirement — is what changes.

**Assumption:** the residual-error estimate from the audit sample is reported as a property of the release and consumers are expected to read it. The alternative — refusing to ship anything unvalidated — is not on the table at 44 person-days.

**Assumption:** annotators are internal Vietnamese speakers on a self-hosted Label Studio inside the network boundary.

## Versions

| Component | Pinned | Source |
|---|---|---|
| Python (pipeline) | 3.12.14 | [endoflife.date, released 2026-08-12](https://endoflife.date/python) — 3.12 for widest library compatibility; the platform API stays on 3.14 |
| Label Studio | 1.23.0 | PyPI, 2026-03-13 (checked live) — run as the official Docker image |
| label-studio-sdk | 2.1.1 | PyPI, 2026-08-10 (checked live) |
| semhash | 0.4.1 | PyPI, 2026-01-20 (checked live) |
| model2vec | 0.9.0 | PyPI, 2026-08-12 (checked live); model `potion-multilingual-128M` |
| crowd-kit | 1.4.2 | PyPI, 2025-10-13 (checked live) — human verdicts only |
| krippendorff | 0.8.2 | PyPI, 2025-11-03 (checked live) — nominal α; set-valued α is ours |
| pandera | 0.32.1 | PyPI, 2026-06-29 (checked live) |
| DVC | 3.67.1 | PyPI, 2026-03-31 (checked live) |
| mlcroissant | 1.1.0 | PyPI, 2026-04-16 (checked live) |
| agent-toolkit | `>=0.1,<0.2`, extra `[llm]` | [spec](../agent-toolkit/spec.md) — LLM access, retry, traffic control, JSON extraction |

Dropped relative to the first draft, and worth noting because it shrinks the dependency surface: **cleanlab** (needs a fixed class space this corpus lacks), **scikit-learn** (was only there for cleanlab's cross-validated probabilities), and **snorkel** 0.10.0 (last released 2024-02-27; the marker rules are ~200 lines of plain Python and do not justify pulling torch and tensorboard).

Rejected: **Argilla** 2.8.0 — last release 2025-03-10, no functional commit since (checked on GitHub). **Great Expectations** 1.20.0 — requires `<3.14` and is heavy for artifact-shape checks; pandera covers it.

## Invariants

1. **Nothing is lost between stages.** For every stage, `output_count + quarantined + deduped_out == input_count`. *Check:* the gate runner asserts the reconciliation on every stage, not just ingest, and writes it to `metrics.json`.
2. **`rid` is stable.** Re-ingesting the same source produces byte-identical `rid` values regardless of record order. *Check:* shuffle a fixture, re-ingest, compare the `rid` set.
3. **No PII downstream of `scrub`.** No artifact in `03_scrubbed/` or later matches a literal PII pattern, and `pii_vault.jsonl` is never DVC-tracked. *Check:* a gate scanning every release-tier file; a repo test asserting the vault path appears in `.gitignore` and in no `.dvc` file.
4. **The task representation never changes.** Every juror vote, correction, and exported label is a set of names drawn from that record's catalog. *Check:* a pandera check on every artifact carrying a label, asserting `set(label) <= set(catalog names)`, applied to jury votes and corrections alike.
5. **Every juror vote is valid or an abstention.** No stored vote names an out-of-catalog tool, and no vote is a truncation of a malformed response. *Check:* validation at write time plus a test feeding malformed, prose-wrapped, over-long, and out-of-catalog responses and asserting each becomes either a clean set or an abstention.
6. **Votes are reproducible and key-independent.** Re-running the jury with a warm cache changes nothing; re-running cold at temperature 0 reproduces the votes; the same vote is produced regardless of which key served it. *Check:* two cold runs over a 20-record fixture against a recording proxy, diffed; a test that forces key rotation mid-run and diffs the votes.
7. **The panel is diverse and clean.** ≥3 jurors, ≥3 families, and no primary-panel juror from the corpus's labelling family. *Check:* the jury gate reads the panel config and fails on violation; a control juror must be explicitly tagged `control` to be admitted at all.
8. **`δ(∅,∅) = 0`.** *Check:* a property test over random set pairs asserting symmetry, `δ(A,A) = 0` including the empty case, `δ ∈ [0,1]`, and no `nan` anywhere.
9. **No jury output reaches an annotator.** No Label Studio payload contains a juror vote, consensus, cohesion, conflict, bucket, stratum, or the generator's proposed answer. *Check:* a contract test asserting the payload key set equals an explicit allowlist — an allowlist, not a denylist, so a new field cannot leak by being forgotten.
10. **Corrections stay in the catalog.** Every stored correction is a subset of that record's own catalog, or the explicit empty set. *Check:* structurally guaranteed by dynamic choices, and asserted again at pull time, because a structural guarantee in someone else's UI is not one of ours.
11. **No group spans splits.** No `group_key` appears in more than one of train/val/test. *Check:* a set-intersection assertion in the split gate.
12. **Test is fully human-validated.** Every test record has `validation.status ∈ {original, corrected}` — never `unvalidated`, never `jury_consensus`. *Check:* export gate.
13. **Label and assistant agree on the way out.** For every exported record, `meta.label` equals the parsed assistant message. *Check:* export gate — the same assertion that found the 48 defects on the way in.
14. **Releases are reproducible.** `dvc repro` from a clean checkout at a given commit reproduces every artifact's SHA-256. *Check:* CI runs it on the S0 fixture and diffs `MANIFEST.sha256`.
15. **The sampling design is reconstructible.** Every annotated record records which stratum selected it and with what probability. *Check:* the residual-error estimator refuses to run when any annotated record lacks a stratum.

## Error Behavior

Gates fail loudly and stop the DAG. A failed gate writes `data/<stage>/GATE_FAILED.json` with the assertion, the observed value, the expected value, and the offending record IDs (capped at 100), and exits non-zero so `dvc repro` halts. No stage consumes an input whose gate did not pass.

| Situation | Behavior |
|---|---|
| Source SHA-256 differs from `params.yaml` | Hard stop. A changed source is a new dataset version, decided by a human, never merged silently. |
| Defect count moves >±10% from declared | Hard stop with the delta. The declared counts are the contract with the corpus. |
| LLM unavailable during PII verification | Stage stops; already-verified spans are kept and the stage resumes from its checkpoint. A record with unverified hits never advances — failing open on PII is the one failure this pipeline will not take. |
| A juror is unreachable for a whole run | The run continues on the remaining jurors if ≥3 families remain, and records the reduced panel on every affected record. Below the diversity floor the stage stops rather than quietly producing weaker signal. |
| One API key exhausts its quota | Key quarantined for a cooldown; dispatch continues on the rest. Throughput degrades, the run does not stop. Reported per key. |
| All keys in a group exhausted | That juror is marked incomplete for the affected records; those records keep the votes they have and are re-queued for the next jury run rather than being scored on a partial panel. |
| Juror response malformed after one retry | Recorded as an abstention with the raw text retained. Never truncated into a partial set. |
| Invalid-vote rate above 5% for a juror | Jury gate fails. A juror that cannot follow the output contract is a prompt or model problem, and its votes are not usable as signal. |
| Jury token budget exhausted mid-run | Clean partial stop; cast votes retained; run status `partial`; records with fewer than 3 valid votes are excluded from triage rather than bucketed on thin evidence. |
| LLM unavailable during question generation | Per [`guided-validation`](../guided-validation/spec.md): record marked `generation_failed`, run continues, task never published without a question. |
| Label Studio unreachable on publish | Retry with backoff, 5 attempts; then fail the stage with the tasks already pushed recorded, so a resume does not duplicate. Publishing is idempotent on `rid`. |
| Response has `verdict=incorrect` with no correction | Rejected, not repaired. Returned to the queue with the reason; counted in `metrics.json`. |
| α below 0.667 at the pilot gate | Hard stop with the per-focus breakdown. The remedy is a guideline revision and a re-pilot, never lowering the threshold. |
| α above 0.95 | Warning plus a mandatory written review note in the datasheet. Not a stop. |
| `likely_label_error` precision below 0.30 at the pilot gate | Hard stop. The panel or the thresholds change before 21k records depend on them. |
| Annotator below 0.85 on gold | Their work is held pending review; already-submitted answers are re-queued for a second opinion rather than discarded. |
| Group leakage or n-gram overlap detected | Hard stop. Every metric computed on a leaked split is void, so there is nothing to salvage by continuing. |
| A record cannot be scrubbed with confidence | Quarantined to `quarantine/pii_uncertain.jsonl`, excluded from the release, counted in the datasheet. |

Two failures have no automated detector. A **plausible but wrong question** — one that reads well and asks about the wrong turn — is caught only by the flag rate, which is why 10% is a gate. And a **jury that is confidently wrong in the same direction as the corpus** produces `agreed` records that are quietly incorrect; only the uniform random audit sample can see those, which is why it is uniform and why it is never allowed to be repurposed for anything else.

## Testing Strategy

- **Contracts.** Every artifact has a pandera schema; a round-trip test writes, reads, and validates each. A schema change that is not accompanied by a stage change fails.
- **Set operations.** Property tests over random set pairs for `δ`: symmetry, identity including the empty case, range, no `nan`. Majority consensus against hand-worked vote sets, including the case where consensus differs from every individual vote. Set-valued α against a hand-computed example, plus the degenerate check that α with an identity distance equals the `krippendorff` package's nominal α on the same data.
- **Adapter.** Fixtures covering all 13 observed `meta` key-sets, each label cardinality, catalog sizes 0 / 1 / 8 / 20, and malformed `TOOLS:` blocks. One test asserts marker tokens survive parsing **verbatim** — a parser that strips them would pass every other test while destroying the annotator's only evidence.
- **Source-integrity gate.** A fixture containing one instance of each defect class, asserting each lands in the right quarantine file with the right label, and that the main path count drops by exactly four.
- **PII.** A hand-built Vietnamese fixture of spoken phone numbers, spoken emails, national IDs, prices, dates, and order references — asserting recall on the first three and *no* replacement on the last three. Placeholder stability is tested by a record mentioning the same number twice. A test asserts the vault path is absent from `dvc.yaml` and present in `.gitignore`.
- **Jury.** Stubbed jurors returning: a clean array, a fenced array, prose-wrapped JSON, an out-of-catalog name, a non-array, and empty — asserting each becomes a valid set or a clean abstention. Panel diversity gate against a config with three models from one family. Cache determinism across two runs. Key-pool failover: a stub returning 429 on one key, asserting the run completes on the rest and the votes are identical to a single-key run. Cost accounting against a fake tokenizer.
- **Triage.** Bucket assignment over hand-built (cohesion, conflict) grids including the boundaries; audit sample-size formula against worked values (`p=0.05, e=0.02 → 457`); a test asserting records with fewer than 3 valid votes are excluded rather than bucketed.
- **Dedup and grouping.** Known duplicate pairs from the corpus; assertion that `source_index` is rejected as a group key and that the largest catalog group (112 records) stays intact through splitting.
- **Label Studio integration.** The generated config validated against a live Label Studio instance in CI via testcontainers — creating the project, pushing three tasks, and pulling back a submitted annotation. The invariant-9 allowlist test runs on the built payload without needing the server.
- **Split and decontamination.** A fixture with a deliberately planted group spanning what would be a random split, asserting the gate catches it; a planted 13-gram overlap, asserting the same.
- **End-to-end (S0 as a test).** The 50-record smoke run *is* the integration test: `dvc repro` from raw to release against stubbed jurors, a stubbed generator LLM, and a containerized Label Studio, asserting a byte-identical `MANIFEST.sha256` on a second run. This passing is the definition of the pipeline being done.
- **Reproducibility.** CI re-runs S0 from a clean checkout and diffs the manifest, which is invariant 14.

## Out of Scope

- **Image, audio, and video.** Explicitly deferred; the platform spec's image controls go with them.
- **Model training and evaluation.** This pipeline produces a dataset, a metric definition, and a zero-shot jury baseline. Running the fine-tune, the learning curve's training runs, and any eval harness belong to a separate spec.
- **Confident Learning and classifier-based label auditing.** Deferred by decision, not dropped — revisit after the first release establishes a label space and the jury's bucket precision is known.
- **Synthetic data generation.** The corpus is already two-thirds machine-labelled; generating more before the existing labels are validated is the model-collapse failure the handbook describes. Revisit after the first release measures the residual error rate, and only for the long-tail strata.
- **Active learning loops.** The jury is a one-shot ranking per release, not a model that retrains as annotations arrive.
- **Fine-tuning a juror.** Jurors are off-the-shelf models behind API keys.
- **The DataForce annotation service.** Deferred, not cancelled — the pilot decides whether it is worth building, and [`dataforce-platform`](../dataforce-platform/spec.md) remains the spec for it.
- **Automatic write-back to the source file.** Export produces an artifact; putting it anywhere is a human step.
- **Multi-language.** Vietnamese only, for the corpus, the questions, and the PII detectors.
- **Cross-border transfer review.** Real under Data Law 60/2024 and newly sharper here, because the jury sends conversation transcripts to several external LLM endpoints. It is a legal review of where the data and those endpoints sit, not a pipeline stage, and it must happen before the first jury run against any offshore endpoint — not before the release.

---

**Grounded in:** measurements over the full corpus (counts in Context are reproducible with the pipeline's `dataforce profile` command) · [Label Studio](https://labelstud.io/guide/setup) · [SemHash](https://github.com/MinishLab/semhash) · [crowd-kit](https://github.com/Toloka/crowd-kit) · [DVC](https://dvc.org) · [Croissant](https://github.com/mlcommons/croissant) · Gebru et al., *Datasheets for Datasets* (CACM 2021) · Bender & Friedman, *Data Statements* (TACL 2018) · Northcutt et al., *Pervasive Label Errors* (NeurIPS 2021) · Sambasivan et al., *Data Cascades* (CHI 2021) · Shumailov et al., *Model collapse* (Nature 2024) · Zheng et al., *Judging LLM-as-a-Judge* (NeurIPS 2023) · Penedo et al., *FineWeb* (arXiv:2406.17557)
