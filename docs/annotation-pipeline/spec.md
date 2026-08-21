# Annotation Pipeline — Gated Stages for Any SFT Dataset

## What

A reproducible pipeline that turns a raw corpus into a versioned, documented, training-ready dataset. It is fifteen stages, each producing a checksummed artifact and each guarded by a machine-checked **gate** that fails the run rather than passing bad data downstream. The stages are sequenced in-process by `api/`, which is the surface every caller enters through; DVC versions the data at milestones and does not orchestrate. Several models answer the dataset's own task first, and their disagreement decides which records a human looks at.

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
| Tool / function selection | a set of **calls**: a name, and the arguments it is called with | soft Jaccard: names matched first, then how far their arguments agree | each name a majority included, each argument the value a majority gave |
| Single-label classification | one class | `0` if equal else `1` | the mode |
| Multi-label classification | set of labels | `1 − |A∩B| / |A∪B|` | included by a strict majority |
| Span extraction (NER) | list of spans | `1 − span-F1` | spans a majority marked |
| Ranking / preference | an ordering | normalised Kendall τ distance | Borda count |
| Free-text generation | a string | `1 − similarity` | **none — abstains** |

Tool selection is the row that stretches the interface, and it is worth reading before the rest of this document: its answer is **compound**. Two jurors naming the same tool and differing on one argument value are neither in agreement nor in the same position as two jurors naming different tools, so δ cannot be a single set comparison — and whatever it is, every cohesion figure, every triage bucket and every α inherits it. That is specified once, in requirements 70–75 and in *Decisions*, rather than being decided inside a stage. The other five rows are single-valued answers and are the easy case.

Free-text generation is the honest exception. There is no defensible consensus over generated strings, so a profile may declare `consensus = None`, and then the jury ranks records by disagreement but proposes no answer. Triage still works: cohesion is computable, `corpus_conflict` is computable, and the four buckets still sort. Only the optional `jury_consensus` tier is unavailable, which is correct — a tier that shipped machine-written prose as a label would be exactly the failure the model-collapse literature describes.

### What is borrowed

| Need | Use | Version checked |
|---|---|---|
| Annotation UI, users, task serving, locking, multi-annotator | **Label Studio** Community (Docker) + `label-studio-sdk` | 1.23.0 (2026-03-13); SDK 2.1.1 (2026-08-10) |
| Near-duplicate detection over embeddings | **SemHash** | 0.4.1 (2026-01-20) |
| Annotator verdict aggregation (Dawid-Skene, MACE) | **crowd-kit** | 1.4.2 (2025-10-13) |
| Krippendorff's α, nominal | **krippendorff** | 0.8.2 (2025-11-03) |
| Artifact schema validation | **pandera** | 0.32.1 (2026-06-29) |
| Data versioning at milestones (`dvc add`) | **DVC** | 3.67.1 (2026-03-31) |
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

1. A **modality** supplies exactly four things, each named for what it returns: `content_parts` (raw → typed parts), `embedding` (parts → vector) for duplicate detection, `personal_data_detectors`, and `display_config`, the annotation-UI half that *displays* a record. Nothing else. A turn that carries something other than a string — a tool call, an attachment reference — is still one part, and rendering it into one is `content_parts`' job by requirement 70: it is the source's own layout, and this is the only member that is allowed to know it.
2. A **profile** supplies exactly nine things, each named for what it returns: `build_record`, `answer_schema`, `answer_distance`, `vote_consensus`, `validity_checks`, `question_text`, `answer_config`, `scenario_hash`, and `training_example`. It declares which modality it composes with, and its own name and version. No member shares a name with a stage.
3. The annotation-UI config is **composed, not owned**: the modality contributes the control that displays the content, the profile contributes the control that captures the answer. Neither may emit the other's half. This split is the reason a new modality does not multiply the profiles that already exist.
4. `answer_distance` must satisfy four properties on the profile's answer type: `δ(a,a) = 0`, `δ(a,b) = δ(b,a)`, `δ ∈ [0,1]`, and never `NaN` — including on whatever the profile's empty or null answer is. This is profile rule 1, and the profile's own tests are what prove it; δ remains the symbol used in the α formulas of requirements 52–53. **The triangle inequality is deliberately not among the four**, because a compound answer's δ is a weighted average and weighted Jaccard does not satisfy it. Nothing in the pipeline needs it: cohesion, corpus conflict, the four buckets and α are all defined on pairwise distances, and no stage embeds an answer in a metric space or clusters answers by distance. A stage that ever wants to is the moment to revisit this, and it says so here so that moment is not a surprise.
5. `vote_consensus` is deterministic given a list of votes, and may return `None` to declare that the profile has no defensible consensus. A profile returning `None` is barred from the optional consensus tier of requirement 34 and is otherwise fully supported. Combining *people's* answers is a different operation and is not this member: annotators are aggregated with per-annotator reliability weighting in stage 10.
6. Every profile satisfies the five **profile rules** in § *Rules a profile must satisfy*, and **tests them itself**. The rules are stated once for every profile to follow; each profile's own test module proves them for its own answer type. There is no shared suite and no check at registration: a profile that breaks a rule is a profile whose author did not follow it, and the cost of that is stated with the rules rather than caught by machinery.
7. Profiles and modalities are resolved from a registry by name, and the resolved pair, with each one's version, is recorded on every artifact and in the release manifest. A run cannot silently change which code produced a dataset.

### The modality seam

8. A record's content is an **ordered list of typed parts**, never a bare string. Each part carries its `type`, its role, and either inline text or a reference. Text profiles see a list of text parts; nothing about the shape changes when a part becomes audio.
9. **Non-text media is held by reference and checksum, never inlined in an artifact**: `{"type": "audio", "uri": "media/ab/abc123.wav", "sha256": "…", "duration_s": 12.4}`. Artifacts stay diffable and streamable at any corpus size, which is the difference between a 126 MiB text corpus and terabytes of video. This is the one modality decision that must be made before the first line of code, because retrofitting it would touch all fifteen stages.
10. `rid` is derived from the content parts' digests, not from raw bytes: text parts contribute their text, media parts contribute their `sha256`. So the identity of a record is modality-independent and stable across re-ingests and re-ordering. A part rendered from something that was not already a string — a tool call — must be rendered **canonically**, one form per value, or `rid` stops being reproducible and invariant 2 fails; requirement 70 says which form.
11. Privacy detection is a modality concern with a **uniform result shape** — a list of typed spans over a named part — so the redaction stage, its report, its vault, and its gate are written once. What a "span" indexes is the modality's business: character offsets in text, a time range in audio, a box in a frame.
12. A modality that cannot yet redact a part **fails closed**: the record is quarantined, never advanced, and it says so on itself — `unredactable_part` is appended to `failed_checks`, the same field stage 1 writes. Failing open on personal data is the one failure this pipeline will not take, and a new modality inherits that rather than choosing it. `privacy` stays what it is, the *evidence*: what was found and replaced. The verdict is never inferred from the evidence, because the success shape and the withheld shape are otherwise identical.

### Ingest and source integrity

**What `remove_invalid` is for.** Some records cannot be used and you can prove it by counting: the label contradicts the training target, the answer names something the record never offered, the answer space is empty. No person decides any of that — if telling right from wrong needs judgment, it is not this stage's business, it is an annotation task, and it belongs in `human_review` with the jury and the annotators.

Running it first is what makes the rest affordable. Every record it moves is one the jury would have spent tokens on, an annotator would have spent minutes on, and the model would then have learned something false from — paid for in that order, and the arithmetic that avoids all three costs seconds. It is also the tripwire: a stage that moves ~0 today is what tells you the day the source or the reader moves, which is why the expected count per check is declared and why a count that shifts fails the gate rather than being logged. Nothing is deleted — each record goes to `quarantine/invalid/<check>.jsonl` naming the check it failed, and comes back by an explicit command once the cause is fixed.

13. Ingest streams the source via `file_utils.iter_json_array_file` or the modality's loader. A source file is never loaded whole.
14. Ingest records provenance per record: source file SHA-256, byte offset, the raw record verbatim, the modality and profile names with versions, and the ingest timestamp. Nothing is dropped; unparsable records are carried with `parse_status = "unparsed"` and their raw text.
15. The **source-integrity gate** runs the profile's validity checks, and each failure writes the record to `data/quarantine/invalid/<check>.jsonl` naming the check it failed, and removes it from the main path. Records are never silently deleted and never silently kept.
16. Expected invalid counts per check are declared in `params.yaml`, and a count moving more than ±10% fails the gate. The source changed, and that must be a decision rather than a surprise. Re-admission is an explicit `dataforce requeue --check <name>` that versions the pipeline.
17. Every artifact is written with `file_utils.write_jsonlines` or `write_json` and read with the matching reader. Both are atomic and create parent directories, so an interrupted stage leaves the previous artifact intact. No stage opens an artifact file directly.

### Privacy

18. `pii_check` detects in two layers with separate jobs: the modality's detectors maximise recall and are allowed to be noisy, and an LLM pass over a bounded window, via `llm.complete_structured` against a fixed classification schema, sets precision. It **always** writes a findings artifact — every candidate span with its class, its surrounding window, and the verifier's verdict — which is what a person reads before deciding anything. A verification response that fails its schema leaves the span **unverified, not negative**.
19. Rewriting content is controlled by one parameter, `enable_redact`, **false by default**. False: the stage reports and leaves content untouched. True: verified spans are replaced with **stable typed placeholders** scoped per record (`<PHONE_1>`, `<EMAIL_1>`), so a value referenced twice stays co-referent — and never deleted, because deleting a value can change the ground truth of the very judgment the record encodes.

    What lands on the record is one entry per span: the `Span` shape — which part, the modality's own locator into it, the class — plus the placeholder it became. That is enough to say *this field held a phone number here, and it is now `<PHONE_1>`* without the record containing a phone number, which is the whole trick: the class and the location are the meaningful part, and the value is the part that cannot be kept. Counts and the class set are **derived** from the spans rather than stored beside them, so the two can never disagree about what was found.
20. The gate is what makes the default safe. With redaction off, release-tier artifacts still match literal personal-data patterns, so the scan below fails and nothing ships. Turning it on is a change to `params.yaml`, which is committed and whose digest every run records in its run manifest — so the decision is attributable, without a bespoke approval format.
21. The placeholder-to-original mapping is written to `data/raw/pii_vault.jsonl`. `data/raw/` is **not DVC-tracked and not committed**: the source file's identity is a SHA-256 in `params.yaml`, and the vault appears in `.gitignore` and in no `.dvc` file. Every other directory under `data/` may be versioned with `dvc add`. The findings and redaction reports record, per class, the counts and a sample of 20 *placeholders in context* — never original values — and the gate fails if any release-tier artifact matches a literal personal-data pattern.

### Duplicates and grouping

