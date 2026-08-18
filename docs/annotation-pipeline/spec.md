# Annotation Pipeline — Gated Stages for Any SFT Dataset

## What

A reproducible pipeline that turns a raw corpus into a versioned, documented, training-ready dataset. It is fifteen DVC stages, each producing a checksummed artifact and each guarded by a machine-checked **gate** that fails the run rather than passing bad data downstream. Several models answer the dataset's own task first, and their disagreement decides which records a human looks at.

Nothing in this document is specific to one dataset, one task, or one modality. A run is **one modality × one profile**:

```
dataforce run --modality text --profile tool_decision
```

The **modality** knows how to load content, embed it for duplicate detection, and find personal data in it. The **profile** knows what an answer is, how to compare two answers, how to ask a human about a record, and how to export a training example. Everything else — the fifteen stages, the gates, the invariants, the jury, the triage, the agreement statistics, the release artifact — is written once, here.

The first modality is `text` and the first profile is `tool_decision`, specified in [`profiles/tool-decision`](../profiles/tool-decision/spec.md). Image, audio, and video are **out of scope as implementations** and **in scope as a seam**: this document specifies the boundary they plug into and one structural decision that must be made now because retrofitting it later would touch every stage.

## Context

### Why this pipeline exists at all

Four findings decide the architecture, and each stage below exists to make one of them visible early and cheap:

| Finding | Source | What it forces |
|---|---|---|
| Aggressive filtering beats collecting more — 10× token efficiency | FineWeb-Edu | Filtering and dedup are stages, not scripts |
| Weak supervision is the largest speed lever — 2.8× | Snorkel, VLDB 2017 | Models triage before humans annotate |
| Even curated benchmarks carry ≥3.3% label errors | Northcutt et al., NeurIPS 2021 | Existing labels are evidence, not truth |
| 92% of ML teams hit a data cascade — an upstream data problem amplifying downstream | Sambasivan et al., CHI 2021 | Every stage has a gate that stops the run |

### The three-piece interface

The entire jury → triage → agreement → adjudication machinery depends on exactly three things from a profile. Supply them and everything downstream works unchanged:

| Task | Answer type | δ — distance between two answers | Consensus over several answers |
|---|---|---|---|
| Tool / function selection | set of names | `1 − |A∩B| / |A∪B|` | included by a strict majority |
| Single-label classification | one class | `0` if equal else `1` | the mode |
| Multi-label classification | set of labels | `1 − |A∩B| / |A∪B|` | included by a strict majority |
| Span extraction (NER) | list of spans | `1 − span-F1` | spans a majority marked |
| Ranking / preference | an ordering | normalised Kendall τ distance | Borda count |
| Free-text generation | a string | `1 − similarity` | **none — abstains** |

Free-text generation is the honest exception. There is no defensible consensus over generated strings, so a profile may declare `consensus = None`, and then the jury ranks records by disagreement but proposes no answer. Triage still works: cohesion is computable, `corpus_conflict` is computable, and the four buckets still sort. Only the optional `jury_consensus` tier is unavailable, which is correct — a tier that shipped machine-written prose as a label would be exactly the failure the model-collapse literature describes.

### What is borrowed

| Need | Use | Version checked |
|---|---|---|
| Annotation UI, users, task serving, locking, multi-annotator | **Label Studio** Community (Docker) + `label-studio-sdk` | 1.23.0 (2026-03-13); SDK 2.1.1 (2026-08-10) |
| Near-duplicate detection over embeddings | **SemHash** | 0.4.1 (2026-01-20) |
| Annotator verdict aggregation (Dawid-Skene, MACE) | **crowd-kit** | 1.4.2 (2025-10-13) |
| Krippendorff's α, nominal | **krippendorff** | 0.8.2 (2025-11-03) |
| Artifact schema validation | **pandera** | 0.32.1 (2026-06-29) |
| Data versioning and the stage DAG | **DVC** | 3.67.1 (2026-03-31) |
| Dataset metadata | **mlcroissant** | 1.1.0 (2026-04-16) |
| Streaming JSON, atomic I/O, hashing, templating, all LLM access | **[`agent-toolkit`](../agent-toolkit/spec.md)** 0.1.0 | released, `giangchicken/agent-toolkit` |

**Argilla is rejected.** Last release 2.8.0, 2025-03-10; every commit to `main` since is a README or project-status edit. **Cleanlab is deferred** — Confident Learning needs a fixed class space, which some profiles have and others do not, so it belongs to a profile that wants it rather than to this core.

### What `agent-toolkit` already provides

Normative: a module that re-implements a row here is a defect, and review rejects it.

| The pipeline needs | The call |
|---|---|
| Stream a large JSON array without loading it | `file_utils.iter_json_array_file(path)` |
| A stable record id | `string_utils.compute_hash(text, "sha256")[:16]` |
| Read and write every artifact, atomically | `file_utils.read_jsonlines` / `write_jsonlines` / `read_json` / `write_json` |
| Read declarative config and prompt files | `file_utils.read_yaml`, `read_txt` |
| Fill a prompt template — `{{placeholder}}` | `string_utils.slot_filling(text, {...})` |
| One LLM call, retried and rate-limited | `llm.complete(prompt, model=, api_key=, base_url=)` |
| A call whose answer must satisfy a JSON Schema | `llm.complete_structured(prompt, schema, mode=)` → `(value, ValidationInfo)` |
| Keep the model's reasoning with its answer | `ValidationInfo.reasoning` |
| Model family, for panel diversity | `llm.model_family(name)` |
| Prompt-token estimate | `llm.count_tokens(messages, model)` |
| Concurrency and requests-per-minute per endpoint | `llm.get_traffic_controller(name, ...)` |
| One exception type around any provider failure | `llm.exceptions.LLMError` and subclasses |
| Tell "key out of quota" from "slow down" | `ProviderQuotaExceededError` ⊂ `LLMRateLimitError` |
| A logger that configures nothing | `get_logger(__name__)` |