22. **Exact duplicates are a `rid` collision and need no field.** `rid` is already a hash over every part's `type:role:text` in order, so two records with byte-identical content carry the same one by construction — a second content hash beside it would be a second name for it. Measured on the reference source: 21,171 distinct rids over 21,172 records, which is that check already run. Of a colliding pair the record with the richer metadata is kept.
23. **Near-duplicates are a cluster, not a hash**, because near-identical is not identical: they are found with SemHash over the modality's embeddings, and a record carries `conversation_cluster` and `conversation_cluster_size`. Members are **not deleted** — `export` drops all but one, so the decision is reversible and recorded.

    **Which one survives is a declared rule, not a stored flag.** The rule: the member with the most `meta` keys, ties broken by the lowest `rid`. Deterministic, so two runs drop the same rows. A rule rather than an `is_representative` boolean because a stored outcome records *that* a choice was made without recording *why* — and this document carried that flag through four requirements with **no rule behind it at all**, which meant which records ship was undecided in a document that specifies fifteen gates.

    A record carries the cluster's **id and size, never the list of its siblings' ids.** The membership exists once, in `clusters.jsonl`, the artifact a person investigating duplicates opens. On the largest cluster measured — 112 records — a sibling list on every row is **248,640 bytes against 2,240, and 112 copies of one fact**, any of which can disagree after any stage touches a cluster. Size is there because it is the question a reader of one row actually has: *of how many* — O(1), no second file.
24. Every record gets a `scenario_hash` from the profile, unioned with its `conversation_cluster`. A field that is unique per record is not a group key, and the profile is responsible for saying so with a measurement rather than an assumption.

    **Both are named for the object and for what the value is**, because that is all a reader needs in order to say whether two records should share one. `scenario_hash` is a hash of whatever this profile means by one scenario — for tool selection the catalog, which is why the profile's own function is `catalog_hash`. `conversation_cluster` is a cluster id over conversations and deliberately *not* called a hash: two near-identical conversations hash differently, so the word would be a lie in the name. `rid` covers the identical case and is already a hash.

    **The two are not nested, and the union is what protects.** They answer different questions over different halves of the record: `scenario_hash` is the profile's — *is this the same scenario* — a pure function of one record, reproducible without a corpus; `conversation_cluster` is `dedup`'s — *do these two say the same thing* — from an embedding that deliberately excludes the instruction role, so it compares the conversation. Neither is a refinement of the other, and the measurement says so loudly: on the reference source, **490 of 491 exact-duplicate-conversation groups span two different catalogs**, covering 980 records. Same utterance, different tools offered, different correct answer. `scenario_hash` alone puts every one of those pairs in a *different* group and lets it straddle a split, which is the leak a model exploits by recognising a conversation it saw with another catalog. This is why requirement 57 splits on the union rather than on either, and why a profile is asked for a measurement rather than an opinion about its own grouping.

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
34. **No jury output becomes a training label without human confirmation.** The jury selects and ranks; it does not relabel. Optionally and explicitly, the unvalidated remainder may carry consensus as a separate tier — `validation.status = "jury_consensus"`, permanently barred from test, with its own error bar measured against the audit sample — opt-in per release, off by default, and unavailable to profiles whose `vote_consensus` is `None`.
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
53. Agreement on **corrections** is computed as α with the profile's `answer_distance`, implemented here because the library covers only nominal, ordinal, interval, and ratio scales. Its nominal degenerate case is tested against the library's output.
54. Where overlap ≥ 2, verdicts are aggregated with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote. Corrections are aggregated with the profile's `vote_consensus`.
55. Disagreements, and records below an aggregated-confidence threshold, go to a second **adjudication** project showing both answers and both notes, resolved by a reviewer who produced neither. Label Studio Community has no review workflow; this is that workflow.
56. Curation records for every record whether its label is `original`, `corrected`, `jury_consensus`, or `unvalidated`, with the validator and the decision date.

### Split, export, document

57. Splitting is **group-based on `scenario_hash`**, never random. A group is wholly in one split, and the same holds for any training subsample.
58. The test split is **100% human-validated**. A record that has not been annotated cannot enter test at any budget, and `jury_consensus` records are barred permanently.
59. Decontamination verifies zero n-gram overlap between test and train, and zero shared `scenario_hash`. Either fails the gate.
60. Export emits the profile's training format. Every exported record carries provenance: source SHA-256, pipeline version, modality and profile versions, `agent-toolkit` version, validation status, validator, dedup cluster, split, stratum, and the panel version where the jury touched it.
61. The release is a DVC-tracked directory with a manifest listing every file's SHA-256, reproducible from one git commit plus one `dataforce run`.
62. Each release ships a **datasheet** (Gebru et al.), a **data statement** (Bender & Friedman), and a **Croissant** file validated by `mlcroissant`. The datasheet states the machine-labelled share explicitly and names the jury panel with each juror's family and gold-calibrated weight, because which records humans looked at is part of how the dataset was made. Documentation is a gated stage; a missing required field fails the release.

### Proving it works before scaling

63. Every dataset climbs three rungs with exit gates, and the numbers on each rung are the profile's: a **smoke** run small enough to finish in one sitting, proving the plumbing; a **pilot** proving the instruments — is the question answerable, is the guideline right, do two people agree, and does each triage bucket predict what humans actually find; then **scale**, which produces the release. You do not climb without passing.
64. The pilot gate requires all of: α on verdict ≥ 0.667 (below it the guideline is broken, not the annotators); α ≤ 0.95 or an investigation (near-perfect agreement on a subtle task means the questions dodge the hard cases); question flag rate ≤ 10%; per-annotator gold accuracy ≥ 0.85; and `likely_label_error` bucket precision above a declared floor — if the jury's flags are mostly wrong it is sending humans on a walk, and the panel changes before the full corpus depends on it.
65. Scale deliberately annotates a **designed subset** rather than everything: the full test split, the audit sample, and the jury-flagged strata. The remainder ships as `unvalidated` with a measured error bar, which is an honest artifact — full manual validation ships the same corpus much later with no error bar at all, because nothing was sampled to estimate one from.

### Layers and the published surface

66. **The engine computes and never touches the filesystem.** No module under `modalities/`, `profiles/`, `pipeline/` or `shared/` opens a file, names a config or data location, or imports `agent_toolkit.file_utils`. Neither axis is constructed at import time, so importing a profile reads nothing and works from any working directory.
67. **`declared/` is the only package that reads `config/`.** It turns files into the objects the engine accepts. Every path it takes is a required parameter with no module-level default, so nothing infers a location from the process's cwd.
68. **`api/` is the published surface.** Every caller enters through it, `cli.py` included — the CLI holds argument parsing, logging setup and exit codes, and no behaviour of its own. `api/` sequences the fifteen stages in-process, persists artifacts, and is the only place a gate's verdict is written to disk.
69. **Every run writes a run manifest** recording the SHA-256 of every policy file it read, the `name@version` of both axes, and the SHA-256 of every artifact it wrote. This is the lineage record that DVC's declared dependencies used to be, and diffing two of them is how reproducibility is checked.

The layer diagram, the import rule and the order the split lands in are in [`../engine-api-split/spec.md`](../engine-api-split/spec.md).

### Compound answers

An answer may be more than one value. Tool selection is the case that forces this: the answer is a set of calls, and a call is a name *and* the arguments it is called with. These six requirements are what the rest of the document assumes wherever it says "answer", and they are numbered from 70 so that every citation of requirements 1–69 in the plan stays true.

70. **A turn that is not a string becomes a part canonically.** A source may carry a tool call as structure — an OpenAI `tool_calls` array, `content: null` beside it. `content_parts` renders it into one text part holding **canonical JSON**: object keys sorted, no insignificant whitespace, arguments parsed from any string form the source used and re-emitted in that one form. Two sources spelling the same call differently therefore produce the same part, the same digest and the same `rid`. This is the modality's job because it is the source's layout, and it is a *rendering* rather than an interpretation: nothing here decides what a call means.
71. **A record stores no answer space. The profile derives one.** Choosing the profile settles the answer *type* — an array of calls — and the record's own content settles the *space*: which names, and each name's `parameters`. Both are already on the record, so a stored answer space is a second copy of one of them, and the record carries no field for it.

    Where a JSON Schema is genuinely needed — the jury's `complete_structured` call, pull-time validation of a human correction, invariant 5's check on an artifact — the profile **materialises one from the record at that moment**, and nothing persists it. That is what requirement 5 means by an answer schema built per record. Everything that needs only the *names* — `scenario_hash`, the validity checks, the capture control — reads the catalog, not a schema wrapped around it.

    Measured, because the first draft of this requirement said the opposite and the numbers are what changed it. Deriving the catalog costs **0.27 µs** per record where the source carries it as data, against 0.07 µs to read a stored copy: **0.0 seconds across a 21,172-record run**, so the stored copy buys nothing on the shape this pipeline is for. Where a source renders its catalog into prose the parse is 93 µs, and paying it once at stage 0 — which already parses it — keeps that at zero too. Against which a stored copy costs a second thing that can disagree with the first, an artifact column on every record, and, for a compound answer, 3,247 bytes against the catalog's own 2,888 — a copy larger than the original. The pipeline's own rule already settled it: *a source's vocabulary is declared once, and everything derivable is derived.*

    A profile whose answer space cannot be expressed as one JSON Schema per record does not have a compound answer, it has a free-text one, and § *The three-piece interface* says what that costs.
72. **δ over a compound answer is soft, and the softness is specified rather than chosen in a stage.** Answers are compared name-first: over the union of names in the two answers, a name in both contributes how far its arguments agree — the share of argument keys present in both and equal, counting a key present in only one as a disagreement, and counting two calls with no arguments as agreeing — and a name in only one contributes zero. δ is one minus the mean of those contributions. Two consequences are the point of it: naming a different tool is full disagreement, and naming the same tool with one differing argument is *partial*. And it degrades exactly: when every matched call has identical arguments, this **is** Jaccard over names, so a names-only profile is the special case rather than a different formula.
73. **At most one call per tool name per answer.** Two calls to one tool with different arguments make the answer a multiset, and matching them pairwise before comparing arguments is a second decision that δ would have to make silently. It is declared out instead, with a validity check that fires — a record whose answer names one tool twice goes to quarantine, where a person decides whether the source means parallel calls or is malformed. *Reversible:* the check is the only thing that would be removed, and requirement 72 would gain a matching rule.
74. **Consensus is per name, then per argument.** A name is in the consensus when a strict majority of votes included it; each of that name's argument keys takes the value a strict majority of the votes naming it gave; a key with no majority is absent, and if a key the tool declares `required` has no majority the call is dropped from the consensus entirely. Never a partially-invented call: a consensus call that would fail requirement 71's validation is not a consensus.
75. **Capturing a compound answer is a form, and the fallback is declared now.** The profile's `answer_config` emits the name control plus, per name, the argument fields generated from that tool's `parameters`. Where the annotation tool cannot express per-name conditional fields, the fallback is one text control capturing JSON, **validated at pull time against requirement 71's schema** — never accepted unvalidated, and the pull gate rejects an answer outside the space rather than truncating it. Which of the two shipped is recorded per project, because it changes what an annotator could physically express and therefore what their agreement means.

## Design

### Stage graph

Fifteen stages: declared inputs, declared outputs, a gate. `api/` sequences them in-process: `dataforce run [stage ...]` runs the stages it is named, or all fifteen.

| # | Phase | Stage | What it is for | Output | Gate |
|---|---|---|---|---|---|
| 0 | data_quality | `load` | Turn the raw source into canonical records, and pin which version of the source file this run used | `interim/1_data_quality/loaded.jsonl` | parsed + unparsed == source count; source SHA-256 matches params |
| 1 | data_quality | `remove_invalid` | Move the records that cannot be used out of the main path, before anything expensive touches them | `interim/1_data_quality/usable.jsonl`, `quarantine/` | invalid counts within ±10% of declared |
| 2 | data_quality | `pii_check` | Find personal data, report it, and replace it if `enable_redact` says so | `interim/1_data_quality/pii_findings.jsonl`, `redacted.jsonl` | every high-recall hit is verified; zero literal personal-data matches downstream |
| 3 | data_quality | `embed` | Turn each record into a vector so near-duplicates can be found | `interim/1_data_quality/embeddings.npy` | row count matches records |
| 4 | data_quality | `dedup` | Group records that say the same thing, so variants of one scenario cannot straddle a split | `interim/1_data_quality/deduped.jsonl`, `clusters.jsonl` | exact dups 0; cluster report emitted |
| 5 | ai_review | `jury` | Have several models answer the task independently, so their disagreement can be measured | `interim/2_ai_review/votes.jsonl`, `consensus.jsonl` | ≥3 families, none `unknown`; no corpus-family juror; estimated tokens ≤ budget; invalid-vote rate ≤ 5% |
| 6 | ai_review | `rank_for_review` | Decide which records a human should look at, and why | `interim/2_ai_review/queue.jsonl` | every stratum met its quota; audit `n` ≥ computed |
| 7 | human_review | `generate_questions` | Turn each queued record into one focused, answerable question | `interim/3_human_review/questions.jsonl` | schema-valid ≥ 98%; estimated tokens ≤ budget |
| 8 | human_review | `publish` | Put the questions in front of annotators, carrying nothing a model produced | project + `published.jsonl` | payload key set equals the allowlist |
| 9 | human_review | `pull` | Collect the answers and normalize them | `interim/3_human_review/responses.jsonl` | every incorrect verdict has a correction |
| 10 | human_review | `aggregate` | Combine two annotators into one verdict, weighted by how reliable each has been | `interim/3_human_review/aggregated.jsonl` | α ≥ 0.667; flag ≤ 10%; gold ≥ 0.85 |
| 11 | human_review | `curate` | Apply the accepted corrections and record who decided what | `interim/3_human_review/curated.jsonl` | every correction inside the profile's answer space |
| 12 | release | `split` | Divide into train / validation / test so no scenario appears on both sides | `processed/{train,val,test}.jsonl` | zero group leakage; zero n-gram overlap |
| 13 | release | `export` | Write the training files in the shape a trainer expects | `release/v1/*.jsonl` | test 100% human-validated; counts reconcile |
| 14 | release | `document` | Write down what this dataset is made of, so a consumer can judge it | `release/v1/{datasheet.md,croissant.json}` | all required fields present; Croissant validates |

Stages 8–10 loop: publish → annotate → pull → aggregate → adjudicate → publish again. Stage 5 re-runs when the panel changes, and its cache makes an unchanged juror free. `embed` precedes `dedup` because `dedup` consumes the embeddings, and all five sit in `data_quality` because each is a property you can check without an opinion: validity (`remove_invalid`), privacy (`pii_check`), uniqueness (`dedup`), with `load` and `embed` as what makes checking them possible. The phase ends with a corpus; `ai_review` is the first opinion about it.

A stage name is a promise about what the stage does to the data, and the table above carries the purpose in a column rather than leaving it to be inferred from the name. `remove_invalid` names the action and its object, and "remove" is scoped by what the pipeline is: records are removed **from the main path**, not deleted. Each one is written to `quarantine/invalid/<check>.jsonl` naming the check it failed, and `dataforce requeue --check <name>` puts it back. `pii_check` names what it always does, with rewriting behind a parameter rather than behind a second stage; `rank_for_review` names what the ranking is *for*; `generate_questions` names what is generated. `validate`, `scrub`, `defect`, `find_problems`, and `triage` were rejected for the opposite failure: each needed a glossary, and none of them said whether the stage changes the data.

### Repository layout

```
dataforce/
├── pyproject.toml   uv.lock   Makefile   README.md   .gitignore
├── dvc.yaml   dvc.lock   params.yaml    dvc.yaml declares no stages: DVC
│                                          versions data, it does not orchestrate
│
├── src/dataforce/
│   ├── api/                     ← the published surface. Every caller enters here,
│   │   │                          cli.py included. Sequences the stages in-process,
│   │   │                          persists artifacts, writes a gate's verdict
│   │   ├── __init__.py          open_engine · build_records · profile_corpus
│   │   ├── engine.py            Engine — a resolved (modality, profile, policy)
│   │   └── artifacts.py         the only place an artifact is read or written,
│   │                            and where a run manifest is built
│   │
│   ├── declared/                ← the only package that reads config/
│   │   ├── manifest.py          reads one from config/<axis>/<name>.yaml
│   │   ├── prompts.py           prompt templates, by prompt_version
│   │   └── thresholds.py        what a gate compares against, and what one
│   │                            source is declared to hold: gates.yaml, params
│   │
│   ├── shared/                  engine — no I/O, no working-directory assumption
│   │   ├── record.py            canonical record + typed content parts
│   │   ├── manifest.py          what an implementation *is*, once read. The type
│   │   │                        both axes are handed, so it cannot live above them
│   │   ├── schemas/             one module per pipeline phase, so a stage imports
│   │   │   ├── base.py          the columns every artifact carries
│   │   │   ├── data_quality.py  loaded · usable · pii_findings · deduped
│   │   │   ├── ai_review.py     votes · queue
│   │   │   ├── human_review.py  questions · published · responses · aggregated
│   │   │   │                    · curated
│   │   │   └── release.py       split
│   │   ├── registry.py          both axes by name; instance state, no global
│   │   ├── agreement.py         α over any δ, cohesion, plurality
│   │   ├── gates/runner.py      engine only — raises, and writes nothing
│   │   └── errors.py
│   │
│   ├── modalities/              ← axis 1: how content is read
│   │   ├── base.py              Modality protocol: 4 methods, nothing more
│   │   └── text/                content_parts · embedding · detectors · display
│   │
│   ├── profiles/                ← axis 2: what an answer is
│   │   ├── base.py              Profile protocol: 9 members, nothing more
│   │   └── tool_decision/       three definitions, the conversions, two steps, one tool:
│   │       ├── __init__.py      the profile object — the index to the rest
│   │       │
│   │       ├── schema.py        DEFINITION · every shape: a tool · a catalog ·
│   │       │                    ANSWER_SCHEMA · answer_schema_for
│   │       ├── answer.py        DEFINITION · what is computed from an answer:
│   │       │                    answer_distance · vote_consensus · training_example
│   │       ├── source_contract.py  DEFINITION · what this corpus calls things
│   │       ├── utils.py         LOGIC · every conversion of a tool and a catalog:
│   │       │                    tools_to_catalog · catalog_to_tools
│   │       │                    · build_system_prompt · to_strict_openai
│   │       │                    · catalog_names · catalog_hash
│   │       │
│   │       ├── build_record.py  STEP · stages 0–1 · build_record · read_catalog
│   │       │                    · validity_checks · scenario_hash
│   │       ├── ask_annotator.py STEP · stages 7–8 · question_text · answer_config
│   │       │                    · readable_catalog
│   │       │
│   │       ├── measure_corpus.py  TOOL · `dataforce profile`, not in the flow
│   │       └── schemas/         JSON Schema per input shape: what a record and a
│   │                            tool are allowed to look like
│   │
│   ├── pipeline/                ← the fifteen stages as pure functions over records,
│   │                            called by api/. A stage's package
│   │                            is created by the task that implements it, not before
│   │   ├── data_quality/        load.py  remove_invalid.py  pii_check.py  embed.py  dedup.py
│   │   ├── ai_review/           jury.py  rank_for_review.py
│   │   │   └── lib/{panel,keypool,vote,consensus,escalate,buckets,strata,sampling}.py
│   │   ├── human_review/        generate_questions.py publish.py pull.py aggregate.py curate.py
│   │   │   ├── labelstudio/{config,client}.py
│   │   │   └── lib/{questions,alpha,gold,adjudicate}.py
│   │   └── release/             split.py  export.py  document.py
│   │       └── lib/{decontaminate,datasheet,croissant,manifest}.py
│   │
│   └── cli.py                   dataforce run --modality M --profile P [stage ...]
│                                a shell over api/: argparse, exit codes, and the
│                                only place logging handlers are configured
│
├── config/                      policy humans edit; never imported as Python
│   ├── gates.yaml   panel.yaml
│   ├── modalities/<name>.yaml   identity + what decides what its vectors mean
│   ├── profiles/<name>.yaml     identity · modality · source shape and vocabulary
│   └── prompts/  templates/     mirrors src/; the path is the prompt_version
│
├── data/
│   ├── raw/                     PRIVACY TIER — NOT DVC-tracked, never committed
│   │   ├── media/               content-addressed, sharded by digest prefix
│   │   └── pii_vault.jsonl
│   ├── interim/{1_data_quality,2_ai_review,3_human_review}/
│   ├── processed/   release/v1/   quarantine/{invalid,pii,human_review}/
│
├── tests/{unit,integration,e2e,fixtures}/   a profile's rule tests live with it
├── deploy/                      docker-compose Label Studio, CI config
└── docs/
```

Nothing under `pipeline/` imports a concrete modality or profile — both arrive through their registries. That is the property invariant 16 and requirement 7 exist to keep true, and it is what a new modality has to satisfy rather than negotiate.

### The two contracts

*Decisions § Two composed axes* says why there are two protocols rather than one bundle per dataset kind. This section says what each member is **for**, and records the test every member had to pass to be here: **a member exists only because a named stage cannot run without it.** The comments name that stage, so a member no stage calls would be visible as the speculative abstraction it is.

Read the two together as one sentence: a modality answers *how is this content read*, a profile answers *what is an answer about it*. Neither may answer the other's question, and that is the whole reason a new modality does not multiply the profiles that already exist.

**Every name contains its result.** Not a preference — a rule, and it applies to every function in the codebase, not only to contract members. `content_parts` returns content parts, `embedding` returns an embedding, `tools_to_catalog` returns a catalog, `build_record` returns a record. A verb goes in front only when the bare noun would be ambiguous.

What the rule rejects, and these were all real names here: `adapt`, `parse`, `of`, `label_of`. A single word that names an operation without its object means nothing read alone — `parse` parses what, into what? — and `label_of` reads backwards. Two more were worse than vague: `load` and `export` were also the names of stages 0 and 13, so a sentence mentioning either was ambiguous. **No function shares a name with a stage.**

The convention comes from the corpus generator, which already had it right: `tools_to_catalog`, `tool_to_block`, `build_system_prompt`, `to_strict_openai`, `render_params`. `X_to_Y` for a conversion, `build_X` for something assembled, `read_X` for something pulled out of a larger structure.

```python
class Modality(Protocol):
    """How content is read. Knows nothing about what an answer is."""

    name: str        # stamped onto every record it touches as
    version: str     #   producer.modality = "text@1" -- requirement 7

    # Stage 0 `load`. One raw source item -> the ordered, typed pieces of content in
    # it. The only code in the system that knows the source's own layout, which is
    # what stops fifteen stages each acquiring an opinion about how a file is shaped.
    # For a chat corpus that means one part per turn; for a call recording it would
    # mean an audio part per channel and a transcript part beside it.
    #
    # A turn carrying structure rather than a string -- a `tool_calls` array with
    # `content: null` beside it -- is still one part, rendered canonically by
    # requirement 70. Rendering, not interpreting: what a call *means* is the
    # profile's, and a modality that started reading arguments would have acquired
    # an opinion about what an answer is.
    def content_parts(self, raw: Any) -> list[Part]: ...

    # Stage 3 `embed`. Content -> one vector. Consumed by `dedup` and by no other
    # stage: it exists to find near-duplicates, not to be reported. A static embedder
    # is preferred so two runs over one corpus dedup identically.
    def embedding(self, parts: list[Part]) -> Sequence[float]: ...

    # Stage 2 `pii_check`. The detectors this *kind of content* needs -- personal data
    # hides differently in a transcript than in a waveform. High recall is the
    # contract here; precision belongs to the verifier inside the stage. The uniform
    # Span shape is why the redaction stage, its report, its vault and its gate are
    # written once rather than once per modality.
    def personal_data_detectors(self) -> list[Detector]: ...   # → list[Span] per part

    # Stage 8 `publish`. The half of the annotation config that *displays* a record.
    # A modality never emits the control that captures an answer: that half is the
    # profile's, and composing them is what makes one screen out of two contracts.
    def display_config(self, record: Record) -> UIControl: ...
```