Consequences: there is **no `io.py`** (`file_utils` is the I/O layer, already atomic), **no JSON-repair helper** (`complete_structured` does it and reports `repaired`), and **no answer-validation code in the jury** (the profile's JSON Schema does it at the library boundary).

Gaps measured from the shipped code, each with its consequence here:

| Gap | Consequence |
|---|---|
| `Completion` is `(content, reasoning)` — the response's `usage` is **discarded** | Every token figure is a `count_tokens` *estimate*; budgets are enforced on estimates and reported as such. Filed against the library. |
| `LLMRateLimitError.retry_after` is never populated | Key cooldown is a declared constant, never a server hint. |
| `set_config_resolver` installs **one process-global** resolver keyed by model name | A key pool rotating credentials per call passes `api_key=`/`base_url=` explicitly, which the library documents as winning over the resolver. No resolver is installed. |
| `get_traffic_controller` memoizes per (loop, name) and **ignores later callers' limits** | Controllers are constructed in exactly one place, before dispatch. |
| `llm.stream`, `complete_with_tools`, `json_utils.loads_repair`/`deep_merge`/`jsonpath_get` are 0.2 | No stage may assume them. |

Pinned as a git ref, the library not being on any registry:

```
agent-toolkit[llm] @ git+https://github.com/giangchicken/agent-toolkit.git@v0.1.0
```

### Relationship to the other specs

- **[`profiles/tool-decision`](../profiles/tool-decision/spec.md)** — the first profile. Holds its corpus measurements, its marker DSL, its Vietnamese PII detectors, its jury panel, and its thresholds.
- **[`guided-validation`](../guided-validation/spec.md)** — the question model, focus rules, glossary, correction shape, and flag taxonomy. Its invariant 1 (the generator's answer never reaches the annotator) is generalised here into requirement 33.
- **[`dataforce-platform`](../dataforce-platform/spec.md)** — deferred behind a Label Studio v0 until the first profile's pilot gate passes. Its image controls are deferred with the image modality.
- **[`agent-toolkit`](../agent-toolkit/spec.md)** — built and released. Its own spec still lists 0.2 symbols and claims a package registry; it needs a sync pass in its repository.

## Requirements

### The profile and modality contracts

1. A **modality** supplies exactly four things: a content loader (raw → typed parts), an embedder (record → vector) for duplicate detection, a list of privacy detectors, and the annotation-UI control that *displays* a record. Nothing else.
2. A **profile** supplies exactly seven things: a source adapter (raw → canonical record), an answer JSON Schema, `delta`, `consensus`, a map of validity checks, a question template set, and an exporter. It declares which modality it composes with.
3. The annotation-UI config is **composed, not owned**: the modality contributes the control that displays the content, the profile contributes the control that captures the answer. Neither may emit the other's half. This split is the reason a new modality does not multiply the profiles that already exist.
4. `delta` must be a metric on the profile's answer type: `δ(a,a) = 0`, `δ(a,b) = δ(b,a)`, `δ ∈ [0,1]`, and never `NaN` — including on whatever the profile's empty or null answer is. A profile whose `delta` fails any of these is rejected at registration, not at the jury stage.
5. `consensus` is deterministic given a list of answers, and may return `None` to declare that the profile has no defensible consensus. A profile returning `None` is barred from the optional consensus tier of requirement 34 and is otherwise fully supported.
6. Every profile passes a shared **conformance suite** before it can be named on a run: `delta` is checked as a metric over generated answer pairs, `consensus` for determinism and for agreeing with `delta` on unanimous input, the answer schema for round-tripping, the adapter for preserving every field it does not own, and the exporter for reproducing the adapter's answer. A profile that does not pass cannot be selected. This suite is what makes "generic" a checked claim rather than a hope.
7. Profiles and modalities are resolved from a registry by name, and the resolved pair, with each one's version, is recorded on every artifact and in the release manifest. A run cannot silently change which code produced a dataset.

### The modality seam

8. A record's content is an **ordered list of typed parts**, never a bare string. Each part carries its `kind`, its role, and either inline text or a reference. Text profiles see a list of text parts; nothing about the shape changes when a part becomes audio.
9. **Non-text media is held by reference and checksum, never inlined in an artifact**: `{"kind": "audio", "uri": "media/ab/abc123.wav", "sha256": "…", "duration_s": 12.4}`. Artifacts stay diffable and streamable at any corpus size, which is the difference between a 126 MiB text corpus and terabytes of video. This is the one modality decision that must be made before the first line of code, because retrofitting it would touch all fifteen stages.
10. `rid` is derived from the content parts' digests, not from raw bytes: text parts contribute their text, media parts contribute their `sha256`. So the identity of a record is modality-independent and stable across re-ingests and re-ordering.
11. Privacy detection is a modality concern with a **uniform result shape** — a list of typed spans over a named part — so the redaction stage, its report, its vault, and its gate are written once. What a "span" indexes is the modality's business: character offsets in text, a time range in audio, a box in a frame.
12. A modality that cannot yet redact a part **fails closed**: the record is quarantined, never advanced. Failing open on personal data is the one failure this pipeline will not take, and a new modality inherits that rather than choosing it.

### Ingest and source integrity

**What `quarantine_invalid` is for.** Some records cannot be used and you can prove it by counting: the label contradicts the training target, the answer names something the record never offered, the answer space is empty. No person decides any of that — if telling right from wrong needs judgment, it is not this stage's business, it is an annotation task, and it belongs in `human_review` with the jury and the annotators.

Running it first is what makes the rest affordable. In the first profile it moves **1,563 of 21,172 records — 7.4%** out of the main path in a few seconds of arithmetic. Left in, those records would have consumed 7.4% of the jury's ~121M estimated tokens, taken annotator hours, and then taught the model something false. Nothing is deleted: each goes to `quarantine/invalid/<check>.jsonl` naming the check it failed, and can be re-admitted by an explicit command once the cause is fixed.

13. Ingest streams the source via `file_utils.iter_json_array_file` or the modality's loader. A source file is never loaded whole.
14. Ingest records provenance per record: source file SHA-256, byte offset, the raw record verbatim, the modality and profile names with versions, and the ingest timestamp. Nothing is dropped; unparsable records are carried with `parse_status = "unparsed"` and their raw text.
15. The **source-integrity gate** runs the profile's validity checks, and each failure writes the record to `data/quarantine/invalid/<check>.jsonl` naming the check it failed, and removes it from the main path. Records are never silently deleted and never silently kept.
16. Expected invalid counts per check are declared in `params.yaml`, and a count moving more than ±10% fails the gate. The source changed, and that must be a decision rather than a surprise. Re-admission is an explicit `dataforce requeue --check <name>` that versions the pipeline.
17. Every artifact is written with `file_utils.write_jsonlines` or `write_json` and read with the matching reader. Both are atomic and create parent directories, so an interrupted stage leaves the previous artifact intact. No stage opens an artifact file directly.

### Privacy

18. `pii_check` detects in two layers with separate jobs: the modality's detectors maximise recall and are allowed to be noisy, and an LLM pass over a bounded window, via `llm.complete_structured` against a fixed classification schema, sets precision. It **always** writes a findings artifact — every candidate span with its class, its surrounding window, and the verifier's verdict — which is what a person reads before deciding anything. A verification response that fails its schema leaves the span **unverified, not negative**.
19. Rewriting content is controlled by one parameter, `enable_redact`, **false by default**. False: the stage reports and leaves content untouched. True: verified spans are replaced with **stable typed placeholders** scoped per record (`<PHONE_1>`, `<EMAIL_1>`), so a value referenced twice stays co-referent — and never deleted, because deleting a value can change the ground truth of the very judgment the record encodes.
20. The gate is what makes the default safe. With redaction off, release-tier artifacts still match literal personal-data patterns, so the scan below fails and nothing ships. Turning it on is a change to `params.yaml`, which is committed and a declared DVC dependency — so the decision is attributable and `dvc repro` stays reproducible, without a bespoke approval format.
21. The placeholder-to-original mapping is written to `data/raw/pii_vault.jsonl`. `data/raw/` is **not DVC-tracked and not committed**: the source file's identity is a SHA-256 in `params.yaml`, and the vault appears in `.gitignore`, in no `.dvc` file, and in no `dvc.yaml` output list. Every other directory under `data/` is DVC-tracked. The findings and redaction reports record, per class, the counts and a sample of 20 *placeholders in context* — never original values — and the gate fails if any release-tier artifact matches a literal personal-data pattern.

### Duplicates and grouping

22. Exact duplicates are removed on `compute_hash` of the content digest, keeping the record with the richer metadata.
23. Near-duplicates are found with SemHash over the modality's embeddings. Cluster members are **not deleted**: they get a shared `dup_cluster_id` and one is marked `is_representative`. Deletion happens at export from an explicit filter, so the decision is reversible and recorded.
24. Every record gets a `group_key` from the profile, unioned with its `dup_cluster_id`. A field that is unique per record is not a group key, and the profile is responsible for saying so with a measurement rather than an assumption.

### The jury

25. A **jury** of independent models answers the dataset's own task per record, via `llm.complete_structured(prompt, profile.answer_schema)`. The schema is the answer constraint, enforced inside the library: a non-conforming answer means `ValidationInfo.ok is False` and the returned value is `None`. The pipeline does not re-validate; it checks that the schema came from the right profile.
26. A non-conforming answer is retried **once**, then recorded as an abstention carrying `ValidationInfo.raw`, `.error`, `.repaired`, and `.strategy`. It is never truncated into a partial answer. `repaired` is reported per juror as a model-quality signal distinct from `ok`.
27. Every vote stores `ValidationInfo.reasoning` when the juror emitted any. It is the only record of *why* a juror answered as it did, it is unrecoverable afterwards, and it is what an adjudicator reads. It never reaches an annotator.
28. Jurors are called with `mode="prompt"`. Under `"auto"`, two jurors on endpoints that differ in `response_format` support get different constraint mechanisms, and cohesion across them is not a meaningful number. Validation is identical in all modes, so asking plainly is what keeps jurors comparable.
29. The panel must be **family-diverse**: at least three jurors over at least three distinct `llm.model_family` values, none of them `"unknown"` — the function collapses every unrecognised name to it, so a panel containing one is not proved diverse, it is unmeasured. Repeated sampling of one model at temperature > 0 is not a panel.
30. No juror may come from a model family that produced the corpus's existing labels, where the profile reports one. Such a juror measures lineage, not correctness. It may run as an explicitly tagged **control**, whose only output is an estimate of how much of the corpus is that family's opinion.
31. Votes are cast at temperature 0 and cached on `(rid, model, prompt_version)`. The cache key excludes the API key: which key served a call must not change the vote.
32. Dispatch runs over a **key pool**, each entry with its own request and estimated-token budget, passing credentials explicitly per call, backing off per key on `LLMRateLimitError`, quarantining a key on `ProviderQuotaExceededError` for a declared cooldown, and continuing on the rest. One `TrafficController` per key group, all constructed before dispatch. `LLMAuthenticationError` and `LLMConfigError` stop the run instead — a bad key is a configuration defect, and treating it as exhaustion would hide it behind degraded throughput.
33. **No model output ever reaches an annotator, in any field** — not a vote, not a reasoning trace, not consensus, cohesion, conflict, bucket, stratum, nor the generator's proposed answer. All of it stays in the pipeline and is joined back on `rid` after responses are pulled. Showing an annotator what three models answered converts an independent judgment into a ratification.
34. **No jury output becomes a training label without human confirmation.** The jury selects and ranks; it does not relabel. Optionally and explicitly, the unvalidated remainder may carry consensus as a separate tier — `validation.status = "jury_consensus"`, permanently barred from test, with its own error bar measured against the audit sample — opt-in per release, off by default, and unavailable to profiles whose `consensus` is `None`.
35. Per record the jury stores every vote, the consensus, the plurality answer, an `exact_unanimity` flag, `cohesion = 1 − mean pairwise δ`, and `corpus_conflict = δ(consensus, existing_label)`.
36. Juror weights are calibrated on the gold set as mean per-answer score against human-validated labels, reported per juror. A juror below a declared floor is dropped for that release and the drop is recorded.
37. The jury runs in **staged escalation**: a minimum panel over the corpus, then an expanded panel only on records showing conflict or low cohesion. Estimated cost is reported before starting and the estimate is a hard ceiling, stopping cleanly with a partial result. Because the library discards `usage`, the ceiling is enforced on `count_tokens` estimates and every token figure is labelled "estimated".
38. The jury's consensus score on the human-validated test split, and each juror's individually, is reported in `metrics.json`. It is the zero-shot baseline the fine-tune must beat, and it comes free with the triage pass.

### Triage

39. Records are bucketed on two axes — how much the jury agreed with itself, and how much it agreed with the existing label:

| | Jury agrees with itself | Jury split |
|---|---|---|
| **Agrees with label** | `agreed` — audit sample only | `ambiguous_agreed` — guideline review candidate |
| **Disagrees with label** | `likely_label_error` — top of queue | `hard_record` — expert plus guideline fix |

40. Two axes, not one score, because a confidently unanimous jury disagreeing with the label is a **label** problem while a split jury disagreeing with the label is usually a **guideline** problem. They need different people and produce different fixes.
41. Bucket thresholds live in `params.yaml` and are **provisional until a pilot measures them**. The pilot reports each bucket's precision against human verdicts, and thresholds get exactly one re-tuning pass. A bucket whose precision the pilot cannot establish gets no quota at scale.
42. The queue is filled from declared strata with declared quotas, always including a **uniform random audit sample** whose only purpose is an unbiased residual-error estimate, and the entire test split. Every record records which stratum selected it and with what probability, so the sampling design is reconstructible.
43. The audit sample is sized from the target confidence interval, not chosen by feel: `n = z²·p(1−p)/e²`. If the observed rate exceeds the assumed `p`, the stage recomputes `n` and requests more.
44. Records with fewer than the minimum number of valid votes are excluded from triage rather than bucketed on thin evidence.

### Annotation

45. Question generation follows [`guided-validation`](../guided-validation/spec.md): focus chosen by rule, batch pre-generation, token budget as a hard ceiling, idempotence on `(rid, prompt_version, model)`. Prompts are files read with `read_txt` and filled with `slot_filling`; output comes from `complete_structured`, and "schema-valid ≥ 98%" is measured from `ValidationInfo.ok`.
46. Publishing creates a Label Studio project from a **generated** labeling config, composed per requirement 3. The answer control is constrained to the profile's answer space by construction wherever the UI can express it, and asserted again at pull time, because a structural guarantee in someone else's UI is not one of ours.
47. All content and glossary HTML is built by the pipeline and **escaped**; corpus text is never interpolated into markup unescaped.
48. The published payload's key set must equal an explicit **allowlist** — an allowlist, not a denylist, so a new field cannot leak by being forgotten.
49. Overlap comes from project membership: a pilot runs one project with every annotator assigned and `maximum_annotations` set to the annotator count; at scale the flagged and audit strata keep overlap 2 and the remainder runs at overlap 1.
50. A gold set of ≥50 expert-labelled records is mixed into every project as ordinary tasks, visually indistinguishable, used both to score each annotator continuously and to calibrate juror weights.
51. Pulling normalizes responses and **rejects, rather than repairs**, any response marked incorrect that carries no correction. Rejected responses return to the queue with the reason attached; this is enforced in the pipeline because Label Studio's conditional validation cannot be relied on.

### Aggregation, adjudication, curation

52. Krippendorff's α on the **verdict** (nominal) is computed across all overlapped records, per question focus and overall, with the `krippendorff` package.
53. Agreement on **corrections** is computed as α with the profile's `delta`, implemented here because the library covers only nominal, ordinal, interval, and ratio scales. Its nominal degenerate case is tested against the library's output.
54. Where overlap ≥ 2, verdicts are aggregated with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote. Corrections are aggregated with the profile's `consensus`.
55. Disagreements, and records below an aggregated-confidence threshold, go to a second **adjudication** project showing both answers and both notes, resolved by a reviewer who produced neither. Label Studio Community has no review workflow; this is that workflow.
56. Curation records for every record whether its label is `original`, `corrected`, `jury_consensus`, or `unvalidated`, with the validator and the decision date.

### Split, export, document

57. Splitting is **group-based on `group_key`**, never random. A group is wholly in one split, and the same holds for any training subsample.
58. The test split is **100% human-validated**. A record that has not been annotated cannot enter test at any budget, and `jury_consensus` records are barred permanently.
59. Decontamination verifies zero n-gram overlap between test and train, and zero shared `group_key`. Either fails the gate.
60. Export emits the profile's training format. Every exported record carries provenance: source SHA-256, pipeline version, modality and profile versions, `agent-toolkit` version, validation status, validator, dedup cluster, split, stratum, and the panel version where the jury touched it.
61. The release is a DVC-tracked directory with a manifest listing every file's SHA-256, reproducible from one git commit plus `dvc repro`.
62. Each release ships a **datasheet** (Gebru et al.), a **data statement** (Bender & Friedman), and a **Croissant** file validated by `mlcroissant`. The datasheet states the machine-labelled share explicitly and names the jury panel with each juror's family and gold-calibrated weight, because which records humans looked at is part of how the dataset was made. Documentation is a gated stage; a missing required field fails the release.

### Proving it works before scaling

63. Every dataset climbs three rungs with exit gates, and the numbers on each rung are the profile's: a **smoke** run small enough to finish in one sitting, proving the plumbing; a **pilot** proving the instruments — is the question answerable, is the guideline right, do two people agree, and does each triage bucket predict what humans actually find; then **scale**, which produces the release. You do not climb without passing.
64. The pilot gate requires all of: α on verdict ≥ 0.667 (below it the guideline is broken, not the annotators); α ≤ 0.95 or an investigation (near-perfect agreement on a subtle task means the questions dodge the hard cases); question flag rate ≤ 10%; per-annotator gold accuracy ≥ 0.85; and `likely_label_error` bucket precision above a declared floor — if the jury's flags are mostly wrong it is sending humans on a walk, and the panel changes before the full corpus depends on it.
65. Scale deliberately annotates a **designed subset** rather than everything: the full test split, the audit sample, and the jury-flagged strata. The remainder ships as `unvalidated` with a measured error bar, which is an honest artifact — full manual validation ships the same corpus much later with no error bar at all, because nothing was sampled to estimate one from.

## Design

### Stage graph

Fifteen DVC stages: declared inputs, declared outputs, a gate. `dvc repro` runs only what changed.

| # | Phase | Stage | What it is for | Output | Gate |
|---|---|---|---|---|---|
| 0 | prepare | `load` | Read the source in, one record at a time, keeping where each came from | `interim/1_prepared/loaded.jsonl` | parsed + unparsed == source count; source SHA-256 matches params |
| 1 | prepare | `quarantine_invalid` | Move the records that cannot be used out of the main path, before anything expensive touches them | `interim/1_prepared/usable.jsonl`, `quarantine/` | invalid counts within ±10% of declared |
| 2 | prepare | `pii_check` | Find personal data, report it, and replace it if `enable_redact` says so | `interim/1_prepared/pii_findings.jsonl`, `redacted.jsonl` | every high-recall hit is verified; zero literal personal-data matches downstream |
| 3 | find_duplicates | `embed` | Turn each record into a vector so near-duplicates can be found | `interim/2_deduped/embeddings.npy` | row count matches records |
| 4 | find_duplicates | `dedup` | Group records that say the same thing, so variants of one scenario cannot straddle a split | `interim/2_deduped/records.jsonl`, `clusters.jsonl` | exact dups 0; cluster report emitted |
| 5 | ai_review | `jury` | Have several models answer the task independently, so their disagreement can be measured | `interim/3_reviewed_ai/votes.jsonl`, `consensus.jsonl` | ≥3 families, none `unknown`; no corpus-family juror; estimated tokens ≤ budget; invalid-vote rate ≤ 5% |
| 6 | ai_review | `rank_for_review` | Decide which records a human should look at, and why | `interim/3_reviewed_ai/queue.jsonl` | every stratum met its quota; audit `n` ≥ computed |
| 7 | human_review | `generate_questions` | Turn each queued record into one focused, answerable question | `interim/4_reviewed_human/questions.jsonl` | schema-valid ≥ 98%; estimated tokens ≤ budget |
| 8 | human_review | `publish` | Put the questions in front of annotators, carrying nothing a model produced | project + `published.jsonl` | payload key set equals the allowlist |
| 9 | human_review | `pull` | Collect the answers and normalize them | `interim/4_reviewed_human/responses.jsonl` | every incorrect verdict has a correction |
| 10 | human_review | `aggregate` | Combine two annotators into one verdict, weighted by how reliable each has been | `interim/4_reviewed_human/aggregated.jsonl` | α ≥ 0.667; flag ≤ 10%; gold ≥ 0.85 |
| 11 | human_review | `curate` | Apply the accepted corrections and record who decided what | `interim/4_reviewed_human/curated.jsonl` | every correction inside the profile's answer space |
| 12 | release | `split` | Divide into train / validation / test so no scenario appears on both sides | `processed/{train,val,test}.jsonl` | zero group leakage; zero n-gram overlap |
| 13 | release | `export` | Write the training files in the shape a trainer expects | `release/v1/*.jsonl` | test 100% human-validated; counts reconcile |
| 14 | release | `document` | Write down what this dataset is made of, so a consumer can judge it | `release/v1/{datasheet.md,croissant.json}` | all required fields present; Croissant validates |

Stages 8–10 loop: publish → annotate → pull → aggregate → adjudicate → publish again. Stage 5 re-runs when the panel changes, and its cache makes an unchanged juror free. `embed` precedes `dedup` because `dedup` consumes the embeddings.

A stage name is a promise about what the stage does to the data, and the table above carries the purpose in a column rather than leaving it to be inferred from the name. `quarantine_invalid` names the action and its object, and the action is true: `remove_invalid` was rejected because nothing is removed — every excluded record is kept under `quarantine/invalid/` and can be re-admitted. `pii_check` names what it always does, with rewriting behind a parameter rather than behind a second stage; `rank_for_review` names what the ranking is *for*; `generate_questions` names what is generated. `validate`, `scrub`, `defect`, `find_problems`, and `triage` were rejected for the opposite failure: each needed a glossary, and none of them said whether the stage changes the data.

### Repository layout

```
dataforce/
├── pyproject.toml   uv.lock   Makefile   README.md   .gitignore
├── dvc.yaml   dvc.lock   params.yaml
│
├── src/dataforce/
│   ├── shared/                  used by everything dataforce ever does
│   │   ├── schemas/             pandera + pydantic, one file per artifact
│   │   ├── record.py            canonical record + typed content parts
│   │   ├── agreement.py         α over any δ, cohesion, plurality
│   │   └── gates/runner.py      engine only — no thresholds live here
│   │
│   ├── modalities/              ← axis 1: how content is read
│   │   ├── base.py              Modality protocol: 4 methods, nothing more
│   │   ├── registry.py
│   │   └── text/                loader · embedder · privacy · display control
│   │
│   ├── profiles/                ← axis 2: what an answer is
│   │   ├── base.py              Profile protocol: 7 members, nothing more
│   │   ├── registry.py
│   │   ├── conformance.py       the suite every profile must pass
│   │   └── tool_decision/       adapter · schema · δ · consensus · checks
│   │                            · questions · answer control · exporter
│   │
│   ├── pipeline/                ← the fifteen stages, written once
│   │   ├── prepare/             load.py  quarantine_invalid.py  pii_check.py
│   │   ├── find_duplicates/     embed.py  dedup.py
│   │   ├── ai_review/           jury.py  rank_for_review.py
│   │   │   └── lib/{panel,keypool,vote,consensus,escalate,buckets,strata,sampling}.py
│   │   ├── human_review/        generate_questions.py publish.py pull.py aggregate.py curate.py
│   │   │   ├── labelstudio/{config,client}.py
│   │   │   └── lib/{questions,alpha,gold,adjudicate}.py
│   │   └── release/             split.py  export.py  document.py
│   │       └── lib/{decontaminate,datasheet,croissant,manifest}.py
│   │
│   └── cli.py                   dataforce run --modality M --profile P
│                                the only place logging handlers are configured
│
├── config/                      policy humans edit; never imported as Python
│   ├── gates.yaml   panel.yaml
│   └── prompts/  templates/
│
├── data/
│   ├── raw/                     PRIVACY TIER — NOT DVC-tracked, never committed
│   │   ├── media/               content-addressed, sharded by digest prefix
│   │   └── pii_vault.jsonl
│   ├── interim/{1_prepared,2_deduped,3_reviewed_ai,4_reviewed_human}/
│   ├── processed/   release/v1/   quarantine/{invalid,pii,human_review}/
│
├── tests/{unit,integration,e2e,conformance,fixtures}/
├── deploy/                      docker-compose Label Studio, CI config
└── docs/
```

Nothing under `pipeline/` imports a concrete modality or profile — both arrive through their registries. That is the property the conformance suite and requirement 7 exist to keep true, and it is what a new modality has to satisfy rather than negotiate.

### The two contracts

```python
class Modality(Protocol):
    name: str
    version: str
    def load(self, raw: Any) -> list[Part]: ...
    def embed(self, parts: list[Part]) -> Sequence[float]: ...
    def privacy_detectors(self) -> list[Detector]: ...     # → list[Span] per part
    def display_control(self, record: Record) -> UIControl: ...
```

```python
class Profile(Protocol):
    name: str
    version: str
    modality: str
    answer_schema: dict[str, Any]                          # JSON Schema for one answer
    def adapt(self, raw: Any, parts: list[Part]) -> Record: ...
    def delta(self, a: Answer, b: Answer) -> float: ...
    def consensus(self, answers: list[Answer]) -> Answer | None: ...
    def validity_checks(self) -> dict[str, Callable[[Record], bool]]: ...
    def question(self, record: Record, focus: str) -> str: ...
    def answer_control(self, record: Record) -> UIControl: ...
    def group_key(self, record: Record) -> str: ...
    def export(self, record: Record) -> dict[str, Any]: ...
```

`answer_schema` may be built per record — a profile whose answer space depends on the record (a catalog, a candidate list) returns a schema closed over that record. The jury passes it straight to `complete_structured`, which is why answer-space validation is not pipeline code.

### Canonical record

One shape flows through every stage; each stage adds fields and removes none.

```jsonc
{
  "rid": "9f2c…",
  "source":   { "file_sha256": "…", "offset": 1043, "ingested_at": "2026-08-18T…" },
  "producer": { "modality": "text@1", "profile": "tool_decision@1" },

  "content": [
    { "kind": "text",  "role": "system", "text": "…" },
    { "kind": "text",  "role": "user",   "text": "…" }
    // a voice profile would add, with no other change to any stage:
    // { "kind": "audio", "role": "user", "uri": "media/ab/abc123.wav",
    //   "sha256": "abc123…", "duration_s": 12.4, "transcript_part": 1 }
  ],
  "answer_space": { "…": "profile-defined; a catalog, a class list, or absent" },
  "label": "…",                        // the profile's answer type
  "meta": { "…": "verbatim from source" },

  "parse_status": "ok",
  "invalid": [],
  "privacy": { "spans_replaced": 2, "classes": ["PHONE", "EMAIL"] },
  "dup_cluster_id": "c_0331", "is_representative": true,
  "group_key": "g_7a1e…",

  "jury": {
    "panel_version": 2, "prompt_version": "jury_vote.v1",
    "votes": [ { "juror": "j1", "family": "glm", "answer": "…", "ok": true,
                 "repaired": false, "reasoning": "…", "raw": "…" },
               { "juror": "j3", "family": "deepseek", "answer": null, "ok": false,
                 "error": "$[0]: 'SendMail' is not one of [...]", "raw": "[\"SendMail\"]" } ],
    "consensus": "…", "plurality": "…",
    "exact_unanimity": false, "cohesion": 0.67, "corpus_conflict": 0.0,
    "est_tokens": 5412
  },
  "triage": { "bucket": "agreed", "strata": ["audit"] },

  "validation": { "status": "corrected", "verdict": "incorrect", "curated_label": "…",
                  "validators": ["u12","u07"], "alpha_contrib": true, "decided_at": "…" },
  "split": "test"
}
```

The second vote is what an abstention looks like: `ok: false`, `answer: null`, and the library's own `error` and `raw` retained. Nothing about it is a partial answer.

## Decisions

**Two composed axes, not one bundle per dataset kind.** *Alternatives:* one plugin supplying all eleven pieces; a full stage graph forked per modality. *Why:* a bundle makes a voice classification dataset and a voice tool-decision dataset each re-declare the same audio loader, embedder, and privacy detectors — the duplication lands exactly where correctness matters most. Forking the stage graph per modality copies fifteen gates, and gates that exist in two places drift. Composition means a new modality is one implementation that every existing profile can immediately use. *Reversible:* yes, and cheaply, since both are protocols resolved from a registry.

**The generic core is `(answer, δ, consensus)`.** *Alternatives:* a per-task pipeline; a task-type enum branched on inside each stage. *Why:* this is what the machinery actually needs. Cohesion, conflict, the four buckets, α, adjudication, and juror calibration are all expressible in those three terms, so genericity here is an interface rather than a framework — which is the difference between a cheap abstraction and a speculative one. *Reversible:* no in practice, and it should not be: it is the whole thesis.

**A profile may declare `consensus = None`.** *Why:* free-text generation has no defensible consensus, and inventing one would produce a plausible machine-written label that the optional tier could ship. Declaring the gap keeps such profiles fully supported for triage — where they are genuinely useful — while making the one thing they cannot do explicit. *Reversible:* a profile can gain a consensus later; nothing depends on its absence.

**Every profile passes a conformance suite before it can be selected.** *Alternatives:* trust the protocol's types; check at first use. *Why:* the types cannot express "δ is a metric" or "consensus is deterministic", and a profile violating either produces cohesion numbers that look fine and mean nothing. Failing at registration rather than at the jury stage moves the error from a 100M-token run to a test. *Reversible:* the suite grows; it does not go away.

**Media by reference and checksum, never inlined.** *Alternatives:* base64 in the JSONL; a parallel manifest keyed by `rid`. *Why:* artifacts must stay streamable and diffable, and inlining a video corpus makes both impossible. Content addressing also gives deduplication and integrity checks for free. *Reversible:* no — this is the decision that has to be right before the first line of code, and it is why it is specified now rather than with the first non-text modality.

**Non-text modalities are a seam, not an implementation.** *Alternatives:* build image support now; leave modality unmodelled and refactor later. *Why:* building now spends real effort on requirements nobody has stated, and the pipeline's value is proved by shipping one dataset first. But three things could not be retrofitted without touching all fifteen stages — typed content parts, media by reference, and a uniform privacy-span shape — so those are in now and the rest waits. *Reversible:* the seam is cheap to widen; the record shape would not have been cheap to change.

**Invalid records are quarantined, never auto-repaired.** *Alternatives:* resolve contradictions by preferring one source; truncate out-of-space labels. *Why:* both are guesses about which of two disagreeing sources is right, applied at scale, invisibly. A quarantine file is a morning's work and a permanent record of what was decided; an auto-repair is a data cascade with a clean-looking count. *Reversible:* re-admission is an explicit command that versions the pipeline.

**Privacy is replaced with stable placeholders, not deleted or hashed.** *Alternatives:* delete the span; hash it; drop the record. *Why:* for many tasks the ground truth turns on whether a value was *supplied*, and deleting it silently inverts the label. A stable typed placeholder preserves suppliedness and co-reference while carrying no personal data. *Reversible:* only from the vault, which never leaves the raw tier.

**`data/raw/` is outside DVC.** *Why:* the vault must never be tracked, and the only cheap way to check that is for the whole directory to be outside DVC — a per-file exclusion is a line someone deletes by accident. The source loses nothing: its identity is a SHA-256 the ingest gate already asserts. *Reversible:* no, deliberately.

**The test split is 100% human-validated, at any budget.** *Alternatives:* validate a sample of test; let jury consensus fill it. *Why:* every number a release reports is computed on test, so a machine-labelled test split measures agreement with a model rather than correctness, and nothing downstream recovers from that. *Reversible:* no.

**The pipeline is DVC stages, not a service.** *Alternatives:* Airflow/Prefect; Celery jobs; a shell script. *Why:* every stage is a pure function from artifact to artifact, which is what DVC models natively, and lineage plus reproducibility from a commit hash is the requirement, not scheduling. *Reversible:* yes; each stage is a CLI command an orchestrator could call unchanged.

**Label Studio, not Argilla, and not our own UI yet.** *Why:* Argilla has shipped no functional change in seventeen months. Building our own UI first inverts the order of risk — it spends a quarter before anyone has answered whether the questions are answerable. *Reversible:* yes; Label Studio is touched only by `human_review/labelstudio/`.

**Assumption:** Label Studio Community honours `maximum_annotations`. The smoke rung verifies it before anything is built on it; if it does not hold, overlap comes from one project per annotator joined on `rid`.

**Assumption:** every token figure is an estimate until `agent-toolkit` surfaces `usage` on `Completion`. Budgets carry declared headroom and runs label their figures "estimated".

## Invariants

1. **Nothing is lost between stages.** `output + quarantined + deduped_out == input`, asserted on every stage and written to `metrics.json`.
2. **`rid` is stable.** Re-ingesting the same source yields byte-identical `rid` values regardless of order. *Check:* shuffle a fixture, re-ingest, compare.
3. **No personal data downstream of `pii_check`, and the vault is untracked.** *Check:* a gate scanning every release-tier file, plus a repo test asserting the vault is in `.gitignore`, in no `.dvc` file, in no `dvc.yaml` output, and that `data/raw/` is absent from DVC entirely.
4. **No media is inlined.** No artifact under `interim/`, `processed/`, or `release/` contains a base64 blob or a non-text part without a `uri` and `sha256`. *Check:* a schema assertion on every artifact carrying content.
5. **Every answer is inside the profile's answer space.** Every vote, correction, and exported label validates against `profile.answer_schema`. *Check:* pandera on every artifact carrying an answer — a second line of defence behind the schema the jury already passed to the library.
6. **Every juror vote is valid or an abstention.** No stored vote is a truncation of a malformed response. *Check:* structurally guaranteed by `complete_structured` returning `None`, plus a test feeding malformed, prose-wrapped, over-long, and out-of-space responses through a stubbed endpoint.
7. **Votes are reproducible and key-independent.** *Check:* two cold runs over a fixture against a recording proxy, diffed; a test forcing key rotation mid-run and diffing the votes.
8. **The panel is diverse, measured, and clean.** ≥3 jurors, ≥3 distinct families, no `"unknown"`, no corpus-family juror unless tagged `control`. *Check:* the jury gate reads the panel config and calls `model_family` on every juror.
9. **δ is a metric.** For every registered profile: `δ(a,a) = 0`, symmetry, range `[0,1]`, no `NaN`, including on the profile's empty answer. *Check:* the conformance suite, over generated answer pairs.
10. **No model output reaches an annotator.** *Check:* a contract test asserting the payload key set equals an explicit allowlist.
11. **Corrections stay in the answer space.** *Check:* structurally where the UI can express it, and asserted again at pull time.
12. **No group spans splits.** No `group_key` in more than one of train/val/test, nor in a subsample absent from train. *Check:* set intersection in the split gate.
13. **Test is fully human-validated.** Every test record has `validation.status ∈ {original, corrected}`. *Check:* export gate.
14. **Releases are reproducible.** `dvc repro` from a clean checkout reproduces every artifact's SHA-256. *Check:* CI on the smoke fixture, diffing `MANIFEST.sha256`.
15. **The sampling design is reconstructible.** Every annotated record records its stratum and selection probability. *Check:* the residual-error estimator refuses to run when any lacks one.
16. **The core is task-agnostic and modality-agnostic.** No module under `pipeline/` or `shared/` imports a concrete profile or modality. *Check:* an import-graph test over the source tree.
17. **The library is not re-implemented.** No module defines a hash helper, a JSONL reader or writer, an atomic-write context manager, a JSON-from-text extractor, a template filler, or a retry wrapper; `openai`, `tenacity`, `tiktoken`, and `jsonschema` appear in no pipeline import. *Check:* a lint test over the source tree.

## Error Behavior

A failed gate writes `data/<stage>/GATE_FAILED.json` with the assertion, the observed and expected values, and up to 100 offending record ids, then exits non-zero so `dvc repro` halts. No stage consumes an input whose gate did not pass. Every provider failure arrives as an `LLMError` subclass, so each dispatching stage wraps one `except LLMError`; nothing catches bare `Exception` around an LLM call.

| Situation | Behavior |
|---|---|
| Source SHA-256 differs from `params.yaml` | Hard stop. A changed source is a new dataset version, decided by a human. |
| Problem count moves > ±10% from declared | Hard stop with the delta. |
| Profile fails the conformance suite | Hard stop at registration, before any stage runs. |
| Profile and modality names disagree | Hard stop. A profile declares its modality; a mismatched pair is a configuration error, not a coercion. |
| A modality has no redactor for a part | Record quarantined to `quarantine/pii/`, never advanced. |
| `enable_redact` is false | The stage reports and stops there. The downstream personal-data scan then fails, so nothing ships — the default cannot silently release personal data. |
| Privacy verification returns a schema-invalid response | Span is unverified, not negative. Record quarantined. |
| LLM unavailable during privacy verification | Stage stops and resumes from its checkpoint; verified spans are kept. |
| A juror unreachable for a whole run | Continue on the rest if ≥3 recognised families remain, recording the reduced panel per record. Below the floor, stop. |
| `LLMRateLimitError` on one key | Per-key backoff; dispatch continues. |
| `ProviderQuotaExceededError` on one key | Key quarantined for the declared cooldown — not from `retry_after`, which the library never populates. Throughput degrades; the run does not stop. |
| All keys in a group exhausted | That juror is incomplete for the affected records, which keep their votes and are re-queued rather than scored on a partial panel. |
| `LLMAuthenticationError` / `LLMConfigError` | Hard stop, not a retry and not a quarantine. |
| Juror answer fails schema after one retry | Abstention with `raw` and `error` retained. Never truncated. |
| Invalid-vote rate above 5% for a juror | Jury gate fails. A juror that cannot follow the output contract is not usable as signal. |
| `repaired` rate above a declared threshold | Warning in `jury_report.json`, not a stop — a prompt-quality signal worth watching before it becomes an invalid-vote problem. |
| Token estimate exhausted mid-run | Clean partial stop; cast votes retained; run status `partial`. |
| Label Studio unreachable on publish | Retry with backoff, 5 attempts, then fail with pushed tasks recorded. Publishing is idempotent on `rid`. |
| Incorrect verdict with no correction | Rejected, not repaired. Returned to the queue with the reason. |
| α below 0.667 at the pilot gate | Hard stop with the per-focus breakdown. The remedy is a guideline revision and a re-pilot, never a lower threshold. |
| α above 0.95 | Warning plus a mandatory written review note in the datasheet. |
| Bucket precision below its floor at the pilot gate | Hard stop. The panel or the thresholds change first. |
| Annotator below 0.85 on gold | Work held pending review; submitted answers re-queued for a second opinion rather than discarded. |
| Group leakage or n-gram overlap | Hard stop. Every metric on a leaked split is void. |

Two failures have no automated detector. A **plausible but wrong question** — well written, about the wrong thing — is caught only by the flag rate, which is why 10% is a gate. And a **jury confidently wrong in the same direction as the existing labels** produces `agreed` records that are quietly incorrect; only the uniform random audit sample can see those, which is why it is uniform and never repurposed.

## Testing Strategy

- **Conformance.** The suite of requirement 6, run against every registered profile in CI: δ as a metric over generated answer pairs, consensus determinism and unanimity agreement, answer-schema round-trip, adapter field preservation, exporter reproducing the adapter's answer. A new profile is not merged until it passes.
- **Genericity.** A second, deliberately trivial profile — single-label classification over a 30-record text fixture — runs the whole graph end to end. Two profiles is the cheapest proof that the core is not secretly one profile's code, and the classification profile is small enough to be worth it for that reason alone.
- **Modality boundary.** A stub modality returning one audio part with a `uri` and no inline bytes runs `load` → `quarantine_invalid` → `pii_check` → `embed`, asserting the stages neither inline it nor crash. This is the seam's only test until a real audio modality exists, and it is what stops the seam rotting.
- **Import graph.** No `pipeline/` or `shared/` module imports a concrete profile or modality — invariant 16. No module re-implements a toolkit function — invariant 17.
- **Contracts.** Every artifact has a pandera schema; a round-trip test writes with `write_jsonlines`, reads with `read_jsonlines`, and validates.
- **Agreement.** α over an arbitrary δ against a hand-computed example, plus the degenerate check that α with an identity distance equals `krippendorff`'s nominal α on the same data. Consensus against hand-worked vote sets, including where consensus differs from every individual answer.
- **Privacy.** Per modality: a fixture asserting recall on real personal data and *no* replacement on look-alikes; placeholder stability across two mentions of one value; the vault absent from `dvc.yaml` and every `.dvc` file and present in `.gitignore`.
- **Jury.** A stubbed OpenAI-compatible endpoint returning a clean answer, a fenced answer, prose-wrapped JSON, an out-of-space answer, a wrong type, and empty — each becoming a valid answer or a clean abstention, with `repaired` true for exactly the fenced and prose-wrapped cases. Panel diversity against one-family and unrecognised-name configs. Cache determinism. Key-pool failover with a 429 on one key and a quota error on another, asserting identical votes to a single-key run and that an auth error stops the run instead.
- **Triage.** Bucket assignment over hand-built (cohesion, conflict) grids including boundaries; audit sizing against worked values (`p=0.05, e=0.02 → 457`); records below the vote minimum excluded rather than bucketed.
- **Toolkit boundary.** One integration test running `agent-toolkit`'s own `tests/consumer_smoke.py` against the installed environment, so a bad git-dependency resolution is caught here rather than at the first jury run.
- **Label Studio.** The generated config validated against a live instance in CI via testcontainers — create project, push three tasks, pull back a submitted annotation. The allowlist test runs on the built payload without a server.
- **Split.** A planted group spanning what would be a random split, and a planted n-gram overlap, each asserted caught.
- **End to end.** The smoke rung *is* the integration test: `dvc repro` from raw to release against stubbed jurors, a stubbed generator, and a containerized Label Studio, asserting a byte-identical `MANIFEST.sha256` on a second run. This passing is the definition of the pipeline being done.

## Out of Scope

- **Image, audio, and video modalities.** The seam is specified and tested with a stub; no real implementation ships here. The platform spec's image controls are deferred with them.
- **Model training and evaluation.** This produces a dataset, a metric definition, the training subsamples, and a zero-shot jury baseline. Fine-tuning, learning-curve training runs, and any eval harness belong to a separate spec.
- **Actual-token accounting.** Needs `usage` on `agent-toolkit`'s `Completion`. Filed against the library.
- **Extending `agent-toolkit`.** Gaps found here are fixed by a release there, not patched locally. The pin is a tag for exactly this reason.
- **Confident Learning and classifier-based label auditing.** Belongs to a profile with a fixed class space, not to this core.
- **Synthetic data generation** and **active learning loops.** The jury is a one-shot ranking per release, not a model that retrains as annotations arrive.
- **Fine-tuning a juror.** Jurors are off-the-shelf models behind API keys.
- **Our own annotation service.** Deferred, not cancelled — the first profile's pilot decides whether it is worth building, and [`dataforce-platform`](../dataforce-platform/spec.md) remains its spec.
- **Automatic write-back to any source file.** Export produces an artifact; putting it anywhere is a human step.
- **Cross-border transfer review.** Real, and sharper because the jury sends content to external LLM endpoints. It is a legal review of where the data and those endpoints sit, not a pipeline stage, and it happens before the first jury run against any offshore endpoint.

---

**Grounded in:** [`agent-toolkit` v0.1.0](https://github.com/giangchicken/agent-toolkit), read from source · [Label Studio](https://labelstud.io/guide/setup) · [SemHash](https://github.com/MinishLab/semhash) · [crowd-kit](https://github.com/Toloka/crowd-kit) · [DVC](https://dvc.org) · [Croissant](https://github.com/mlcommons/croissant) · Gebru et al., *Datasheets for Datasets* (CACM 2021) · Bender & Friedman, *Data Statements* (TACL 2018) · Northcutt et al., *Pervasive Label Errors* (NeurIPS 2021) · Sambasivan et al., *Data Cascades* (CHI 2021) · Shumailov et al., *Model collapse* (Nature 2024) · Zheng et al., *Judging LLM-as-a-Judge* (NeurIPS 2023) · Penedo et al., *FineWeb* (arXiv:2406.17557)