```python
class Profile(Protocol):
    """What an answer is. Knows nothing about how content is read."""

    name: str        # stamped onto every record it touches as
    version: str     #   producer.profile = "tool_decision@1" -- requirement 7
    modality: str    # the axis it composes with. A run naming a different pair is a
                     # hard stop, never a coercion: coercing it would ship a dataset
                     # whose provenance says something untrue.

    answer_schema: dict[str, Any]   # JSON Schema for one answer. The answer's *type*,
                                    # declared rather than described, so the jury can
                                    # constrain a model with it and pandera can check
                                    # an artifact against it -- invariant 5. A compound
                                    # answer's is materialised per record, from the
                                    # catalog the record already carries, at the moment
                                    # a schema is needed -- and never persisted, because
                                    # it is bigger than the catalog it would copy
                                    # (requirement 71). One schema is the whole
                                    # answer-space constraint, which is why no stage
                                    # validates an answer by hand.

    # Stage 0 `load`. Raw item + parts -> the canonical record. Keeps every field it
    # does not own, because what looks like noise now is what a later question turns
    # out to need -- profile rule 4. `build_` and not a bare noun: `record` alone is
    # the name of the thing every function here already takes as an argument.
    def build_record(self, raw: Any, parts: list[Part]) -> Record: ...

    # Stages 5 `jury`, 6 `rank_for_review`, 10 `aggregate`. The distance between two
    # answers -- and the *only* thing the core knows about disagreement. Cohesion,
    # corpus conflict, the four triage buckets, Krippendorff's alpha over a set-valued
    # answer, adjudication and juror calibration are all written in terms of it, which
    # is what lets `shared/agreement.py` be generic without being a framework.
    # Must satisfy profile rule 1's four properties -- the one nothing generic
    # enforces. Not the triangle inequality: a compound answer's delta is a weighted
    # average, requirement 4 says which four are claimed and why the fourth is not.
    def answer_distance(self, a: Answer, b: Answer) -> float: ...

    # Stage 5 `jury`. The votes' consensus: several answers to one record -> one
    # answer, deterministically. Named for whose consensus it is, because the pipeline
    # also combines *people's* answers and that is a different operation -- annotators
    # are aggregated with Dawid-Skene weighting in stage 10, never with this.
    # Over a compound answer it is majority per name and then majority per argument,
    # and a call it could only assemble partially is dropped rather than invented --
    # requirement 74.
    # Returning None for every input is a legal declaration rather than a failure:
    # free-text generation has no defensible consensus, and inventing one would ship a
    # plausible machine-written label. It bars the optional consensus tier and nothing
    # else -- triage still works, because triage needs only `answer_distance`.
    def vote_consensus(self, votes: list[Answer]) -> Answer | None: ...

    # Stage 1 `remove_invalid`. Named checks a record passes or *provably* fails.
    # Provably: no judgment. If telling right from wrong needs a person, it is an
    # annotation task, not a validity check. The names are the quarantine filenames
    # and the keys `params.yaml` declares expected counts against.
    #
    # A name also says which *kind* of defect it is, because the two have different
    # remedies: `label_*` is a defect in the answer, which a person can fix, and a
    # bare noun is a defect in the record, which they cannot -- nobody can annotate
    # a record that offers no options. That is why `Record.failed_checks` is one
    # list: the classification is in the name, so a stage that needs the split
    # derives it, and no second field can drift out of step with the first.
    def validity_checks(self) -> dict[str, Callable[[Record], bool]]: ...

    # Stage 7 `generate_questions`. The text of one focused, answerable question about
    # this record. The profile owns the wording because only it knows what the answer
    # is; choosing *which* focus to ask about is the stage's job.
    def question_text(self, record: Record, focus: str) -> str: ...

    # Stage 8 `publish`. The half of the annotation config that *captures* an answer,
    # constrained to this record's answer space wherever the UI can express it -- and
    # asserted again at pull time, because a UI constraint is not a guarantee. For a
    # compound answer that is a name control plus per-name argument fields, with a
    # JSON text control as the declared fallback where the tool cannot express them --
    # requirement 75, which also says why which one shipped is recorded.
    def answer_config(self, record: Record) -> UIControl: ...

    # Stages 4 `dedup` and 12 `split`. What makes two records the same scenario, so no
    # group straddles a split and no metric is computed on leaked data. A field that is
    # unique per record is not a group key, and saying which field is one is the
    # profile's job -- with a measurement, not an assumption. Written at `dedup`,
    # unioned with the duplicate cluster; enforced at `split`, where a straddling group
    # fails the gate.
    def scenario_hash(self, record: Record) -> str: ...

    # Stage 13 `export`. One training example, in the shape this profile's trainer
    # expects. The last place the pipeline can assert that the answer it is shipping is
    # the answer it recorded -- profile rule 5.
    def training_example(self, record: Record) -> dict[str, Any]: ...
```

Twelve methods across the two contracts, and thirteen of the fifteen stages call at least one of them. The two that call neither are `pull`, which normalizes what annotators returned, and `document`, which reads what earlier stages already recorded — and that is the expected shape of the list, not a gap in it.

`answer_schema` may be built per record — a profile whose answer space depends on the record (a catalog, a candidate list) builds one closed over that record, **at the moment a schema is needed and never stored on it** (requirement 71). The jury passes it straight to `complete_structured`, which is why answer-space validation is not pipeline code.

**What the contracts deliberately do not own.** Each of these was a plausible member and each is somewhere better:

| Not a member | Where it lives instead | Why |
|---|---|---|
| `validate(answer)` | `answer_schema`, handed to the library | a schema the provider enforces beats a predicate the pipeline runs after the fact |
| A quality score | `answer_distance` | one distance expresses every agreement statistic; a score expresses one |
| The prompt text | `config/prompts/<axis>/<name>/<slug>.vN.txt` | a prompt is the measuring instrument, so it has to be diffable and nameable in an artifact — requirement 45 |
| Reading or writing artifacts | `file_utils` via the stage | stages own I/O; an implementation that opened a file would be a stage |
| Any threshold | `params.yaml`, `config/gates.yaml` | a number in code is not reviewable, and every run records the digest of each policy file it read |
| Its own identity | `config/<axis>/<name>.yaml` | `version` is a claim about how a dataset was made; edited as a class attribute it is a claim no review saw |

### What goes in, and what comes out

The canonical record below is the middle. This is the two ends, written as assumptions because they are what the pipeline takes on trust — and each one is why some stage or gate exists.

**In: one source file, and nothing believed about it.**

*Assumption:* a source is **one file holding one JSON array**, one element per record, readable in a single streaming pass. Its identity is the SHA-256 in `params.yaml` rather than its path, and `load` hard-stops when the two disagree — which is how running the same command over a changed file becomes a decision rather than a surprise. A record never spans two elements, and one run reads one source.

*Assumption:* **where the content is** is the modality's to know and no other module's. `content_parts` is the only code in the system that reads the source's own layout; for `text` that is one part per turn of a `messages` array.

*Assumption:* **the source's own answer is evidence, not truth.** ≥3.3% label errors in curated benchmarks is one of the four findings above, and a source that has already been relabelled once says so in its own metadata. It is carried into `label` verbatim and in source order, and every stage after `load` treats it as a claim to be checked — which is what the jury, the triage buckets and the annotators are for.

*Assumption:* **nothing else about the input is clean, and each uncleanliness gets a stage rather than a precondition.** The label may contradict the training target (`remove_invalid`), the content may carry personal data (`pii_check`), one scenario may appear many times (`dedup`), and the answer space itself may not arrive as data — a source may render it into a turn as prose, in which case reading it back is the profile's own grammar, with a byte-identical round trip over the whole source as the only acceptable proof that the reader agrees with the writer.

*Assumption:* **every corpus-specific name is declared, never spelled in code.** Which turn is the instruction, which turn restates the answer, which key holds the label, what this file calls its labelling model — all of it is `config/profiles/<name>.yaml`, read once into the profile's source contract. A module that names `llm_model` has quietly become a module about one file.

**What an already-standardised input would buy, stated so the cost of the declaration is visible.** If a source arrives in the canonical shape — the answer space as data, the pipeline's own role names, the answer at a known key — then the shape branch has one arm, no catalog grammar is needed on the way in, and the source contract shrinks to roles and a label key. The declaration is kept anyway, and the reason is not that some source will fail to be tidy: **a hand-standardised input is a transformation nobody recorded.** Requirement 14 exists to stop exactly that — provenance says which file a record came from and at which offset, and a person having reshaped it in between makes both untrue. Whatever a source does natively, the profile declares it and stage 0 performs the conversion, so the transformation is code, digested with the run.

**Out: `release/vN`, and only what a consumer can judge.**

One line per record per split, in the shape this profile's trainer expects: `training_example(record)` and nothing generic. For a conversational profile that is `{"messages": [...], "meta": {...}}`, with the answer in both the target turn and `meta.label` and the two asserted equal as the line is written — the one assertion that catches a record whose two statements of the answer have drifted apart.

```
release/v1/
├── train.jsonl  val.jsonl  test.jsonl   one training example per line
├── MANIFEST.sha256                      every file above, digested
├── run_manifest.json                    every policy file read, both axes as
│                                          name@version, every artifact written — req 69
├── datasheet.md   data_statement.md     what this dataset is made of — req 62
└── croissant.json                       validated by mlcroissant
```

The profile supplies the body; `export` adds the per-record provenance of requirement 60. The record's internal blocks do **not** travel: votes, cohesion, the triage bucket, privacy counts and the duplicate cluster stay in `interim/`, where the pipeline's own reasoning belongs. A consumer gets what was decided and how the dataset was made, not the machinery that decided it.

*Assumption:* a consumer's question is *can I train on this, and can I say where it came from* — and the three invariants that answer it are 13 (test is 100% human-validated), 12 (no group straddles a split) and 14 (two runs from a clean checkout are byte-identical). Anything the release cannot answer about itself is a documentation defect rather than a data one, which is why `document` is a gated stage and not a README.

**What the output is not.** Not a database, not an API response, and not one file per record. Fifteen stages produce JSONL and one release directory; the platform that would serve them is [`dataforce-platform`](../dataforce-platform/spec.md), deferred behind a Label Studio v0 until the first profile's pilot gate passes.

#### One item, all the way through

Concrete so it can be argued with. This is the shape **the contracts are written against** — a conversation of as many turns as it takes, a catalog offered as data, and an answer that names calls *and their arguments*. It is not a description of any one file: a source's own layout is that source's business, absorbed by the profile manifest's `shape` and roles, and any single corpus's quirks and counts belong in that profile's spec, not here.

The item is invented. That is a rule rather than a convenience: this repository is public, so no example, fixture or docstring here is ever lifted from real data.

**1 · One element of the source array, complete.**

```jsonc
{
  "id": "s4471",
  // Every turn, in order. Multi-turn is the normal case: a tool is often declined
  // once, called after the customer supplies what was missing, and called again on
  // the result. The answer is the *last* assistant turn -- what a model is trained
  // to produce -- and everything before it is context.
  "messages": [
    { "role": "system", "content": "Choose which tool(s) to call next, with arguments." },
    { "role": "user",   "content": "Cho mình xem số dư tài khoản." },
    { "role": "assistant", "content": "Bạn cho mình mã khách hàng nhé." },
    { "role": "user",   "content": "Mã của mình là 480215." },
    { "role": "assistant", "content": null,
      "tool_calls": [ { "id": "c1", "type": "function",
                        "function": { "name": "LookupBalance",
                                      "arguments": "{\"ma_khach\": \"480215\"}" } } ] },
    { "role": "tool", "tool_call_id": "c1", "content": "{\"so_du\": 1250000}" },
    { "role": "assistant", "content": "Số dư của bạn là 1.250.000 đồng. Bạn cần gì thêm không?" },
    { "role": "user",   "content": "Gửi giúp mình sao kê tháng này qua email." },
    // the target: the call this record teaches, with the arguments it teaches
    { "role": "assistant", "content": null,
      "tool_calls": [ { "id": "c2", "type": "function",
                        "function": { "name": "SendStatement",
                                      "arguments": "{\"ma_khach\": \"480215\", \"ky\": \"thang_nay\"}" } } ] }
  ],
  // The catalog: what this record offered, as data. Standard OpenAI function objects,
  // so `parameters` is a JSON Schema and is what an argument is checked against.
  "tools": [
    { "type": "function",
      "function": { "name": "LookupBalance",
                    "description": "Tra cứu số dư tài khoản của khách hàng.",
                    "parameters": { "type": "object",
                                    "properties": { "ma_khach": { "type": "string" } },
                                    "required": ["ma_khach"] } } },
    { "type": "function",
      "function": { "name": "SendStatement",
                    "description": "Gửi sao kê cho khách hàng qua email.",
                    "parameters": { "type": "object",
                                    "properties": { "ma_khach": { "type": "string" },
                                                    "ky": { "type": "string",
                                                            "enum": ["thang_nay", "thang_truoc"] } },
                                    "required": ["ma_khach", "ky"] } } },
    { "type": "function", "function": { "name": "OpenTicket", "…": "…" } }
  ],
  // Whatever else the source carries. Kept verbatim and read only where the profile
  // manifest declares a meaning for a key -- what labelled this, whether a person has
  // checked it, which scenario it came from.
  "meta": { "label_source": "…", "human_checked": true, "scenario": "…" }
}
```

**2 · What `load` adds before the profile sees it.** Not in the source file, and required rather than defaulted — a record without provenance cannot be constructed at all.

```jsonc
"__provenance__": {
  "source":   { "file_sha256": "7c0d4e19b2a8f3", "offset": 4471,
                "ingested_at": "2026-08-21T09:14:02Z" },
  "producer": { "modality": "text@1", "profile": "tool_decision@1" }
}
```

**3 · The canonical record.**

```jsonc
{
  "rid": "…",                         // sha256 over the content parts' digests, in order
  "source":   { "file_sha256": "7c0d4e19b2a8f3", "offset": 4471, "ingested_at": "…" },
  "producer": { "modality": "text@1", "profile": "tool_decision@1" },
  // One part per turn, in order. `type` is the four-value closed set and nothing
  // else: text | image | audio | video. A turn that arrived as a `tool_calls`
  // array is a *text* part holding canonical JSON -- requirement 70 -- because a
  // call is not a kind of content, and a `call` type would oblige the text
  // modality to know what one is.
  "content": [ { "type": "text", "role": "system",    "text": "…" },
               { "type": "text", "role": "user",      "text": "…" },
               { "type": "text", "role": "assistant", "text": "…" },
               { "type": "text", "role": "user",      "text": "…" },
               // the call, canonically: keys sorted, no insignificant whitespace
               { "type": "text", "role": "assistant",
                 "text": "[{\"arguments\":{\"ma_khach\":\"480215\"},\"name\":\"LookupBalance\"}]" },
               // the tool's own result, byte-for-byte as the source spelled it --
               // it was already a string, so requirement 70 does not touch it, and
               // normalising it would change what `rid` is computed over. A role the
               // manifest declares no meaning for: embedded, displayed, not read
               { "type": "text", "role": "tool",      "text": "{\"so_du\": 1250000}" },
               { "type": "text", "role": "assistant", "text": "…" },
               { "type": "text", "role": "user",      "text": "…" },
               // the target turn: the last one carrying `roles.target`
               { "type": "text", "role": "assistant",
                 "text": "[{\"arguments\":{\"ky\":\"thang_nay\",\"ma_khach\":\"480215\"},\"name\":\"SendStatement\"}]" } ],
  // no `answer_space`. The profile settles the answer *type* and this record's own
  // catalog settles the space, so a stored copy would be a second representation of
  // one of them -- requirement 71. What needs the names reads the catalog; what needs
  // a JSON Schema materialises one from the record and does not persist it
  // the same answer the target turn states, read from where the source states it.
  // Twice on purpose -- see below
  "label": [ { "name": "SendStatement",
               "arguments": { "ma_khach": "480215", "ky": "thang_nay" } } ],
  "meta":  { "…": "verbatim from source" },
  "parse_status": "ok",
  "failed_checks": [],
  "privacy": null, "conversation_cluster": null, "conversation_cluster_size": null,
  "scenario_hash": null,
  "jury": null, "triage": null, "validation": null, "split": null
}
```

Every block after `failed_checks` is `null` because the stage that owns it has not run. That is the shape of a record leaving stage 1, and no later stage removes a field.

**Why the answer appears twice.** `label` and the target turn hold the same value, and that redundancy is load-bearing rather than sloppy: it is the *only* thing that makes a mismatch detectable. A source states its answer once as a field and once as the content the model is trained to produce, the two can disagree, and `label_assistant_mismatch` is the check that reads both and compares them through δ. On the reference source it found 48 records where they differed — records that would have trained a model on the losing side of two disagreeing sources. Collapse the two into one and the check has nothing to compare.

They also stop being the same value later, which is the second reason both exist. `label` is the *source's* claim and is never rewritten; a human correction lands in `validation.curated_label` at stage 11; and `content` is never rewritten either, so `rid` — a digest over the content parts — stays stable across a relabelling. Three fields, three different claims about the answer, and `export` is where they are reconciled into the one line that ships.

**`tool` is a role, not a part type.** The four-value closed set is about *kinds of content*; `role` is a free string the source chooses, and a `tool` turn is text like any other — it embeds, it displays, and `rid` covers it. What it does not have is a *declared meaning*: the profile manifest names three roles (`instruction`, `conversation`, `target`), so no check and no stage may read a `tool` turn by meaning. It is carried because it was in the conversation, and nothing more is claimed about it.

**4 · The four validity checks, on this item.** The answer's calls name tools the record offered; each call's arguments satisfy that tool's `parameters`, `ky` inside its `enum`; the catalog is non-empty; one call is within the declared ceiling. Nothing fires, so the record stays on the main path. Any one of them failing writes it to `quarantine/invalid/<check>.jsonl` — named, not deleted, and re-admitted by `dataforce requeue --check <name>` once the cause is fixed.

**5 · The exported line**, after annotation:

```jsonc
{ "messages": [ "…every turn, unchanged…",
                { "role": "assistant", "content": null,
                  "tool_calls": [ { "id": "c2", "type": "function",
                                    "function": { "name": "SendStatement",
                                                  "arguments": "{\"ma_khach\": \"480215\", \"ky\": \"thang_nay\"}" } } ] } ],
  "meta": { "…": "the record's meta", "label": [ { "name": "SendStatement", "arguments": { "…": "…" } } ] } }
```

The answer is in two places — the final turn and `meta.label` — and they are asserted equal as the line is written. That assertion is at export and not only at ingest because the answer can change at stage 11, and it has to hold on the answer that ships.

#### The distance between this shape and the code

Stated because the gap is the plan's, not the reader's to discover. Each line below was run:

| The shape needs | Today | Verified |
|---|---|---|
| A turn that carries a call rather than a string | `content_parts` reads `turn["content"]` and builds a `TextPart` | `ValidationError` on `"content": null`, `KeyError` when the key is absent |
| An answer of `(name, arguments)` | `answer_schema` is an array of strings | an argument-carrying label is quarantined by two checks — reported, run continues |
| δ over `(name, arguments)` | `answer_distance` is Jaccard over names, and raises on anything else | `TypeError` by design: `_tools` refuses to compare a shape it cannot mean |
| `role: "tool"` as a declared role | three roles are declared: instruction, conversation, target | it embeds and displays; it is simply not named, so nothing may read it by meaning |

Only the first is mechanical. The other three move the **answer type**, and the answer type is what the generic core is written in terms of — δ, `vote_consensus`, the capture control, `training_example` and every count that today means "names". None of it is `pipeline/` or `shared/` work, which is the two-axis design paying off: it is one profile declaring a richer answer, with its own δ and its own consensus rule per parameter. What it cannot be is a widened version of a names-only profile, because a δ that has to weigh a disagreement about one argument value against a disagreement about the tool is a decision, and every triage bucket and α inherits it.

### Canonical record

One shape flows through every stage; each stage adds fields and removes none.

**Why one shape rather than one table per stage, joined on `rid`.** Four reasons, and the first is the one that decides it.

- **Invariant 1 is a count, and a join is where rows go missing.** `output + quarantined + deduped_out == input` is only checkable when a stage's output rows *are* its input rows plus fields. Under a join, a dropped row and a failed match are the same observation.
- **Several stages read across earlier ones.** A triage bucket is a function of the jury block, the validity list and the duplicate cluster at once; the pilot gate reads gold, validation and jury together. Every one of those would be a join written by hand, in a stage whose subject is something else.
- **A record that leaves the main path has to stay self-describing.** `quarantine/invalid/<check>.jsonl` is read by a person with nothing to join against, and the same is true of `quarantine/pii/` and a failed gate's offending ids. Which is why **one field answers "why is this record not on the main path"** — `failed_checks`, appended to by whichever stage withheld it, never one field per stage. Three stages ask that question and a reader who has to check three differently-shaped fields is a reader who will check two of them.
- **Adds-and-never-removes makes the schemas additive.** `loaded.jsonl` and `curated.jsonl` are the same type at two points in one record's life, so artifact schemas stay non-strict and a later stage cannot invalidate an earlier stage's validation. It is also what lets one named stage be re-run without rewriting another's output.

Every block below has exactly one owning stage, named in the comments. The one shared block is `validation`, opened by `aggregate` and completed by `curate` — two stages of one loop, never two writers racing.

```jsonc
{
  // stage 0 `load` -- identity and provenance, written once and never rewritten.
  // `rid` comes from the content parts' digests in order, so re-ingesting a shuffled
  // source yields byte-identical ids (invariant 2); `producer` is the resolved pair,
  // so a dataset cannot silently change the code that made it (requirement 7).
  "rid": "9f2c…",
  "source":   { "file_sha256": "…", "offset": 1043, "ingested_at": "2026-08-18T…" },
  "producer": { "modality": "text@1", "profile": "tool_decision@1" },

  // stage 0, from the modality's `content_parts`. An ordered list of typed parts
  // rather than a string: one of the three things that could not be retrofitted
  // without touching all fifteen stages, so it is settled before stage one exists.
  "content": [
    { "type": "text",  "role": "system", "text": "…" },
    { "type": "text",  "role": "user",   "text": "…" },
    // a turn that arrived as a `tool_calls` array, rendered canonically -- one form
    // per value, so `rid` is reproducible (requirement 70, invariant 2)
    { "type": "text",  "role": "assistant",
      "text": "[{\"arguments\":{\"ma_khach\":\"480215\"},\"name\":\"LookupBalance\"}]" }
    // a voice profile would add, with no other change to any stage:
    // { "type": "audio", "role": "user", "uri": "media/ab/abc123.wav",
    //   "sha256": "abc123…", "duration_s": 12.4, "transcript_part": 1 }
  ],
  // stage 0, from the profile's `build_record`. The two fields it owns: the answer,
  // and everything the profile does not own -- kept verbatim, because what looks like
  // noise now is what a later question turns out to need.
  "label": "…",                        // the profile's answer type. What an answer may
                                       // *be* is derived from this record, never stored
                                       // beside it -- requirement 71
  "meta": { "…": "verbatim from source" },

  "parse_status": "ok",   // stage 0: ingest drops nothing, so an unparsable record is
                          // here too, flagged rather than absent
  // stage 1 `remove_invalid`: the names of the checks that fired. Non-empty means the
  // record is in quarantine, with the check name as its filename. One list rather than
  // one per kind of failure -- the check name already says which kind it is, and "is
  // this record on the main path" has to stay one condition no stage can half-remember
  "failed_checks": [],
  // stage 2 `pii_check`: the *evidence*, one entry per span -- which part held it,
  // where in that part, which class it is, and the placeholder it became. Counts and
  // the class set are derived from this, not stored beside it. The matched *text* is
  // never here: that text is the personal data, and `<PHONE_1>` -> original lives in
  // the untracked vault, keyed by placeholder, for whoever is entitled to it. Not the
  // verdict either: a record this stage withheld says so in `failed_checks`
  "privacy": { "spans": [ { "part": 1, "type": "PHONE",
                            "locator": { "start": 42, "end": 52 },
                            "placeholder": "<PHONE_1>" } ] },
  // stage 4 `dedup`: cluster members are marked, never deleted, so the decision stays
  // reversible and recorded. `scenario_hash` is the profile's, unioned with the cluster, so
  // variants of one scenario cannot straddle a split. Deliberately *not* a
  // `failed_checks` entry: a duplicate is not withheld, it stays on the main path and
  // is filtered at export by an explicit choice -- which is why the conservation gate
  // counts `deduped_out` as its own term rather than folding it into `quarantined`.
  "conversation_cluster": "c_0331", "conversation_cluster_size": 112,
  "scenario_hash": "g_7a1e…",

  // stage 5 `jury`: every vote kept, including abstentions, because an abstention is
  // evidence about a juror. `panel_version` and `prompt_version` are here so a number
  // can be attributed to the panel and prompt that produced it.
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
  // stage 6 `rank_for_review`: why a human is being asked about this record, and under
  // which sampling stratum -- so the design stays reconstructible (invariant 15).
  "triage": { "bucket": "agreed", "strata": ["audit"] },

  // stages 10 `aggregate` and 11 `curate`: what people decided, who decided it, and
  // whether it counts toward alpha. `curated_label` is the only label a release ships
  // from a human; `jury_consensus` records are barred from test permanently.
  "validation": { "status": "corrected", "verdict": "incorrect", "curated_label": "…",
                  "validators": ["u12","u07"], "alpha_contrib": true, "decided_at": "…" },
  "split": "test"   // stage 12: assigned by `scenario_hash`, never at random
}
```

The second vote is what an abstention looks like: `ok: false`, `answer: null`, and the library's own `error` and `raw` retained. Nothing about it is a partial answer.

## Decisions

**Two composed axes, not one bundle per dataset kind.** *Alternatives:* one plugin supplying all eleven pieces; a full stage graph forked per modality. *Why:* a bundle makes a voice classification dataset and a voice tool-decision dataset each re-declare the same audio loader, embedder, and privacy detectors — the duplication lands exactly where correctness matters most. Forking the stage graph per modality copies fifteen gates, and gates that exist in two places drift. Composition means a new modality is one implementation that every existing profile can immediately use. *Reversible:* yes, and cheaply, since both are protocols resolved from a registry.

**The generic core is `(answer, answer_distance, vote_consensus)`.** *Alternatives:* a per-task pipeline; a task-type enum branched on inside each stage. *Why:* this is what the machinery actually needs. Cohesion, conflict, the four buckets, α, adjudication, and juror calibration are all expressible in those three terms, so genericity here is an interface rather than a framework — which is the difference between a cheap abstraction and a speculative one. *Reversible:* no in practice, and it should not be: it is the whole thesis.

**A profile may declare `vote_consensus = None`.** *Why:* free-text generation has no defensible consensus, and inventing one would produce a plausible machine-written label that the optional tier could ship. Declaring the gap keeps such profiles fully supported for triage — where they are genuinely useful — while making the one thing they cannot do explicit. *Reversible:* a profile can gain a consensus later; nothing depends on its absence.

**A module holds one step of the workflow — and merging stops where the consumers differ.** *Alternatives:* one file per concern, which is what was built first: a profile of nine modules where four were under ninety lines, and fourteen schema modules of which eleven describe stages that do not exist. The opposite extreme — one module per package, `shared/artifacts.py` holding all twelve artifact schemas — was drafted and rejected. *Why:* two rules pull against each other and both are load-bearing.

*Group what changes together.* The reader of this codebase follows a **path** — how does one record get from the source file to a training example — so a file per concern charges ten navigations for one step. Everything stage 0 and stage 1 do belongs in `build_record.py`, and the three modules that read the source changed together every time the source changed.

*And a module is a definition or a step, never both.* A **definition** module defines one noun — `schema.py` is every shape this profile's data has, `source_contract.py` is what one corpus calls things — and a **logic** module holds every conversion of one: `utils.py` is the six ways a catalog is written or read, `answer.py` the distance between two answers, the consensus of several, and the row a trainer wants. A definition is *supposed* to be used by many steps: one used in a single place is not a definition, it is that step. A **step** module is used by exactly one step of the flow and by nothing else, which is why `validity_checks` has no file of its own — it serves stage 1 alone, so it lives beside the stage-0 code that produces what it checks. This is what answers "why does one file turn up in four different states": only definitions and their conversions do, there are five such modules, and each is named for the noun or for the job.

*And never make a consumer depend on what it does not use.* This is what kills the single-module version. Fifteen stages under `pipeline/` import from `shared/`; if all twelve artifact schemas sit in one module, then `data_quality/load.py` and `release/document.py` import the same file, and editing the release schema puts every stage in the blast radius. So `shared/schemas/` stays a package and is divided by **pipeline phase** — the boundary along which artifacts actually change and along which stages actually import. Fourteen modules become six, and `load.py` imports `schemas/data_quality.py` and nothing else. `schema_for(name)` still resolves all of them by name, for the round-trip test that must iterate every artifact; a stage never uses it.

The same test keeps `manifest.py` and `prompts.py` apart inside `declared/` despite both being "things read from `config/`": a caller that wants a prompt has no business importing manifest loading. It is also the one rule the layering overrides. A definition owning every conversion of its noun would put `Manifest` and the code that reads one in a single module, but invariant 18 forbids the engine importing `declared/` and three engine modules need the type — so the shape is `shared/manifest.py` and the reader is `declared/manifest.py`, and where the two rules disagree the layering wins. And `utils.py` holds one grammar rather than one copy per consumer for the same reason: a *format* copied into each of the places that reads it is two sources of truth.

The second deviation is `schema.py`, and it is a convention rather than a conflict: **a profile's schemas live in one `schema.py` in the profile's own folder.** By R2 as written, what an answer looks like and what is computed from one are one noun and belong in one module. They are split because the schemas are read as a group and by different readers — the jury hands `answer_schema_for(record)` to `complete_structured`, the annotation UI constrains a control to the same names, and the first thing an author of a second profile needs is the shape their answers must have, not the metric over them. One file per profile folder is where that group is looked for. Nothing in `shared/schemas/` moves with it: those twelve are artifact schemas, and not one of them names anything a profile owns — `label` is `pa.Column(object)` precisely so that what a label *is* stays the profile's.

The convention has a second half, and it is what split `tool_schema.py`: **a shape is a shape, and turning one thing into another is logic.** So `schema.py` holds the `Tool`, `Catalog` and `Gap` types beside the two answer schemas, and `utils.py` holds every conversion over them — which is why the docstring prefixes gained a fourth word, `LOGIC ·`, beside `DEFINITION ·`, `STEP ·` and `TOOL ·`. The grammar itself was *not* split: rendering a catalog and reading one back are still one module, because the byte-identical round trip over 21,172 corpus catalogs is the proof the two directions agree, and it only reads as one proof while they sit together. `schema.py` is now the most-imported module in the profile — four importers against `utils.py`'s three — which is the check that the seam was a real one.

*The cost:* the file count falls less than a flat merge would give — 49 to 30, not 21. *Reversible:* yes, and splitting later is cheaper than merging, because a merge is what proves two halves belonged together.

**A source's vocabulary is declared once, and everything derivable is derived.** *Alternatives:* declare each fact where it is read, which is what the first manifest did — it carried both `roles.target: assistant` and `label.restated_in: target`, and a dotted path `label.at: meta.label` beside a `meta:` block that named every other field as a bare key. *Why:* two keys stating one fact can disagree, and the manifest is hand-edited — the moment one is deleted the other is a lie that no type checks. The target role *is* the turn the answer is restated in, because it is the content the model is trained to produce, so the restating turn is a property computed from `roles.target` rather than a key. And a path grammar buys nothing when every field this source names is a key in `meta`. *The cost:* a future source that restates its answer somewhere other than the target turn, or states it outside `meta`, needs a new key added here — which is the right time to think about it, rather than now. *Reversible:* yes, and cheaply; both were removed by deleting code, not by adding it.

**Every contract member is named for what it returns.** *Alternatives:* verb names (`load`, `adapt`, `export`); the mathematical symbol (`delta`). *Why:* a contract member is read far more often than written, and the reader has only the name and the signature. `adapt` names an activity so general it excludes nothing, and `load`/`export` were also stage names — one word meaning two things in one system, which is how a reviewer ends up unable to tell whether a sentence is about a stage or a method. Naming for the return value gives every member a falsifiable name: `content_parts` returning something that is not content parts is visibly wrong. *The cost:* `answer_distance` is longer than `δ`, and the symbol survives only in the α formulas where it is standard. *Reversible:* yes, and this is the cheapest moment it will ever be — after Phase 3 there are fifteen stages calling these names.

**Profile rules are stated for the author, not enforced by a shared suite.** *Alternatives:* a generic conformance suite run at registration — which is what was built first, and removed; checking at first use. *Why:* the suite was 392 lines to check five properties, and 95 of those were machinery for inventing sample answers out of an arbitrary JSON Schema — code written for profiles that do not exist, which is the definition of speculative. The five properties are short enough to state in prose and each profile can prove them over its own answer type in a test module it owns, where the assertions read in that type's own terms rather than through a generated sample. *The cost, stated plainly:* nothing now fails when a profile breaks a rule. A `answer_distance` that is not a metric produces cohesion numbers that look fine and mean nothing, and it surfaces as a bad ranking rather than a red build. That cost is accepted because a rule the author is told to follow is the author's responsibility, and because the alternative was paying 392 lines and an import-time exam to insure against a mistake in code nobody has written yet. *Reversible:* yes — the rules are written so a suite could be built from them later, and the first profile to arrive without its own tests is the signal to do it.

**A call is carried as a canonically-rendered text part, not as a new part type.** *Alternatives:* a `call` value in the part type's closed set; a separate `calls` field on the record beside `content`. *Why:* the part type discriminates *kinds of content* — `text | image | audio | video` — and a tool call is not a kind of content, it is something the profile understands. Adding `call` would oblige the text modality to know what a call is, which is the one thing the two-axis split exists to prevent; a `calls` field beside `content` is worse, because the call's position in the conversation is load-bearing and a parallel field loses the ordering. Rendered as canonical JSON in a text part, a call is a turn like any other: `rid` covers it, `embedding` sees it, `display_config` shows it, and the profile parses it because the profile is what declares the answer type. *The cost:* the canonical form is now load-bearing for `rid`, which is why requirement 70 specifies it and invariant 2 tests it. *Reversible:* yes before any artifact exists, and only then.

**δ over a compound answer is soft, and the shape of the softness is specified here.** *Alternatives:* Jaccard over names alone, ignoring arguments; Jaccard over `(name, arguments)` treated as one atom. *Why:* ignoring arguments makes two jurors who agree on every tool and disagree on every value look unanimous — it discards exactly the signal a function-calling dataset is about. Treating the pair as an atom makes "right tool, one argument differs" identical to "wrong tool", which collapses the distinction the triage buckets exist to draw: the first is a record worth one annotator minute, the second is a label error. Name-first with per-argument agreement keeps them apart and reduces to Jaccard over names when arguments agree, so the names-only behaviour that was measured end to end is the special case rather than something replaced. *The cost, stated plainly:* the weighted form loses the triangle inequality, and the mean over the union of names is a choice — a record whose answer has one call weights that call's arguments as heavily as a record with four calls weights each of its own. Both are written into requirement 4 and requirement 72 rather than left to be discovered from a cohesion figure that looks wrong. *Reversible:* yes; it is one function with the profile's own tests around it, and the four properties are what any replacement must also satisfy.

**One call per tool name per answer, enforced by a check.** *Alternatives:* a multiset answer with pairwise matching before comparing arguments; silently keeping the last call for a repeated name. *Why:* matching two calls to one tool is a second decision δ would have to make invisibly, and the wrong match produces a confident number. Keeping the last is data loss disguised as normalisation. A check that fires puts the record in front of a person, which is the correct response to an answer the profile cannot yet mean. *The cost:* a source that genuinely means parallel calls to one tool cannot be ingested without lifting this, and the day that source arrives is the day requirement 72 gains a matching rule. *Reversible:* yes — removing the check and adding the rule, in that order.

**Content parts say `type`, the same word every provider uses.** *Alternatives:* `kind`, a name reserved for us so it could never be mistaken for a provider's field. *Why:* an ordered array of typed parts is how OpenAI, Anthropic and Gemini all model content, and all three call the discriminator `type` — so `type` is the field an engineer already recognises, which is worth more than avoiding a collision that cannot actually happen. The values disambiguate on their own: ours are closed and bare — `text | image | audio | video` — where OpenAI's are `input_text` / `input_image` / `input_audio` and Anthropic's differ again, so `"type": "audio"` is unambiguously a DataForce part. No provider's JSON is ever stored: a profile's `training_example` produces it, mapping both the value and its nesting to whatever that provider wants — ours keeps the payload flat on the part, where OpenAI nests it under a key repeating the type. The one real cost is that `type` shadows a Python builtin if a part is ever modelled as a dataclass attribute rather than a mapping key; that is a lint note, not a bug. *Reversible:* yes, but only before any artifact exists.

**The record has no `answer_space` field. Reversed, with the measurement that reversed it.** *Alternatives, both of which this document previously specified:* materialise the full per-record JSON Schema onto the record; store the names as a cheap index and derive the rest. *Why the reversal:* the case for storing anything was that deriving means re-parsing a rendered catalog in every stage that reads a name. Measured, that is **0.27 µs** per record where the source carries its catalog as data — 0.0 seconds across 21,172 records — because there is nothing to parse; and where a source does render it into prose, the parse belongs at stage 0, which already does it, so it is paid once rather than per stage. The cost the field was buying protection against does not exist on the shape this pipeline is for.

What the field cost instead: a second representation of the catalog that can disagree with the first, an artifact column on every record of every artifact, a name that says *answer space* for something every consumer read as a *catalog index* — `record.answer_space["items"]["enum"]`, a name list mined out of a JSON Schema — and, under a compound answer, a copy larger than the original. It also does not survive its own generalisation: a compound answer space is `oneOf` with `const`, and there is no `enum` path to mine, so every consumer would have been rewritten anyway.

*Why it took three passes to see:* each earlier version was defended on a cost that had never been measured. The rule that settles it was already in this document — *a source's vocabulary is declared once, and everything derivable is derived* — and the answer space is derivable from the record by definition, because everything the profile knows about a record is on the record. *The cost of the reversal:* reading a name now needs the source contract, so `catalog_names(record)` gains a parameter and moves beside the catalog grammar; and a source that renders its catalog into prose has exactly one place that may parse it, stage 0, with a test that no later stage does. *Reversible:* yes, and the field would come back as the catalog rather than as a schema.

**Media by reference and checksum, never inlined.** *Alternatives:* base64 in the JSONL; a parallel manifest keyed by `rid`. *Why:* artifacts must stay streamable and diffable, and inlining a video corpus makes both impossible. Content addressing also gives deduplication and integrity checks for free. *Reversible:* no — this is the decision that has to be right before the first line of code, and it is why it is specified now rather than with the first non-text modality.

**Non-text modalities are a seam, not an implementation.** *Alternatives:* build image support now; leave modality unmodelled and refactor later. *Why:* building now spends real effort on requirements nobody has stated, and the pipeline's value is proved by shipping one dataset first. But three things could not be retrofitted without touching all fifteen stages — typed content parts, media by reference, and a uniform privacy-span shape — so those are in now and the rest waits. *Reversible:* the seam is cheap to widen; the record shape would not have been cheap to change.

**Invalid records are quarantined, never auto-repaired.** *Alternatives:* resolve contradictions by preferring one source; truncate out-of-space labels. *Why:* both are guesses about which of two disagreeing sources is right, applied at scale, invisibly. A quarantine file is a morning's work and a permanent record of what was decided; an auto-repair is a data cascade with a clean-looking count. *Reversible:* re-admission is an explicit command that versions the pipeline.

**Privacy is replaced with stable placeholders, not deleted or hashed.** *Alternatives:* delete the span; hash it; drop the record. *Why:* for many tasks the ground truth turns on whether a value was *supplied*, and deleting it silently inverts the label. A stable typed placeholder preserves suppliedness and co-reference while carrying no personal data. *Reversible:* only from the vault, which never leaves the raw tier.

**`data/raw/` is outside DVC.** *Why:* the vault must never be tracked, and the only cheap way to check that is for the whole directory to be outside DVC — a per-file exclusion is a line someone deletes by accident. The source loses nothing: its identity is a SHA-256 the ingest gate already asserts. *Reversible:* no, deliberately.

**The test split is 100% human-validated, at any budget.** *Alternatives:* validate a sample of test; let jury consensus fill it. *Why:* every number a release reports is computed on test, so a machine-labelled test split measures agreement with a model rather than correctness, and nothing downstream recovers from that. *Reversible:* no.

**DVC versions data; it does not orchestrate.** *Choice:* no `dvc.yaml` stage DAG and no `dvc repro`. `api/` sequences the stages in-process, and a dataset is versioned when a person decides it is worth versioning, with `dvc add`. *Alternatives:* DVC keeps both jobs with `pipeline/` stages as thin shells over `api/`; DVC orchestrates and `api/` is a second path; Airflow/Prefect; Celery; a shell script. *Why:* a DVC stage is a process invocation, so if DVC orchestrates then `api/` is permanently a *second* path that has to be kept in step with the one the tests exercise — one behaviour with two implementations. Decided when `dvc.yaml` declared zero stages, which is the only moment it is free. *What it costs, stated once:* stage-level caching. `dvc repro` skipping an unchanged stage was free and now nothing is. The expensive case is partly covered because stage 5's vote cache on `(rid, model, prompt_version)` was always planned independently of DVC, and naming stages lets a person re-do one without re-doing the corpus; if a stage becomes slow enough to need real caching the fix is a content-addressed cache inside that stage, not a DAG above it. *Reversible:* yes — every stage stays a pure function from records to records, so a `dvc.yaml` calling `dataforce run <stage>` could be added later without touching one of them.

**The engine receives parsed data, never a path.** *Alternatives:* the engine keeps reading YAML but every path is an injected parameter; leave it as it was, with `Path("config")` at module level. *Why:* injected paths still put the filesystem inside the engine, so an `api/` caller must materialise config on disk and no engine module can be tested without a tmpdir. It is also what made the library only work from the repo root: both axes were constructed at import time off a relative path. *Reversible:* yes, but going back re-introduces the working-directory dependency that made `api/` impossible.

**`api/` is a Python surface; HTTP is a later task over it.** *Alternatives:* FastAPI now. *Why:* an HTTP layer over a surface that does not exist yet fixes its request shapes before the surface is known, and forces an auth decision this spec has no input for. *Reversible:* n/a — it is additive, and the engine does not change when it arrives.

**Label Studio, not Argilla, and not our own UI yet.** *Why:* Argilla has shipped no functional change in seventeen months. Building our own UI first inverts the order of risk — it spends a quarter before anyone has answered whether the questions are answerable. *Reversible:* yes; Label Studio is touched only by `human_review/labelstudio/`.

**Assumption:** Label Studio Community honours `maximum_annotations`. The smoke rung verifies it before anything is built on it; if it does not hold, overlap comes from one project per annotator joined on `rid`.

**Assumption:** every token figure is an estimate until `agent-toolkit` surfaces `usage` on `Completion`. Budgets carry declared headroom and runs label their figures "estimated".

### Rules a profile must satisfy

Five properties the pipeline assumes of every profile. They are not checked by any shared code — see *Decisions* for why, and for the cost. Each profile proves them in its own test module; `tests/unit/test_answers.py` under the profile's own tests is where `tool_decision` does it.

| # | Rule | Why the pipeline needs it | Symptom when it is broken |
|---|---|---|---|
| 1 | **`answer_distance` is a metric.** `d(a,a) = 0`, symmetric, in `[0,1]`, never `NaN` — including on the empty answer, which for some corpora is a third of the corpus. | Cohesion, corpus conflict, the four triage buckets and α are all mean distances. A distance that is not a metric makes each of them a number with no meaning. | Nothing fails. Cohesion looks plausible, the review queue is ranked wrongly, and α is reported to three decimal places. This is the expensive one. |
| 2 | **`vote_consensus` is deterministic**, and returns the unanimous answer when every vote agrees. | The optional consensus tier may write a label from it, and a label that changes between runs is not reproducible — invariant 14. | Two runs produce different datasets from one commit. |
| 3 | **An answer survives a JSON round trip.** `json.loads(json.dumps(a)) == a`, and `answer_distance` treats the result as equal to the original. | Every artifact is JSONL. An answer that is a `set` or a tuple comes back as something else, and every distance computed after the round trip is wrong. | Distances become non-zero between a vote and itself, one stage later. |
| 4 | **`build_record` preserves every field it does not own.** Anything in the raw item that is not `content`, the answer, or the answer space lands in `meta` verbatim. | What looks like noise now is what a later question turns out to need; the corpus profiler counts fields nothing yet reads. | A field is silently gone, and only a re-ingest from the source recovers it. |
| 5 | **`training_example` reproduces the answer the record carries.** The exported example states the same answer as `record.label`, in whatever place that profile's trainer expects it. | It is the last point at which the pipeline can notice it is shipping a different answer from the one people agreed on. | A release trains on the wrong labels. For `tool_decision` this fired on 48 records before the source was fixed. |

A profile with no defensible consensus returns `None` from `vote_consensus` for every input, including unanimous input. That is a declaration rather than a failure of rule 2: it bars the profile from the optional consensus tier and nothing else, since triage needs only `answer_distance`.

## Invariants

1. **Nothing is lost between stages.** `output + quarantined + deduped_out == input`, asserted on every stage and written to `metrics.json`.
2. **`rid` is stable.** Re-ingesting the same source yields byte-identical `rid` values regardless of order, and a turn that arrived as structure renders to one canonical string whatever spelling the source used. *Check:* shuffle a fixture, re-ingest, compare; plus one fixture carrying the same call with reordered keys and differing whitespace, asserting one `rid`.
3. **No personal data downstream of `pii_check`, and the vault is untracked.** *Check:* a gate scanning every release-tier file, plus a repo test asserting the vault is in `.gitignore`, in no `.dvc` file, and that `data/raw/` is absent from DVC entirely.
4. **No media is inlined.** No artifact under `interim/`, `processed/`, or `release/` contains a base64 blob or a non-text part without a `uri` and `sha256`. *Check:* a schema assertion on every artifact carrying content.
5. **Every answer is inside the profile's answer space.** Every vote, correction, and exported label validates against `profile.answer_schema` — for a compound answer that means each call's name is in the record's catalog *and* its arguments satisfy that tool's parameter schema, requirement 71. *Check:* pandera on every artifact carrying an answer, plus the pull gate on a human correction — a second line of defence behind the schema the jury already passed to the library.
6. **Every juror vote is valid or an abstention.** No stored vote is a truncation of a malformed response. *Check:* structurally guaranteed by `complete_structured` returning `None`, plus a test feeding malformed, prose-wrapped, over-long, and out-of-space responses through a stubbed endpoint.
7. **Votes are reproducible and key-independent.** *Check:* two cold runs over a fixture against a recording proxy, diffed; a test forcing key rotation mid-run and diffing the votes.
8. **The panel is diverse, measured, and clean.** ≥3 jurors, ≥3 distinct families, no `"unknown"`, no corpus-family juror unless tagged `control`. *Check:* the jury gate reads the panel config and calls `model_family` on every juror.
9. **`answer_distance` satisfies profile rule 1's four properties.** For every profile: `d(a,a) = 0`, symmetry, range `[0,1]`, no `NaN`, including on the profile's empty answer. Not the triangle inequality — requirement 4 says why it is excluded and what would have to change to need it. *Check:* the profile's own test module, over random answer pairs drawn from its answer schema, plus for a compound answer the two cases that are the whole point: a differing name is farther than a differing argument, and identical arguments reduce δ to Jaccard over names. This is the one invariant in this list that nothing generic enforces, which is why it is rule 1 and why the cost of breaking it is written down.
10. **No model output reaches an annotator.** *Check:* a contract test asserting the payload key set equals an explicit allowlist.
11. **Corrections stay in the answer space.** *Check:* structurally where the UI can express it, and asserted again at pull time.
12. **No group spans splits.** No `scenario_hash` in more than one of train/val/test, nor in a subsample absent from train. *Check:* set intersection in the split gate.
13. **Test is fully human-validated.** Every test record has `validation.status ∈ {original, corrected}`. *Check:* export gate.
14. **Releases are reproducible.** Two `dataforce run` invocations from a clean checkout produce byte-identical artifacts. *Check:* CI on the smoke fixture, diffing the run manifest and `MANIFEST.sha256`.
15. **The sampling design is reconstructible.** Every annotated record records its stratum and selection probability. *Check:* the residual-error estimator refuses to run when any lacks one.
16. **The core is task-agnostic and modality-agnostic.** No module under `pipeline/` or `shared/` imports a concrete profile or modality. *Check:* an import-graph test over the source tree.
17. **The library is not re-implemented.** No module defines a hash helper, a JSONL reader or writer, an atomic-write context manager, a JSON-from-text extractor, a template filler, or a retry wrapper; `openai`, `tenacity`, `tiktoken`, and `jsonschema` appear in no pipeline import. *Check:* a lint test over the source tree.
18. **The engine touches no filesystem.** No module under `modalities/`, `profiles/`, `pipeline/` or `shared/` opens a file, names a config or data location, or imports `agent_toolkit.file_utils`; and none of them imports `api/` or `declared/`. *Check:* an AST guard over the source tree, asserting the guarded set is non-empty so it cannot pass vacuously.
19. **Importing the engine reads nothing.** *Check:* a subprocess importing a concrete profile with a working directory that is not the repo root, and succeeding — the one assertion that cannot be written in-process.

## Error Behavior

A failed gate raises `GateFailed` carrying every gate's verdict; the gate engine writes nothing. `api/` catches it, writes `data/<stage>/GATE_FAILED.json` with the assertion, the observed and expected values, and up to 100 offending record ids, and re-raises, so the CLI exits non-zero and an in-process caller gets the results attached to the exception. No stage consumes an input whose gate did not pass. Every provider failure arrives as an `LLMError` subclass, so each dispatching stage wraps one `except LLMError`; nothing catches bare `Exception` around an LLM call.

| Situation | Behavior |
|---|---|
| Source SHA-256 differs from `params.yaml` | Hard stop. A changed source is a new dataset version, decided by a human. |
| Problem count moves > ±10% from declared | Hard stop with the delta. |
| Profile breaks a profile rule | Nothing stops the run. The rules are stated, not enforced; the symptom is in § *Rules a profile must satisfy*, per rule. |
| Profile and modality names disagree | Hard stop. A profile declares its modality; a mismatched pair is a configuration error, not a coercion. |
| A modality has no redactor for a part | Record quarantined to `quarantine/pii/`, never advanced, carrying `unredactable_part` in `failed_checks` so the file it is in is not the only record of why. |
| An answer's shape is not the profile's answer type | Quarantined by the validity check that names it, run continues. Never coerced: a call object read as a name, or a name read as a call, would put a guess in a label. |
| An answer names one tool twice | Quarantined — requirement 73. A person decides whether the source means parallel calls or is malformed. |
| A consensus call is missing a required argument | No consensus for that call; it is dropped rather than completed. The record ranks by disagreement as usual. |
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

- **Profile rules.** Not a shared suite — requirement 6 and *Decisions* say why, and what it costs. Each profile proves the five rules of § *Rules a profile must satisfy* in its own test module, over its own answer type: `answer_distance` a metric including on the empty answer, `vote_consensus` deterministic and honouring unanimity, an answer surviving a JSON round trip, `build_record` preserving every field it does not own, and `training_example` reproducing the record's answer. A profile arriving without them is the signal to build the suite after all.
- **Genericity.** A second, deliberately trivial profile — single-label classification over a 30-record text fixture — runs the whole graph end to end. Two profiles is the cheapest proof that the core is not secretly one profile's code, and the classification profile is small enough to be worth it for that reason alone.
- **Modality boundary.** A stub modality returning one audio part with a `uri` and no inline bytes runs `load` → `remove_invalid` → `pii_check` → `embed`, asserting the stages neither inline it nor crash. This is the seam's only test until a real audio modality exists, and it is what stops the seam rotting.
- **Import graph.** No `pipeline/` or `shared/` module imports a concrete profile or modality — invariant 16. No module re-implements a toolkit function — invariant 17. No engine module opens a file or imports `api/` or `declared/` — invariant 18, shown failing on the five I/O sites it was written against.
- **Import purity, as a subprocess.** `python -c "import dataforce.profiles.tool_decision"` from a working directory that is not the repo root — invariant 19. This is the test that would have caught the problem the engine/api split exists to fix.
- **Two registries in one process,** holding different profiles, neither seeing the other's.
- **Contracts.** Every artifact has a pandera schema; a round-trip test writes with `write_jsonlines`, reads with `read_jsonlines`, and validates.
- **Compound answers.** δ hand-worked on four pairs: same call, same tool with one differing argument, different tools, and one answer empty — asserting the ordering `0 < δ(argument) < δ(tool) ≤ 1` and that identical arguments reproduce Jaccard over names exactly. Canonical rendering: one call spelled three ways — reordered keys, extra whitespace, arguments as a JSON string versus an object — yielding one part and one `rid`. Consensus: a vote set agreeing on the name and splitting 2–1 on one argument, and one where a required argument has no majority, asserting the call is dropped rather than half-built.
- **Agreement.** α over an arbitrary δ against a hand-computed example, plus the degenerate check that α with an identity distance equals `krippendorff`'s nominal α on the same data. Consensus against hand-worked vote sets, including where consensus differs from every individual answer.
- **Privacy.** Per modality: a fixture asserting recall on real personal data and *no* replacement on look-alikes; placeholder stability across two mentions of one value; the vault absent from every `.dvc` file and present in `.gitignore`.
- **Jury.** A stubbed OpenAI-compatible endpoint returning a clean answer, a fenced answer, prose-wrapped JSON, an out-of-space answer, a wrong type, and empty — each becoming a valid answer or a clean abstention, with `repaired` true for exactly the fenced and prose-wrapped cases. Panel diversity against one-family and unrecognised-name configs. Cache determinism. Key-pool failover with a 429 on one key and a quota error on another, asserting identical votes to a single-key run and that an auth error stops the run instead.
- **Triage.** Bucket assignment over hand-built (cohesion, conflict) grids including boundaries; audit sizing against worked values (`p=0.05, e=0.02 → 457`); records below the vote minimum excluded rather than bucketed.
- **Toolkit boundary.** One integration test running `agent-toolkit`'s own `tests/consumer_smoke.py` against the installed environment. The file is **not in the wheel** — the library builds `packages = ["src/agent_toolkit"]` — so CI fetches it with `git clone --depth 1 -b v0.1.0`. A bad git-dependency resolution is then caught here rather than at the first jury run.
- **Label Studio.** The generated config validated against a live instance in CI via testcontainers — create project, push three tasks, pull back a submitted annotation. The allowlist test runs on the built payload without a server.
- **Split.** A planted group spanning what would be a random split, and a planted n-gram overlap, each asserted caught.
- **End to end.** The smoke rung *is* the integration test: `dataforce run` from raw to release against stubbed jurors, a stubbed generator, and a containerized Label Studio, asserting a byte-identical run manifest and `MANIFEST.sha256` on a second run. This passing is the definition of the pipeline being done. Nothing asserts a second run is *fast* — there is no stage cache to assert about.

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
