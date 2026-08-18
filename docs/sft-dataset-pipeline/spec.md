# SFT Dataset Pipeline — Raw Corpus to Released Training Set

## What

A reproducible, gated pipeline that turns the raw Tool-Decision corpus (`fc_train_final.json`) into a versioned, documented, SFT-ready dataset. It is fifteen DVC stages, each producing a checksummed artifact and each guarded by a machine-checked **gate** that fails the run rather than passing bad data downstream. Existing open source carries the annotation UI, deduplication, annotator aggregation, agreement statistics, and data versioning; [`agent-toolkit`](../agent-toolkit/spec.md) 0.1.0 — already built and released — carries streaming JSON, atomic artifact I/O, hashing, prompt templating, and every LLM call including schema-validated structured output. This spec builds only the five things that exist nowhere: a marker-preserving adapter, the validation-question generator, a Vietnamese spoken-form PII scrubber, a multi-model **LLM jury** that finds records worth human attention, and the gate runner.

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

Three defects are detectable without a single human judgment, and a fourth was fixed in the
source on 2026-08-17 — which is itself the finding that matters most here:

| Defect | Count | Why it is fatal for SFT |
|---|---:|---|
| `meta.label` disagrees with the assistant message | **0** — was 48 (0.227%) | Fixed upstream on 2026-08-17. The gate stays, with an expected count of 0: the fix proves the file moves, and a regression here silently trains the model on the losing side of two disagreeing sources. |
| Label names a tool absent from that record's own catalog | **722** (3.41%) | The target tells the model to call something it was never offered. Unlearnable, and it teaches hallucination. |
| Catalog parser finds no `[ToolName]` block | **841** (3.97%) | Either genuinely toolless prompts or a parser miss — the two must be distinguished before either is trusted. |
| `source_index` is unique per record (13,366 distinct over 13,366 records) | — | It looks like a grouping key and is not one. Splitting on it gives no leakage protection. |

That fix closed a discrepancy inside our own documents. [`guided-validation`](../guided-validation/spec.md) reports 7,486 zero-label records, counted from the assistant message, against 7,498 from `meta.label` — a 12-record net difference that was the arithmetic of those 48 disagreements. Both counts are now 7,498, so that spec's figure is stale rather than wrong, and it needs a sync pass.

**The source file changed three times in four weeks, and that is the load-bearing observation.** Measured with one parser across the versions on disk, `label_assistant_mismatch` was 48 in the 2026-08-17 backup and is 0 in the current file. Every count in this section is therefore a statement about one SHA-256, not about "the corpus" — which is exactly why requirement 8 pins the expected counts in `params.yaml` and requirement 7's gate hard-stops when they move. That mechanism was specified before this change was noticed, and it is what would have caught it.

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
| Streaming JSON, atomic I/O, hashing, templating, all LLM access | **[`agent-toolkit`](../agent-toolkit/spec.md)** | **0.1.0 released**, `giangchicken/agent-toolkit` |

**Argilla was the obvious candidate and is rejected.** It is the closest fit on paper — LLM-data-native, Python-first, records with typed questions and built-in distribution. But its last release is 2.8.0 on 2025-03-10, and every commit to `main` since that date is a README or project-status edit: seventeen months with no functional change. Betting an annotation pipeline on a library that has stopped shipping is a cost that lands later and cannot be undone cheaply. Label Studio is heavier and its XML labeling config is the thing [`dataforce-platform`](../dataforce-platform/spec.md) deliberately rejected for the platform's *own* schema — but it is maintained, and here we only *generate* that XML, never author it by hand.

**Cleanlab is deferred, not dismissed.** Confident Learning is the right tool for a fixed label space, and this corpus does not have one (above). Adopting it would mean either collapsing 14,411 tool names into a coarse proxy label — reshaping the task to fit the tool — or building a per-decision classifier whose class balance and feature pipeline are themselves a project. The LLM jury needs neither, produces a richer signal, and reuses infrastructure that already has to exist for question generation. If the jury's precision turns out to be the bottleneck after the first release, Cleanlab returns as a second opinion over whatever fixed label space the release has by then established.

### What `agent-toolkit` already provides

The library is built, released at `v0.1.0`, and verified against an installed wheel. Every row below is a function the pipeline **calls**, not one it writes. This table is normative: a pipeline module that re-implements a row here is a defect, and code review rejects it.

| The pipeline needs | The call | Used by |
|---|---|---|
| Stream a 126 MiB JSON array without loading it | `file_utils.iter_json_array_file(path)` | `load` |
| A stable record id | `string_utils.compute_hash(text, "sha256")[:16]` | `load`, dedup keys |
| Read and write every artifact, atomically, `ensure_ascii=False` | `file_utils.read_jsonlines` / `write_jsonlines` / `read_json` / `write_json` | every stage |
| Read declarative config and prompt files | `file_utils.read_yaml`, `file_utils.read_txt` | every stage |
| Accent-insensitive Vietnamese comparison | `string_utils.normalize_text(text, remove_tone_marks=True)` | PII patterns, dedup keys |
| Fill a prompt template | `string_utils.slot_filling(text, {...})` — `{{placeholder}}` syntax | jury, question gen, PII verify |
| One LLM call, retried, rate-limited, `str` in / `str` out | `llm.complete(prompt, model=, api_key=, base_url=)` | PII verify |
| A call whose answer must satisfy a JSON Schema | `llm.complete_structured(prompt, schema, mode=)` → `(value, ValidationInfo)` | jury votes, question gen |
| Keep the model's reasoning alongside its answer | `ValidationInfo.reasoning`, `Completion.reasoning` | jury |
| Recover JSON from a fenced or prose-wrapped reply | inside `complete_structured`; reported as `ValidationInfo.repaired` | jury |
| Model family, for panel diversity | `llm.model_family(name)` | panel gate |
| Prompt-token estimate | `llm.count_tokens(messages, model)` | jury budget |
| Concurrency and requests-per-minute per endpoint | `llm.get_traffic_controller(name, max_concurrency=, requests_per_minute=)` | key pool |
| Retry policy, set once for the process | `llm.RetryPolicy(...)`, `llm.set_default_retry_policy(...)` | `cli.py` |
| One exception type to catch around any provider failure | `llm.exceptions.LLMError` and its subclasses | everywhere |
| Tell "this key is out of quota" from "slow down" | `ProviderQuotaExceededError` ⊂ `LLMRateLimitError` ⊂ `LLMAPIError` | key pool |
| A logger that configures nothing | `get_logger(__name__)` | everywhere |

Three consequences worth naming, because each removes a file the pipeline would otherwise contain: there is **no `io.py`** — `file_utils` is the I/O layer, and it is already atomic and already creates parent directories; there is **no JSON-repair helper** — `complete_structured` does that internally and reports whether it was needed; and **`vote.py` does not validate the catalog constraint** — the schema does, at the library boundary.

**What the toolkit does not give us, and what each gap costs.** These are measured from the shipped code, not guessed:

| Gap | Consequence for this spec |
|---|---|
| `Completion` is `(content, reasoning)` — the response's `usage` is **discarded** | Every token figure in this document is a `count_tokens` *estimate*, and the budget ceiling of requirement 33 is enforced on estimates. Actual-token accounting requires `usage` on `Completion`, which is a toolkit change, not a pipeline one. Filed against `agent-toolkit` 0.2; not worked around here. |
| `LLMRateLimitError.retry_after` exists as a field but is never populated from a `Retry-After` header | The key pool's cooldown is a declared constant in `config/panel.yaml`, never a server hint. |
| `json_utils` ships only `iter_json_array`; `loads_repair`, `deep_merge`, `json_diff`, `jsonpath_get` are 0.2 | No stage may assume them. |
| `llm.stream` and `complete_with_tools` are 0.2 | Neither is wanted: jurors return JSON text, which is exactly the contract `complete_structured` validates. |
| `set_config_resolver` installs **one process-global** resolver, and `resolve_config` is keyed by model name | A key pool rotating credentials per call cannot be expressed as a resolver. The pool passes `api_key=` and `base_url=` explicitly on every call, which the toolkit documents as always winning over the resolver. No resolver is installed; the default `EnvConfigResolver` is left in place and unused. |
| `get_traffic_controller` memoizes per (event loop, `provider_name`) and **ignores the limits given by later callers** | One key group's budget is fixed by whichever call creates it first. Controllers are therefore constructed in exactly one place, from `config/panel.yaml`, before any dispatch. |

Pinned as a git ref, since the library is not on any registry:

```
agent-toolkit[llm] @ git+https://github.com/giangchicken/agent-toolkit.git@v0.1.0
```

### Relationship to the existing specs

This spec sits **above** the other three and narrows two of them. Applying it requires these amendments, which are proposed here and not yet made:

- **[`dataforce-platform`](../dataforce-platform/spec.md):** drop image modality from v1 — requirement 7's `bbox`/`polygon`, requirement 27's IoU comparators, requirement 31's COCO/YOLO exporters, and the images in the E2E scenario. Defer the whole FastAPI + React annotation service behind a Label Studio-based v0 until the pilot gate passes. What Label Studio does *not* give us — a review workflow, agreement metrics, the catalog, subscriptions — is precisely what remains of the platform's justification, and the pilot is what establishes whether that is worth a quarter of engineering.
- **[`guided-validation`](../guided-validation/spec.md):** unchanged in substance. The question model, focus rules, glossary, correction shape, and flag taxonomy are all retained; only the rendering surface changes from a bespoke React card to a generated Label Studio config. Its invariant 1 (the generator's answer never reaches the annotator) gets *stronger*: neither the generator's proposed answer nor any juror's vote is sent to Label Studio at all, so nothing can leak through a response schema.
- **[`agent-toolkit`](../agent-toolkit/spec.md):** built and shipped. Its own spec's Public-surface section still lists 0.2 symbols; that document needs a sync pass, tracked in its repository. The jury's key pool stays in this pipeline; it graduates into the library only when a second consumer needs it.

## Requirements

### Acceptance criteria, fixed before any data moves (Step 1)

1. The release's primary metric is **exact-set-match accuracy** of the predicted tool set against the gold set, measured on the human-validated test split only. Secondary metrics: abstention (zero-label) precision and recall, and macro set-F1. All three are declared in `params.yaml` before the first stage runs and are not changed afterwards without a new release version.
2. The pipeline emits the **inputs to a learning curve** — deterministic 25% / 50% / 100% subsamples of the training split, group-disjoint under requirement 55 and recorded in the manifest — so the question "more data or better data?" can be answered by measurement. Running the training and producing the curve itself is out of scope (see Out of Scope), and this requirement is satisfied by the slices plus the metric definition, not by a plotted result.
3. The task representation is fixed for the whole pipeline: input is (tool catalog, conversation), output is a **set of tool names drawn from that record's own catalog**, and the empty set is a first-class answer, not a missing value. No stage may substitute a per-tool binary, a coarse proxy class, or a cardinality bucket for the set.

### Ingest and source integrity (Steps 2, 3)

4. Ingest streams the source via `file_utils.iter_json_array_file`. The 126 MiB file must never be loaded whole.
5. Every record gets a stable `rid = string_utils.compute_hash(system ‖ user ‖ assistant, "sha256")[:16]`, independent of position, so artifacts are diffable across re-ingests and re-ordering is not a change.
6. Ingest records source provenance per record: source file SHA-256, byte offset, `meta` verbatim, and the ingest timestamp. Nothing is dropped; unparsable records are carried with `parse_status = "unparsed"` and their raw text.
7. The **source-integrity gate** detects and quarantines, as separate named defect classes: `label_assistant_mismatch` (0 expected, was 48 before the 2026-08-17 source fix), `label_not_in_catalog` (722 expected), `empty_catalog` (841 expected), and `label_cardinality_anomaly`. Quarantined records leave the main path into `data/quarantine/<defect>.jsonl` with the defect recorded; they are never silently deleted and never silently kept.
8. Expected defect counts are declared in `params.yaml`. A count that moves by more than ±10% fails the gate — the source changed, and that must be a decision rather than a surprise.
9. Every artifact is written with `file_utils.write_jsonlines` or `write_json` and read with the matching reader. Both writers are atomic and create parent directories, so an interrupted stage leaves the previous artifact intact rather than a truncated one; no stage opens an artifact file directly.

### PII (Step 9, legal)

10. A scrub stage detects and replaces, in every message, both literal and Vietnamese spoken-form personal data: phone numbers, email addresses, national ID numbers, bank account numbers, and full personal names in the customer turn. Spoken-form detection covers digit words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), spoken `@` (`a còng`), and spoken punctuation (`chấm`, `gạch dưới`).
11. Detection matches against `string_utils.normalize_text(text, remove_tone_marks=True)` as well as the raw text, so a transcript spelling `khong` or `chin` is not missed while patterns stay written in correct Vietnamese. Span offsets are resolved back onto the original text; the normalized form is a matching aid and is never stored or written.
12. Replacement is a **stable typed placeholder** (`<PHONE_1>`, `<EMAIL_1>`) scoped per record, so a value referenced twice in one conversation stays co-referent and the tool-calling semantics survive scrubbing. Replacement is never deletion.
13. Every regex hit above a configured recall threshold is verified by an LLM pass over the surrounding ±80-character window, via `llm.complete_structured` against a fixed classification schema. A response that fails the schema is treated as unverified, never as a negative. The regex layer sets recall; the LLM layer sets precision.
14. A scrubbing report records, per class, the number of spans replaced and a sample of 20 *placeholders in context* (never the original values). The mapping from placeholder to original value is written to `data/raw/pii_vault.jsonl`.
15. `data/raw/` is **not DVC-tracked and not committed**: the source file is tracked by SHA-256 recorded in `params.yaml` rather than by DVC, and `pii_vault.jsonl` appears in `.gitignore`, in no `.dvc` file, and in no `dvc.yaml` output list. Every other directory under `data/` is DVC-tracked.
16. The scrub gate fails if any release-tier artifact matches a literal PII pattern.

### Deduplication and grouping (Step 3)

17. Exact duplicates are removed on `compute_hash(system ‖ user)`, keeping the record with the richer `meta`.
18. Near-duplicate and semantic duplicates are found with SemHash over the concatenated conversation. Cluster members are not deleted; they are assigned a shared `dup_cluster_id`, and one representative per cluster is marked `is_representative`. Deletion happens at export, from an explicit filter, so the decision is reversible and recorded.
19. Every record gets a `group_key` for splitting: the catalog fingerprint, unioned with its `dup_cluster_id`. `source_index` is explicitly **not** a group key (measured above).

### The LLM jury (Steps 3, 5)

20. A **jury** of independent LLMs predicts the tool set for each record, from the record's own system message and conversation, via `llm.complete_structured(prompt, schema)` where `schema` is `{"type": "array", "items": {"type": "string", "enum": <this record's catalog>}}`. Each juror answers the corpus's task exactly as stated in requirement 3 — no reformulation, no per-tool questioning, no auxiliary labels.
21. That schema is how requirement 3's catalog constraint is enforced: a vote naming a tool outside the record's own catalog fails validation inside the library, so `ValidationInfo.ok` is `False` and the returned value is `None`. The pipeline does not re-check the constraint; it checks that the schema was built from the right catalog.
22. An invalid vote is retried **once** with the same prompt, and then recorded as an abstention carrying `ValidationInfo.raw`, `.error`, `.repaired`, and `.strategy`. An invalid vote never becomes a partial vote by truncation, and `repaired` is reported per juror as a model-quality signal distinct from `ok`.
23. Every vote stores `ValidationInfo.reasoning` when the juror emitted any. It is the only record of *why* a juror voted as it did, it is not recoverable afterwards, and it is what an adjudicator reads when a `hard_record` reaches them. It is never sent to Label Studio (requirement 46).
24. Jurors are called with `mode="prompt"`. A decode-time constraint over a 20-value enum changes which tokens are reachable, the toolkit's own module docstring records a measured case where that made the answer worse, and — decisively — a juror constrained by `response_format` is not comparable to one whose endpoint silently ignored it. Validation runs identically either way, so asking plainly and validating afterwards is what keeps jurors comparable.
25. The panel must be **family-diverse**: at least three jurors drawn from at least three distinct families as reported by `llm.model_family`. No juror may resolve to `"unknown"` — the function's own contract is that two unrecognised names read as one family, so a panel containing one is not proved diverse, it is unmeasured. Repeated sampling of one model at temperature > 0 does not count as a panel, because correlated jurors agree on their shared errors and the disagreement signal collapses.
26. No juror in the primary panel may come from the model family that labelled the corpus. 14,241 records (67.3%) were labelled by `gemma-4-31B-it`; a `gemma` juror measures family agreement, not correctness. A same-family juror may be run as an explicitly-labelled **control** whose only output is an estimate of how much of the corpus label is family-specific.
27. Votes are cast at temperature 0 and cached on `(rid, model, prompt_version)`. The cache key excludes the API key: which key served a call must not be able to change the vote. A change to `config/panel.yaml` or to a prompt file bumps `prompt_version`.
28. Jury dispatch runs over a **key pool**. Each entry carries its own request and token budget; the pool round-robins, passes `api_key=` and `base_url=` explicitly per call, backs off per key on `LLMRateLimitError`, quarantines a key that raises `ProviderQuotaExceededError` for a declared cooldown, and continues on the remaining keys. A single exhausted key never stalls a run. Estimated per-key and per-juror consumption is reported on the run.
29. Concurrency and rate limiting come from `llm.get_traffic_controller`, one controller per key group, all constructed in one place from `config/panel.yaml` before dispatch begins — because the toolkit fixes a controller's limits at creation and ignores them on later calls naming the same group.
30. Set-valued agreement everywhere uses one distance, `δ(A,B) = 1 − |A ∩ B| / |A ∪ B|`, with `δ(∅, ∅) = 0` by definition. That convention is load-bearing: 35.4% of the corpus is the empty set, and treating two agreeing abstentions as maximally distant would invert the signal on a third of the data.
31. Per record the jury stage stores: every individual vote, the **majority-consensus set** (tools included by a strict majority of valid jurors), the **plurality set** (most frequent exact set), an `exact_unanimity` flag, `jury_cohesion = 1 − mean pairwise δ`, and `corpus_conflict = δ(consensus, corpus_label)`.
32. Juror weights are calibrated on the gold set as mean set-F1 against human-validated labels, and are reported per juror. A juror whose gold F1 falls below a declared floor is dropped from the panel for that release, and the drop is recorded.
33. The jury runs in **staged escalation**: a 3-juror pass over the corpus, then an expanded panel only on records showing conflict or low cohesion. The stage reports estimated cost from `llm.count_tokens` before starting and treats the token estimate as a hard ceiling, stopping cleanly with a partial result. Because the toolkit discards the response's `usage`, the ceiling is enforced on estimates and the run reports it as such.
34. The jury's consensus accuracy on the human-validated test split — and each juror's individually — is reported in `metrics.json`. It is the zero-shot baseline the fine-tune has to beat, and it comes free with the triage pass.
35. **No jury vote ever becomes a training label without human confirmation.** The jury selects and ranks records for human attention; it does not relabel. A corpus that is already two-thirds machine-labelled cannot be improved by overwriting it with more machine labels — that is the recursion the model-collapse literature describes (Shumailov et al., *Nature* 2024).
36. Optionally and explicitly, the unvalidated remainder may carry jury consensus as a **separate tier**: `validation.status = "jury_consensus"`, permanently barred from the test split, reported in the datasheet with its own error bar measured against the human-validated audit sample. This is opt-in per release and off by default.
37. Deterministic marker-DSL rules — missing required parameter, `{hold_missing}` clause satisfied, `{trigger}` keyword in the last turn, `{constraint}` violated, `{turn_trigger}` scope violation — act as hard validity constraints on juror votes and as the defect detectors of requirement 7. They may additionally be admitted as one **rule juror** producing a set, but only if their gold set-F1 clears the same floor as any other juror.

### Triage — deciding what a human looks at

38. Records are bucketed on two axes, cohesion and conflict, and the buckets carry different meanings and different destinations:

| | Jury agrees with itself | Jury split |
|---|---|---|
| **Agrees with corpus** | `agreed` — audit sample only | `ambiguous_agreed` — glossary review candidate |
| **Disagrees with corpus** | `likely_label_error` — top of queue | `hard_record` — expert plus guideline fix |

39. Bucket thresholds live in `params.yaml` and are **provisional until the pilot measures them**. The pilot reports each bucket's precision — the fraction of `likely_label_error` records the annotators actually judged incorrect — and the thresholds get exactly one re-tuning pass from that measurement. Shipping thresholds that were never checked against a human verdict is the failure this requirement exists to prevent.
40. The annotation queue is filled from five strata with declared quotas: (a) `likely_label_error`, (b) `hard_record`, (c) the zero-label population, deliberately oversampled because it carries the corpus's real difficulty, (d) a **uniform random audit sample** whose only purpose is an unbiased residual-error estimate, and (e) the entire test split. Every stratum's selection is recorded per record so the sampling design is reconstructible.
41. The random audit sample is sized from the target confidence interval, not chosen by feel: `n = z²·p(1−p)/e²`. At `p = 0.05` and `e = ±0.02`, `n = 457`; the default is 500. If the observed rate exceeds the assumed `p`, the stage recomputes `n` and requests more.

### Question generation and annotation (Steps 4, 5)

42. Question generation follows [`guided-validation`](../guided-validation/spec.md) unchanged: focus chosen by rule, batch pre-generation, token budget as a hard ceiling, idempotence on `(rid, prompt_version, model)`. Prompts are files under `config/prompts/`, read with `file_utils.read_txt` and filled with `string_utils.slot_filling`; the generator's output is obtained with `llm.complete_structured` against the question schema, and the gate's "schema-valid ≥ 98%" is measured from `ValidationInfo.ok`.
43. `slot_filling` uses `{{double-brace}}` placeholders and the corpus's marker DSL uses `{single-brace}` tokens, so filling a template can never consume `{trigger}` or `{hold_missing}`. This non-collision is asserted by test, not assumed, because it is the only thing standing between prompt templating and silent destruction of the annotator's evidence.
44. Publishing creates a Label Studio project from a **generated** labeling config. The correction control is a dynamic `<Choices value="$tool_choices" choice="multiple">` populated from that record's own catalog plus an explicit "no tool" option, so a correction is a set drawn from the catalog by construction.
45. All evidence and glossary HTML is built by the pipeline and **escaped**; corpus text is never interpolated into markup unescaped.
46. Nothing from the generator or the jury is written to Label Studio in any field — not data, not metadata, not a prediction. Proposed answers, juror votes, juror reasoning, cohesion, conflict, and stratum stay in the pipeline and are joined back on `rid` after responses are pulled.
47. Overlap is achieved by project membership rather than a per-task setting: the pilot runs one project with both annotators assigned and `maximum_annotations` set to the annotator count, giving 100% overlap; at scale the flagged and audit strata keep overlap 2 and the remainder runs at overlap 1. *This depends on Label Studio Community honouring `maximum_annotations`, which the smoke stage verifies before anything else is built on it.*
48. A gold set of ≥50 expert-labelled records is mixed into every project as ordinary tasks, visually indistinguishable, and used both to score each annotator continuously and to calibrate juror weights per requirement 32.
49. Pulling responses normalizes them into the canonical answer shape and **rejects, rather than repairs**, any response where `verdict = incorrect` carries no correction. Rejected responses return to the queue with the reason attached; correction-required is enforced in the pipeline because Label Studio's conditional validation cannot be relied on.

### Aggregation, adjudication, curation (Step 6)

50. Krippendorff's alpha on the **verdict** (nominal: correct / incorrect / unsure) is computed across all overlapped records, per question focus and overall, with the `krippendorff` package.
51. Agreement on **corrections** — which are sets — is computed as α with the `δ` of requirement 30, implemented in this pipeline because the library covers only nominal, ordinal, interval, and ratio scales. Its nominal degenerate case is tested against the library's output.
52. Where overlap ≥ 2, verdicts are aggregated with Dawid-Skene, which estimates per-annotator reliability, rather than majority vote. Corrections are aggregated as the majority-consensus set under the same rule the jury uses.
53. Records where annotators disagree, or where the aggregated confidence is below threshold, are published to a second **adjudication** Label Studio project showing both answers and both notes, resolved by a reviewer who did not produce either. Label Studio Community has no review workflow; this is that workflow.
54. Curation applies accepted corrections to produce the curated label, and records for every record whether its label is `original`, `corrected`, `jury_consensus`, or `unvalidated`, with the validator and the decision date.

### Split, decontamination, export (Step 7)

55. Splitting is **group-based on `group_key`**, never random. A group is wholly in one split.
56. The test split is **100% human-validated**. A record that has not been through annotation cannot enter test, at any budget, and `jury_consensus` records are barred permanently. This is the rule that keeps every reported number meaningful.
57. Decontamination verifies zero 13-gram overlap between the test split and train, and zero shared `group_key`. Overlap fails the gate.
58. Export emits SFT JSONL in the source `messages` shape, with the curated label in both the assistant message and `meta.label` — which must be asserted equal on the way out. Upstream drove that class to 0 on 2026-08-17; the assertion stays because a curation step that writes one and not the other would reintroduce it.
59. Every exported record carries provenance: source SHA-256, pipeline version, `agent-toolkit` version, validation status, validator, dedup cluster, split, stratum, and — where the jury touched it — the panel version and the consensus it produced.
60. The release is a DVC-tracked directory with a manifest listing every file's SHA-256, and the whole release is reproducible from one git commit plus `dvc repro`.

### Documentation (Step 8)

61. Each release ships a **datasheet** (Gebru et al.) answering the handbook's six questions, a **data statement** (Bender & Friedman) covering language variety and both creator and annotator demographics, and a **Croissant** metadata file validated by `mlcroissant`.
62. The datasheet states the synthetic share explicitly. 14,241 of 21,172 records (67.3%) are machine-labelled by `gemma-4-31B-it`, and 1,358 have already been relabelled once. Given the model-collapse result, a corpus that is two-thirds machine-labelled must be documented as such, and the human-validated test split is the mitigation that makes the release measurable at all.
63. The datasheet names the jury panel — every juror's model, family as reported by `model_family`, version, and gold-calibrated weight — because the selection of which records humans looked at is part of how the dataset was made.
64. Documentation generation is a pipeline stage with a gate, not a manual step. A missing required datasheet field fails the release.

## Design

### Stage graph

Each stage is one DVC stage: declared inputs, declared outputs, a gate. `dvc repro` runs only what changed.

| # | Phase | Stage | Handbook step | Output | Gate |
|---|---|---|---|---|---|
| 0 | prepare | `load` | 2 Collection | `interim/1_prepared/loaded.jsonl` | parsed + unparsed == source count; source SHA-256 matches params |
| 1 | prepare | `validate` | — | `interim/1_prepared/validated.jsonl`, `quarantine/` | defect counts within ±10% of declared |
| 2 | prepare | `scrub` | 9 Legal | `interim/1_prepared/scrubbed.jsonl` | zero literal-PII matches downstream |
| 3 | find_duplicates | `embed` | 3 Filtering | `interim/2_deduped/embeddings.npy` | row count matches records |
| 4 | find_duplicates | `dedup` | 3 | `interim/2_deduped/records.jsonl`, `clusters.jsonl` | exact dups 0; cluster report emitted |
| 5 | ai_review | `jury` | 3, 5 | `interim/3_reviewed_ai/votes.jsonl`, `consensus.jsonl` | ≥3 families, none `unknown`; no corpus-family juror in panel; estimated tokens ≤ budget; invalid-vote rate ≤ 5% |
| 6 | ai_review | `triage` | 3, 5 | `interim/3_reviewed_ai/queue.jsonl` | every stratum met its quota; audit `n` ≥ computed |
| 7 | human_review | `generate` | 4 | `interim/4_reviewed_human/questions.jsonl` | schema-valid ≥ 98%; estimated tokens ≤ budget |
| 8 | human_review | `publish` | 5 | Label Studio project + `published.jsonl` | payload key set equals the allowlist |
| 9 | human_review | `pull` | 5 | `interim/4_reviewed_human/responses.jsonl` | every `incorrect` has a correction |
| 10 | human_review | `aggregate` | 6 QA | `interim/4_reviewed_human/aggregated.jsonl` | α ≥ 0.667; flag ≤ 10%; gold ≥ 0.85 |
| 11 | human_review | `curate` | 6 | `interim/4_reviewed_human/curated.jsonl` | every correction ⊆ that record's catalog |
| 12 | release | `split` | 7 | `processed/{train,val,test}.jsonl` + curve slices | zero group leakage; zero 13-gram overlap |
| 13 | release | `export` | 7 | `release/v1/sft_*.jsonl` | test 100% human-validated; counts reconcile; label == assistant |
| 14 | release | `document` | 8 | `release/v1/{datasheet.md,croissant.json}` | all required fields present; Croissant validates |

Stages 8–10 loop: publish → annotate → pull → aggregate → adjudicate → pull again. Stage 5 re-runs when the panel changes, and its cache makes an unchanged juror free. `embed` precedes `dedup` because `dedup` consumes the embeddings.

### Repository layout

Phase folders are named for what happens in them, in run order, so a stage name in `dvc.yaml` leads straight to a directory. Each phase holds its **stage entry points** at the top and its helpers in `lib/`; `dvc.yaml` is the authority on which is which.

```
dataforce/
├── pyproject.toml   uv.lock   Makefile   README.md   .gitignore
├── dvc.yaml   dvc.lock   params.yaml
│
├── src/dataforce/
│   ├── shared/                  used by everything dataforce ever does
│   │   ├── schemas/             pandera + pydantic, one file per artifact
│   │   ├── sets.py              δ, consensus, plurality, cohesion, α_set
│   │   └── gates/runner.py      engine only — no thresholds live here
│   │
│   ├── pipeline/                one domain of dataforce, not all of it
│   │   ├── prepare/
│   │   │   ├── load.py  validate.py  scrub.py          ← 3 stages
│   │   │   └── lib/{adapter,pii_patterns,pii_verify,vault,rules}.py
│   │   ├── find_duplicates/
│   │   │   ├── embed.py  dedup.py                      ← embed runs first
│   │   │   └── lib/{near_duplicates,grouping}.py
│   │   ├── ai_review/
│   │   │   ├── jury.py  triage.py
│   │   │   └── lib/{panel,keypool,vote,consensus,escalate,buckets,strata,sampling}.py
│   │   ├── human_review/
│   │   │   ├── generate.py  publish.py  pull.py  aggregate.py  curate.py
│   │   │   ├── labelstudio/{config,client}.py
│   │   │   └── lib/{questions,alpha,gold,adjudicate}.py
│   │   └── release/
│   │       ├── split.py  export.py  document.py
│   │       └── lib/{decontaminate,datasheet,croissant,manifest}.py
│   │
│   └── cli.py                   dataforce <stage> | dataforce gate run <stage>
│                                the only place logging handlers are configured
│
├── config/                      policy humans edit; never imported as Python
│   ├── gates.yaml   panel.yaml
│   ├── prompts/{jury_vote.v1.txt, question_gen.v1.txt, pii_verify.v1.txt}
│   └── templates/{labeling_config.xml.j2, datasheet.md.j2}
│
├── data/
│   ├── raw/                     PII TIER — NOT DVC-tracked, never committed
│   │                            source file + pii_vault.jsonl
│   ├── interim/                 DVC-tracked
│   │   ├── 1_prepared/  2_deduped/  3_reviewed_ai/  4_reviewed_human/
│   ├── processed/               train/val/test + 25/50/100% curve slices
│   ├── release/v1/              sft_*.jsonl, datasheet, croissant, MANIFEST
│   └── quarantine/{prepare,scrub,human_review}/
│
├── notebooks/                   dataforce profile, corpus survey
├── tests/{unit,integration,e2e,fixtures}/
├── deploy/                      docker-compose Label Studio, CI config
└── docs/
```

There is deliberately no `io.py` and no JSON-repair module: `agent_toolkit.file_utils` is the I/O layer and `complete_structured` is the repair layer. `data/raw/` is the one directory outside DVC, which is what makes invariant 3 checkable rather than aspirational.

The library is a host's responsibility to configure and it configures nothing itself, so `cli.py` is the single place that installs logging handlers and calls `set_default_retry_policy`. No module under `pipeline/` touches either.

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
    "panel_version": 2, "prompt_version": "jury_vote.v1",
    "votes": [ { "juror": "j1", "family": "glm", "set": ["VerifyEmail_15d"],
                 "ok": true, "repaired": false, "strategy": "prompt",
                 "reasoning": "Khách đã cung cấp email nên…", "raw": "[\"VerifyEmail_15d\"]" },
               { "juror": "j2", "family": "qwen", "set": [], "ok": true,
                 "repaired": true, "strategy": "prompt", "reasoning": "", "raw": "```json\n[]\n```" },
               { "juror": "j3", "family": "deepseek", "set": null, "ok": false,
                 "strategy": "prompt", "error": "$[0]: 'SendMail' is not one of [...]",
                 "raw": "[\"SendMail\"]" } ],
    "consensus": ["VerifyEmail_15d"], "plurality": ["VerifyEmail_15d"],
    "exact_unanimity": false, "cohesion": 0.67, "corpus_conflict": 0.0,
    "est_tokens": 5412
  },
  "triage": { "bucket": "agreed", "strata": ["audit"] },

  "validation": { "status": "corrected", "verdict": "incorrect",
                  "curated_label": [], "validators": ["u12","u07"],
                  "alpha_contrib": true, "decided_at": "…" },
  "split": "test"
}
```

The third vote is what an abstention looks like: `ok: false`, `set: null`, and the library's own `error` and `raw` retained. Nothing about it is a partial vote.

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

Each match writes the record to `quarantine/prepare/<defect>.jsonl` with the defect name and leaves the main path. `empty_catalog` is a **quarantine for triage, not a verdict**: 841 records is large enough that a parser miss and a genuinely toolless prompt must be told apart by hand before either is trusted, and the gate forces that to happen. Quarantined records can be re-admitted by an explicit `dataforce requeue --defect <name>` after the underlying cause is fixed, which creates a new pipeline version.

### PII scrubbing

Two layers, each doing one job. The regex layer maximizes recall and is allowed to be noisy; it matches against both the raw text and `normalize_text(text, remove_tone_marks=True)`, so a transcript that dropped its diacritics is still caught while the patterns stay readable. The LLM layer, prompted with a ±80-character window through `complete_structured`, decides whether the span is personal data or a price, date, or reference code. Only spans surviving both are replaced.

```
"số của em là không chín không một …"     ← regex hit, LLM: PHONE      → "<PHONE_1>"
"đơn hàng hai không hai bốn sáu tám"        ← regex hit, LLM: ORDER_REF → unchanged
```

Placeholders are stable within a record, so a phone given in turn 3 and confirmed in turn 7 becomes `<PHONE_1>` both times and the tool-calling logic — which turns on whether a required value was *supplied* — is preserved. This is why replacement, not deletion, is specified: deleting the value would flip the ground truth of every `{hold_missing}` judgment in the record.

A span whose verification call fails the schema is **unverified, not negative**. Its record is quarantined to `quarantine/scrub/pii_uncertain.jsonl` rather than advancing, because failing open on PII is the one failure this pipeline will not take.

### The LLM jury

The prompt is a file, `config/prompts/jury_vote.v1.txt`, filled with `slot_filling`:

```
{{system_message}}
{{conversation}}

Trả về DUY NHẤT một JSON array gồm tên các tool cần gọi, theo đúng thứ tự gọi.
Nếu không cần gọi tool nào, trả về [].
Chỉ được dùng tên tool xuất hiện trong danh sách trên.
```

`{{system_message}}` carries the `TOOLS:` block and its markers verbatim. The two syntaxes cannot collide — the template reads `{{double}}`, the DSL uses `{single}` — which is why templating cannot silently eat `{trigger}`, and why a test asserts it.

One call per juror:

```python
schema = {"type": "array",
          "items": {"type": "string", "enum": [t.name for t in record.catalog]}}
value, info = await complete_structured(
    prompt, schema, mode="prompt",
    model=juror.model, api_key=key.api_key, base_url=juror.base_url,
    temperature=0,
)
```

The `enum` is the catalog constraint, enforced by the library's validator. `info.ok is False` *is* the abstention — the pipeline stores `info.error`, `info.raw`, `info.repaired`, `info.strategy`, and `info.reasoning` and moves on. There is no bespoke parse-and-check step, and no code path where a malformed response becomes a truncated set.

**Aggregation is set-valued throughout.** One distance does all the work:

```python
def delta(a: set[str], b: set[str]) -> float:
    if not a and not b: return 0.0          # two abstentions agree perfectly
    return 1.0 - len(a & b) / len(a | b)
```

That `δ(∅,∅) = 0` line is not a detail. 35.4% of this corpus is the empty set; a Jaccard implementation returning `0/0 → nan` or treating two empty sets as maximally distant would make the zero-label population — the part carrying the corpus's real difficulty — look like the part with the least jury agreement.

From the votes: `consensus` is the set of tools a strict majority of valid jurors included; `plurality` is the most frequent exact set; `cohesion = 1 − mean pairwise δ`; `corpus_conflict = δ(consensus, corpus_label)`. Consensus can be a set no individual juror proposed, which is acceptable for a ranking signal and is exactly why requirement 35 forbids it from becoming a label on its own.

**Panel composition.** Three jurors minimum, three distinct `model_family` values minimum, none of them `"unknown"`, and no juror from the `gemma` family in the primary panel — that family labelled 67.3% of the corpus, so its agreement measures lineage rather than correctness. The `unknown` exclusion is not pedantry: `model_family` returns it for any name its table does not recognise, so two unrecognised jurors would count as one family and a panel could pass the diversity gate without being diverse. Running one `gemma` juror as a declared control is worth doing once: the gap between the control's agreement with the corpus and the panel's agreement with the corpus is a direct estimate of how much of this dataset is one model's opinion.

**Cost, estimated rather than measured.** The corpus is 100,557,307 prompt characters. At 3 characters per token — stated as an assumption, since Vietnamese diacritics tokenize unevenly — one full pass is ~34M input tokens and ~0.8M output:

| Pass | Records | Input tokens |
|---|---:|---:|
| 3-juror sweep, whole corpus | 21,172 | ~101M |
| escalate to 7 jurors on ~15% | ~3,200 | ~+20M |
| **staged total** | | **~121M in, ~3M out** |

Against a flat 7-juror sweep at ~235M, staging saves about half, and the cache makes a re-run after a panel change cost only the new juror. The p99 prompt is ~17,000 characters (~5.7k tokens) from the 20-tool catalogs — no context-window concern on any current model.

The ceiling is enforced against `count_tokens`, not against billed usage, because `Completion` carries no `usage` field. `count_tokens` is documented as rough — measured drift on Vietnamese runs −33% to +64% — so the budget in `params.yaml` must be set with headroom, and the run reports "estimated" on every token figure it prints. Correcting this properly means adding `usage` to the toolkit's `Completion`; until then, no number here should be read as a bill.

**Key pool.** Jurors are `(family, model, base_url, key_group)`; keys are pooled per group with their own request and estimated-token budgets. Credentials are passed per call as `api_key=` and `base_url=` — never through `set_config_resolver`, which installs one resolver for the whole process and cannot express per-call rotation. The pool dispatches round-robin, backs off per key on `LLMRateLimitError`, quarantines a key raising `ProviderQuotaExceededError` for a cooldown declared in `config/panel.yaml`, and keeps going on the rest, so a run's throughput degrades with key exhaustion instead of stopping. One `TrafficController` per key group, all obtained from `get_traffic_controller` in a single constructor pass before dispatch, because the toolkit fixes a controller's limits at first creation and ignores later callers' values. Estimated consumption is reported per key and per juror so the next run can be budgeted from evidence.

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

The distinction that a single score cannot express: a confidently-unanimous jury disagreeing with the corpus is probably a **label** problem, while a split jury disagreeing with the corpus is probably a **guideline** problem — the record may be genuinely underdetermined by the tool descriptions. Those need different people and produce different fixes, and collapsing them into one priority number sends both to the same queue. A `hard_record` reaching an adjudicator arrives with each juror's stored `reasoning`, which is the only artifact that explains why the panel split.

Thresholds separating the quadrants start as guesses in `params.yaml` and are re-tuned exactly once, from the pilot's measurement of each bucket's precision against human verdicts. A bucket whose precision the pilot cannot establish does not get a quota at scale.

### Annotation via Label Studio

The config is generated from `config/templates/labeling_config.xml.j2`, one per project, never hand-written:

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

Note what the pipeline holds rather than Label Studio: the generator's proposed answer, every juror vote, every juror's reasoning, cohesion, conflict, bucket, stratum, and the gold flag. Label Studio sees a question and a set of choices. Showing an annotator that three models said `[]` would turn an independent judgment into a ratification, which is the same argument [`guided-validation`](../guided-validation/spec.md) makes about the generator's answer, now applying to a larger set of fields — and `reasoning` is the most persuasive of them, so it is the one most important to withhold.

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
data/release/v1/
├── sft_train.jsonl        messages format, curated labels
├── sft_val.jsonl
├── sft_test.jsonl         100% human-validated, group-disjoint, decontaminated
├── curve_25.jsonl  curve_50.jsonl    deterministic train subsamples, group-disjoint
├── quarantine.jsonl       every excluded record with its defect
├── jury_report.json       panel, per-juror gold weights and families, bucket precision,
│                          zero-shot baseline, estimated token consumption per key
├── datasheet.md
├── data_statement.md
├── croissant.json
├── metrics.json           counts, α, flag rate, gold accuracy, residual error ± CI
└── MANIFEST.sha256
```

## Decisions

**The toolkit is a dependency, not a starting point.** Every row of the reuse table above is a function this pipeline calls. *Alternatives:* re-implement the small ones locally (hashing, JSONL I/O, templating) to avoid a git dependency; vendor the library. *Why:* the library exists because these exact functions were harvested from two internal codebases where they had drifted apart, and re-implementing them here would restart that drift with this pipeline as the third copy. The concrete saving is not lines but decisions already made and tested — atomic writes with parent-directory creation, `utf-8-sig` readers that strip a BOM, a `slot_filling` pass limit that terminates on mutually referential placeholders, and structured output that reports *why* it failed. *Reversible:* yes for any single call, and the pin is a tag, so a toolkit change cannot arrive unannounced.

**Juror votes are validated by a JSON Schema at the library boundary, not by pipeline code.** *Alternatives:* `extract_json_from_text` plus a hand-written check that every name is in the catalog — which is what the previous draft of this spec specified. *Why:* the constraint and the parse are the same concern, `complete_structured` already does both and reports the outcome in one object, and a hand-written check is a second place where "in the catalog" could be defined slightly differently. It also removes the failure mode requirement 22 exists to prevent: with the library returning `None` on failure, there is no code path that could truncate a malformed response into a partial set. *Reversible:* yes, but there is no reason to.

**Jurors are called with `mode="prompt"`, not `"auto"`.** *Alternatives:* `"auto"` (the toolkit's default: native `response_format`, falling back to prompt); `"grammar"` for vLLM endpoints. *Why:* the panel is a measuring instrument, and `"auto"` would silently give different jurors different constraint mechanisms depending on what their endpoint implements — a juror whose tokens were constrained is not comparable to one whose weren't, and cohesion across the two is not a meaningful number. The toolkit's own module docstring records a measured case where a decode-time constraint made the answer worse. Validation is identical in all three modes, so asking plainly costs nothing but a slightly higher `repaired` rate. *Reversible:* yes, one config field — but changing it invalidates cross-release cohesion comparisons, so it bumps `prompt_version`.

**The task is never reformulated.** Every juror, every question, and every training target is the set-valued task the corpus already states. *Alternatives:* recast as per-(record, tool) binary "call or not", which would have made 98,766 two-class examples and unlocked classifier-based tooling; recast as cardinality buckets. *Why:* the reformulation buys access to methods that need a fixed class space, and pays for it by measuring something the model will never be asked to do — a per-tool decision made in isolation, without the set-level interactions (`{hold_other}` means *another tool covers this*, which is a statement about the set) that the marker DSL is largely about. A jury that answers the real task needs no reformulation, and its errors are the errors that matter. *Reversible:* the binary view can be reconstructed from jury votes at any time as a diagnostic, so nothing is lost by not adopting it as the primary representation.

**An LLM jury, not Confident Learning.** *Alternatives:* Cleanlab over a proxy label space; a trained multi-label classifier; a single strong LLM as judge. *Why:* Cleanlab needs a fixed class space and this corpus has 14,411 tool names with a modal frequency of 35, so adopting it requires reshaping the task — see the decision above. A generative jury needs no class space at all: it answers the task directly, and its disagreement with the corpus is a signal in the corpus's own units. One judge would be cheaper and is rejected because a single model's agreement is indistinguishable from a single model's bias, and this corpus was already labelled by a single model. *Reversible:* yes, and cheaply — the jury is confined to `ai_review/`, its output is three numbers and a set per record, and Cleanlab can be added later over whatever label space the first release establishes.

**Panel diversity is measured with `model_family`, and `"unknown"` disqualifies.** *Alternatives:* trust the juror names as declared in config; count distinct model strings. *Why:* distinct model strings are not distinct families — three Qwen checkpoints are one family — and the function that knows the difference is already in the toolkit. Its contract is explicit that unrecognised names all collapse to `"unknown"`, which would let two unrecognised jurors pass a "three distinct families" check while being unmeasured. Failing closed means a new model must be added to the toolkit's family table before it can serve on a panel, which is the right amount of friction. *Reversible:* yes, panel config — but the table lives in the library, so adding a family is a toolkit release.

**Jury votes never become labels without a human.** *Alternatives:* auto-apply consensus where the jury is unanimous; auto-apply everywhere and human-check a sample. *Why:* the corpus is already two-thirds machine-labelled and has been relabelled once. Overwriting machine labels with other machine labels is the accumulation-versus-replacement distinction the model-collapse literature turns on, and replacement is the losing side of it. The opt-in `jury_consensus` tier exists for teams that need volume, kept in a separate tier with its own error bar and barred from test, so the choice is visible in the artifact instead of buried in it. *Reversible:* the tier is a flag; but data shipped as human-validated when it was not cannot be un-shipped.

**One set distance, with `δ(∅,∅) = 0`.** *Alternatives:* exact-set-match only; per-tool micro-averaging; treating the empty set as a distinct class. *Why:* exact match throws away the difference between "one tool too many" and "completely wrong", which is most of the useful gradient. The empty-set convention is load-bearing on 35.4% of the corpus. *Reversible:* no, in practice — cohesion and conflict computed under a different convention are not comparable across releases.

**Two triage axes, not one score.** *Alternatives:* a single priority number, as a Cleanlab score would give. *Why:* a unanimous jury disagreeing with the corpus is a label problem; a split jury disagreeing with the corpus is usually a guideline problem. They go to different people and produce different fixes. *Reversible:* yes.

**Bucket thresholds are provisional until the pilot measures them.** *Why:* every threshold here is currently a guess, and a guess that decides which 3,500 of 21,172 records humans look at is worth one measurement. The pilot's bucket-precision gate is the only thing standing between "the jury found the errors" and "the jury found something". *Reversible:* yes, and expected to change exactly once.

**The key pool lives in the pipeline, not in `agent-toolkit`, and passes credentials per call.** *Alternatives:* add the pool to the library's LLM client; express it as a `ConfigResolver`. *Why:* the library has one specified consumer for it, and growing a shared library for a single caller is how libraries acquire features nobody else wants; cost accounting per key is a pipeline concern anyway. The resolver route is not merely inelegant but unavailable: `set_config_resolver` installs one resolver process-wide and `resolve_config` keys on the model name, so per-call key rotation cannot be expressed through it. Explicit `api_key=` and `base_url=` arguments are documented to win over the resolver, which is exactly the hook the pool needs. *Reversible:* yes — it graduates when a second consumer appears, which is the right trigger.

**Token budgets are enforced on estimates, and the spec says so.** *Alternatives:* read `usage` from the response (not available — `Completion` discards it); parse provider billing APIs; skip budgeting. *Why:* the honest options are an estimate or nothing, and an estimate with declared headroom stops a runaway run while a missing budget does not. Claiming measured consumption when the number came from `count_tokens` would be worse than the imprecision, especially given the ±33–64% drift the toolkit documents on Vietnamese. *Reversible:* yes, and cheaply, once the toolkit surfaces `usage` — at which point this becomes measurement and the assumption below retires.

**Defects are quarantined, never auto-repaired.** The 48 label/assistant contradictions could have been resolved by preferring the assistant message — and upstream did resolve them, deliberately and outside this pipeline, which is the right place for that call. The 722 out-of-catalog labels could be truncated to the catalog. *Alternatives:* exactly that, silently. *Why:* both "fixes" are guesses about which of two disagreeing sources is right, applied at scale, invisibly. A quarantine file with 722 records is a morning's work for someone who knows the corpus and a permanent record of what was decided; an auto-repair is a data cascade with a clean-looking count. *Reversible:* re-admission is an explicit command that versions the pipeline.

**PII is replaced with stable placeholders, not deleted or hashed.** *Alternatives:* delete the span; hash it; drop the record. *Why:* the ground truth of this corpus turns on whether a required value was supplied. Deleting a phone number converts a correct call into what now looks like a correct `{hold_missing}`, silently inverting the label on ~2% of records. A stable typed placeholder preserves suppliedness and co-reference while carrying no personal data. *Reversible:* only from the vault, which never leaves the raw tier — so getting this right the first time matters.

**`data/raw/` is outside DVC.** *Alternatives:* DVC-track everything and rely on a remote that is never configured; encrypt the vault in place. *Why:* invariant 3 says the vault is never tracked, and the only way to check that cheaply is for the whole directory to be outside DVC — a per-file exclusion is a line someone deletes by accident. The source file loses nothing by it: its identity is a SHA-256 in `params.yaml`, which is what the ingest gate already asserts. *Reversible:* no, and deliberately so.

**The test split is 100% human-validated, at any budget.** *Alternatives:* validate a sample of test; let jury consensus fill it. *Why:* every number the release reports is computed on test. A test split that is machine-labelled measures agreement with a model, not correctness, and no amount of downstream care recovers from that. It is the single most load-bearing rule here. *Reversible:* no.

**Group split on catalog fingerprint ∪ dedup cluster.** *Alternatives:* random split; split on `source_index`. *Why:* `source_index` is unique per record and provides no protection — measured, not assumed. Records sharing a tool catalog are near-variants of one scenario (largest such group: 112 records), and a random split puts variants of the same scenario on both sides, inflating every metric. *Reversible:* yes, but every metric produced before the fix would be void.

**Phase folders are named for what happens in them, in run order.** *Alternatives:* concern-oriented folders (`jury/`, `pii/`, `labelstudio/`) as an earlier draft of this spec specified; a flat module list. *Why:* the unit of work here is a DVC stage, and a reader arriving from `dvc.yaml` should land in the right directory without a map. `ai_review/` and `human_review/` next to each other also state the architecture's central idea — machines look first, humans look second, and the first decides what the second sees — where a concern-oriented tree buries it. *Reversible:* yes; it is a rename.

**The pipeline is DVC stages, not a service.** *Alternatives:* Airflow/Prefect; Celery jobs in the platform API; a shell script. *Why:* every stage is a pure function from artifact to artifact, which is what DVC models natively — and data lineage plus reproducibility from a commit hash is the requirement, not scheduling. *Reversible:* yes; each stage is a CLI command an orchestrator could call unchanged.

**Label Studio, not Argilla, and not the DataForce annotation service yet.** *Alternatives:* Argilla; build the platform's own UI now; Doccano; Prodigy. *Why:* Argilla has shipped no functional change in seventeen months. Building our own UI first inverts the order of risk — it spends a quarter before anyone has answered whether the *questions* are answerable. Label Studio is maintained, its dynamic-choices feature fits the per-record tool catalog precisely, and generating its XML is a file we own rather than a format we adopt. *Reversible:* yes, cheaply — Label Studio is touched only by `human_review/labelstudio/`.

**Assumption:** Label Studio Community honours `maximum_annotations` for multi-annotator overlap. The docs describe collaborative labelling as available in both editions, while review workflows and agreement analytics are Enterprise. S0 verifies this empirically; if it does not hold, overlap comes from publishing the same tasks to one project per annotator and joining on `rid`.

**Assumption:** `potion-multilingual-128M` embeds Vietnamese well enough for near-duplicate detection. Checked by a retrieval sanity test on 200 hand-paired records, with a sentence-transformer fallback.

**Assumption:** 3 characters per token for Vietnamese cost estimates, cross-checked against `count_tokens`. Neither is a measurement — `count_tokens` is itself an estimate with documented drift of −33% to +64% on Vietnamese, and the toolkit surfaces no actual usage. The budget therefore carries declared headroom and the run labels every token figure "estimated".

**Assumption:** enough API keys exist across ≥3 model families recognised by `model_family` to run a 3-juror sweep of ~101M estimated input tokens within the release window. If keys are concentrated in one family, requirement 25 binds and the panel — not the requirement — is what changes.

**Assumption:** the residual-error estimate from the audit sample is reported as a property of the release and consumers are expected to read it. The alternative — refusing to ship anything unvalidated — is not on the table at 44 person-days.

**Assumption:** annotators are internal Vietnamese speakers on a self-hosted Label Studio inside the network boundary.

## Versions

| Component | Pinned | Source |
|---|---|---|
| Python (pipeline) | 3.12.14 | [endoflife.date, released 2026-08-12](https://endoflife.date/python) — 3.12 for widest library compatibility; the platform API stays on 3.14 |
| agent-toolkit | `agent-toolkit[llm] @ git+https://github.com/giangchicken/agent-toolkit.git@v0.1.0` | Released 2026-08; not on any registry, so a direct-URL dependency pinned to the tag. Needs `git` on the installing machine. |
| Label Studio | 1.23.0 | PyPI, 2026-03-13 (checked live) — run as the official Docker image |
| label-studio-sdk | 2.1.1 | PyPI, 2026-08-10 (checked live) |
| semhash | 0.4.1 | PyPI, 2026-01-20 (checked live) |
| model2vec | 0.9.0 | PyPI, 2026-08-12 (checked live); model `potion-multilingual-128M` |
| crowd-kit | 1.4.2 | PyPI, 2025-10-13 (checked live) — human verdicts only |
| krippendorff | 0.8.2 | PyPI, 2025-11-03 (checked live) — nominal α; set-valued α is ours |
| pandera | 0.32.1 | PyPI, 2026-06-29 (checked live) |
| DVC | 3.67.1 | PyPI, 2026-03-31 (checked live) |
| mlcroissant | 1.1.0 | PyPI, 2026-04-16 (checked live) |

`agent-toolkit[llm]` brings `openai`, `tenacity`, `aiohttp`, `tiktoken`, and `jsonschema`; the pipeline does not depend on any of them directly and must not import them. Its core brings `json-repair` and `pyyaml`. `tiktoken` fetches its vocabulary over the network on first use, so CI sets `TIKTOKEN_CACHE_DIR` against a populated cache — otherwise a `count_tokens` call in an offline runner reaches for the network.

Dropped relative to the first draft, and worth noting because it shrinks the dependency surface: **cleanlab** (needs a fixed class space this corpus lacks), **scikit-learn** (was only there for cleanlab's cross-validated probabilities), and **snorkel** 0.10.0 (last released 2024-02-27; the marker rules are ~200 lines of plain Python and do not justify pulling torch and tensorboard).

Rejected: **Argilla** 2.8.0 — last release 2025-03-10, no functional commit since (checked on GitHub). **Great Expectations** 1.20.0 — requires `<3.14` and is heavy for artifact-shape checks; pandera covers it.

## Invariants

1. **Nothing is lost between stages.** For every stage, `output_count + quarantined + deduped_out == input_count`. *Check:* the gate runner asserts the reconciliation on every stage, not just ingest, and writes it to `metrics.json`.
2. **`rid` is stable.** Re-ingesting the same source produces byte-identical `rid` values regardless of record order. *Check:* shuffle a fixture, re-ingest, compare the `rid` set.
3. **No PII downstream of `scrub`, and the vault is untracked.** No artifact in `interim/1_prepared/scrubbed.jsonl` or later matches a literal PII pattern. `pii_vault.jsonl` is in `.gitignore`, in no `.dvc` file, and in no `dvc.yaml` output list; `data/raw/` is absent from DVC entirely. *Check:* a gate scanning every release-tier file, plus a repo test asserting all four of those facts about the vault path.
4. **The task representation never changes.** Every juror vote, correction, and exported label is a set of names drawn from that record's catalog. *Check:* a pandera check on every artifact carrying a label, asserting `set(label) <= set(catalog names)`, applied to jury votes and corrections alike; for votes it is a second line of defence behind the schema `enum`.
5. **Every juror vote is valid or an abstention.** No stored vote names an out-of-catalog tool, and no vote is a truncation of a malformed response. *Check:* structurally guaranteed by `complete_structured` returning `None` when validation fails, plus a test feeding malformed, prose-wrapped, over-long, and out-of-catalog responses through a stubbed endpoint and asserting each becomes either a clean set or an abstention carrying `error` and `raw`.
6. **Votes are reproducible and key-independent.** Re-running the jury with a warm cache changes nothing; re-running cold at temperature 0 reproduces the votes; the same vote is produced regardless of which key served it. *Check:* two cold runs over a 20-record fixture against a recording proxy, diffed; a test that forces key rotation mid-run and diffs the votes.
7. **The panel is diverse, measured, and clean.** ≥3 jurors, ≥3 distinct `model_family` values, no `"unknown"`, and no primary-panel juror from the corpus's labelling family. *Check:* the jury gate reads `config/panel.yaml`, calls `model_family` on every juror, and fails on violation; a control juror must be explicitly tagged `control` to be admitted at all.
8. **Marker tokens survive templating and parsing.** A `{trigger}`, `{hold_missing}`, `{constraint}`, or `{turn_trigger}` token present in the source system message is present, byte-identical, in the adapter's output and in the rendered juror prompt. *Check:* a test rendering a template whose fill values contain marker tokens and asserting `slot_filling` altered none of them, alongside the adapter's verbatim-marker test.
9. **`δ(∅,∅) = 0`.** *Check:* a property test over random set pairs asserting symmetry, `δ(A,A) = 0` including the empty case, `δ ∈ [0,1]`, and no `nan` anywhere.
10. **No jury output reaches an annotator.** No Label Studio payload contains a juror vote, a juror's reasoning, consensus, cohesion, conflict, bucket, stratum, or the generator's proposed answer. *Check:* a contract test asserting the payload key set equals an explicit allowlist — an allowlist, not a denylist, so a new field cannot leak by being forgotten.
11. **Corrections stay in the catalog.** Every stored correction is a subset of that record's own catalog, or the explicit empty set. *Check:* structurally guaranteed by dynamic choices, and asserted again at pull time, because a structural guarantee in someone else's UI is not one of ours.
12. **No group spans splits.** No `group_key` appears in more than one of train/val/test, and none in a curve slice that is absent from train. *Check:* a set-intersection assertion in the split gate.
13. **Test is fully human-validated.** Every test record has `validation.status ∈ {original, corrected}` — never `unvalidated`, never `jury_consensus`. *Check:* export gate.
14. **Label and assistant agree on the way out.** For every exported record, `meta.label` equals the parsed assistant message. *Check:* export gate, running the same assertion that counted 48 of these before the source was fixed.
15. **Releases are reproducible.** `dvc repro` from a clean checkout at a given commit reproduces every artifact's SHA-256. *Check:* CI runs it on the S0 fixture and diffs `MANIFEST.sha256`.
16. **The sampling design is reconstructible.** Every annotated record records which stratum selected it and with what probability. *Check:* the residual-error estimator refuses to run when any annotated record lacks a stratum.
17. **The library is not re-implemented.** No module under `src/dataforce/` defines a hash helper, a JSONL reader or writer, an atomic-write context manager, a JSON-from-text extractor, a template filler, or a retry wrapper. *Check:* a lint test over the source tree asserting `agent_toolkit` is the importer of record for each, and that `openai`, `tenacity`, `tiktoken`, and `jsonschema` appear in no pipeline import.

## Error Behavior

Gates fail loudly and stop the DAG. A failed gate writes `data/<stage>/GATE_FAILED.json` with the assertion, the observed value, the expected value, and the offending record IDs (capped at 100), and exits non-zero so `dvc repro` halts. No stage consumes an input whose gate did not pass.

Every provider failure arrives as an `LLMError` subclass, so each stage that calls a model wraps its dispatch in one `except LLMError` and maps it to the row below. Nothing catches bare `Exception` around an LLM call.

| Situation | Behavior |
|---|---|
| Source SHA-256 differs from `params.yaml` | Hard stop. A changed source is a new dataset version, decided by a human, never merged silently. |
| Defect count moves >±10% from declared | Hard stop with the delta. The declared counts are the contract with the corpus. |
| LLM unavailable during PII verification (`LLMAPIError`) | Stage stops; already-verified spans are kept and the stage resumes from its checkpoint. A record with unverified hits never advances — failing open on PII is the one failure this pipeline will not take. |
| PII verification returns a response that fails its schema | The span is unverified, not negative. The record goes to `quarantine/scrub/pii_uncertain.jsonl`. |
| A juror is unreachable for a whole run | The run continues on the remaining jurors if ≥3 recognised families remain, and records the reduced panel on every affected record. Below the diversity floor the stage stops rather than quietly producing weaker signal. |
| `LLMRateLimitError` on one key | Per-key backoff, dispatch continues on the rest. |
| `ProviderQuotaExceededError` on one key | Key quarantined for the cooldown declared in `config/panel.yaml` — not from `retry_after`, which the library never populates. Throughput degrades, the run does not stop. Reported per key. |
| All keys in a group exhausted | That juror is marked incomplete for the affected records; those records keep the votes they have and are re-queued for the next jury run rather than being scored on a partial panel. |
| `LLMAuthenticationError` or `LLMConfigError` on any key | Hard stop, not a retry and not a quarantine. A bad key is a configuration defect, and the toolkit already classifies it as non-retriable; treating it as exhaustion would hide it behind degraded throughput. |
| Juror response fails schema validation after one retry | Recorded as an abstention with `ValidationInfo.raw` and `.error` retained. Never truncated into a partial set. |
| Invalid-vote rate above 5% for a juror | Jury gate fails. A juror that cannot follow the output contract is a prompt or model problem, and its votes are not usable as signal. |
| `repaired` rate above a declared threshold for a juror | Warning in `jury_report.json`, not a stop. The votes are valid; the juror is just wrapping them in prose, which is a prompt-quality signal worth watching before it becomes an invalid-vote problem. |
| Jury token estimate exhausted mid-run | Clean partial stop; cast votes retained; run status `partial`; records with fewer than 3 valid votes are excluded from triage rather than bucketed on thin evidence. |
| LLM unavailable during question generation | Per [`guided-validation`](../guided-validation/spec.md): record marked `generation_failed`, run continues, task never published without a question. |
| Label Studio unreachable on publish | Retry with backoff, 5 attempts; then fail the stage with the tasks already pushed recorded, so a resume does not duplicate. Publishing is idempotent on `rid`. |
| Response has `verdict=incorrect` with no correction | Rejected, not repaired. Returned to the queue with the reason; counted in `metrics.json`. |
| α below 0.667 at the pilot gate | Hard stop with the per-focus breakdown. The remedy is a guideline revision and a re-pilot, never lowering the threshold. |
| α above 0.95 | Warning plus a mandatory written review note in the datasheet. Not a stop. |
| `likely_label_error` precision below 0.30 at the pilot gate | Hard stop. The panel or the thresholds change before 21k records depend on them. |
| Annotator below 0.85 on gold | Their work is held pending review; already-submitted answers are re-queued for a second opinion rather than discarded. |
| Group leakage or n-gram overlap detected | Hard stop. Every metric computed on a leaked split is void, so there is nothing to salvage by continuing. |

Two failures have no automated detector. A **plausible but wrong question** — one that reads well and asks about the wrong turn — is caught only by the flag rate, which is why 10% is a gate. And a **jury that is confidently wrong in the same direction as the corpus** produces `agreed` records that are quietly incorrect; only the uniform random audit sample can see those, which is why it is uniform and why it is never allowed to be repurposed for anything else.

## Testing Strategy

- **Contracts.** Every artifact has a pandera schema; a round-trip test writes with `write_jsonlines`, reads with `read_jsonlines`, and validates. A schema change that is not accompanied by a stage change fails.
- **Set operations.** Property tests over random set pairs for `δ`: symmetry, identity including the empty case, range, no `nan`. Majority consensus against hand-worked vote sets, including the case where consensus differs from every individual vote. Set-valued α against a hand-computed example, plus the degenerate check that α with an identity distance equals the `krippendorff` package's nominal α on the same data.
- **Adapter.** Fixtures covering all 13 observed `meta` key-sets, each label cardinality, catalog sizes 0 / 1 / 8 / 20, and malformed `TOOLS:` blocks. One test asserts marker tokens survive parsing **verbatim** — a parser that strips them would pass every other test while destroying the annotator's only evidence.
- **Templating.** A test filling a template whose values contain `{trigger}` and `{hold_missing}` and asserting `slot_filling` returned them untouched, which is invariant 8. A second asserts a `{{placeholder}}` the mapping does not cover is left in place rather than blanked.
- **Source-integrity gate.** A fixture containing one instance of each defect class, asserting each lands in the right quarantine file with the right label, and that the main path count drops by exactly four.
- **PII.** A hand-built Vietnamese fixture of spoken phone numbers, spoken emails, national IDs, prices, dates, and order references — asserting recall on the first three and *no* replacement on the last three. A tone-stripped variant of the same fixture asserts `normalize_text` matching catches `khong chin khong mot`. Placeholder stability is tested by a record mentioning the same number twice. A test asserts the vault path is absent from `dvc.yaml` and every `.dvc` file and present in `.gitignore`, and that `data/raw/` is not a DVC output anywhere.
- **Jury.** A stubbed OpenAI-compatible endpoint returning: a clean array, a fenced array, prose-wrapped JSON, an out-of-catalog name, a non-array, and empty — asserting each becomes a valid set or a clean abstention, and that `repaired` is true for exactly the fenced and prose-wrapped cases. Panel diversity gate against a config with three models from one family, and against one containing a name `model_family` does not recognise. Cache determinism across two runs. Key-pool failover: a stub returning 429 on one key and a quota error on another, asserting the run completes on the rest and the votes are identical to a single-key run. `LLMAuthenticationError` asserted to stop the run rather than quarantine the key. Cost accounting against a fake tokenizer.
- **Toolkit boundary.** A test asserting no pipeline module imports `openai`, `tenacity`, `tiktoken`, or `jsonschema`, and that the reuse table's functions are imported from `agent_toolkit` rather than redefined — invariant 17. Plus one integration test that runs `agent-toolkit`'s own `tests/consumer_smoke.py` against the environment the pipeline installs, so a bad resolution of the git dependency is caught here rather than at the first jury run.
- **Triage.** Bucket assignment over hand-built (cohesion, conflict) grids including the boundaries; audit sample-size formula against worked values (`p=0.05, e=0.02 → 457`); a test asserting records with fewer than 3 valid votes are excluded rather than bucketed.
- **Dedup and grouping.** Known duplicate pairs from the corpus; assertion that `source_index` is rejected as a group key and that the largest catalog group (112 records) stays intact through splitting.
- **Label Studio integration.** The generated config validated against a live Label Studio instance in CI via testcontainers — creating the project, pushing three tasks, and pulling back a submitted annotation. The invariant-10 allowlist test runs on the built payload without needing the server.
- **Split and decontamination.** A fixture with a deliberately planted group spanning what would be a random split, asserting the gate catches it; a planted 13-gram overlap, asserting the same; a curve-slice test asserting 25% ⊂ 50% ⊂ train and no group crossing a slice boundary.
- **End-to-end (S0 as a test).** The 50-record smoke run *is* the integration test: `dvc repro` from raw to release against stubbed jurors, a stubbed generator LLM, and a containerized Label Studio, asserting a byte-identical `MANIFEST.sha256` on a second run. This passing is the definition of the pipeline being done.
- **Reproducibility.** CI re-runs S0 from a clean checkout and diffs the manifest, which is invariant 15.

## Out of Scope

- **Image, audio, and video.** Explicitly deferred; the platform spec's image controls go with them.
- **Model training and evaluation.** This pipeline produces a dataset, a metric definition, the learning-curve *slices*, and a zero-shot jury baseline. Running the fine-tune, training on those slices to produce the curve, and any eval harness belong to a separate spec.
- **Actual-token accounting.** Requires `usage` on `agent-toolkit`'s `Completion`. Filed against the library; this pipeline budgets on estimates and says so.
- **Extending `agent-toolkit`.** Gaps found here — `usage`, `retry_after`, a family-table entry for a new juror — are filed against that repository and fixed by a release there, not patched locally. The pin is a tag for exactly this reason.
- **Confident Learning and classifier-based label auditing.** Deferred by decision, not dropped — revisit after the first release establishes a label space and the jury's bucket precision is known.
- **Synthetic data generation.** The corpus is already two-thirds machine-labelled; generating more before the existing labels are validated is the model-collapse failure the handbook describes. Revisit after the first release measures the residual error rate, and only for the long-tail strata.
- **Active learning loops.** The jury is a one-shot ranking per release, not a model that retrains as annotations arrive.
- **Fine-tuning a juror.** Jurors are off-the-shelf models behind API keys.
- **The DataForce annotation service.** Deferred, not cancelled — the pilot decides whether it is worth building, and [`dataforce-platform`](../dataforce-platform/spec.md) remains the spec for it.
- **Automatic write-back to the source file.** Export produces an artifact; putting it anywhere is a human step.
- **Multi-language.** Vietnamese only, for the corpus, the questions, and the PII detectors.
- **Cross-border transfer review.** Real under Data Law 60/2024 and newly sharper here, because the jury sends conversation transcripts to several external LLM endpoints. It is a legal review of where the data and those endpoints sit, not a pipeline stage, and it must happen before the first jury run against any offshore endpoint — not before the release.

---

**Grounded in:** measurements over the full corpus (counts in Context are reproducible with the pipeline's `dataforce profile` command) · [`agent-toolkit` v0.1.0](https://github.com/giangchicken/agent-toolkit), read from source for the reuse table above · [Label Studio](https://labelstud.io/guide/setup) · [SemHash](https://github.com/MinishLab/semhash) · [crowd-kit](https://github.com/Toloka/crowd-kit) · [DVC](https://dvc.org) · [Croissant](https://github.com/mlcommons/croissant) · Gebru et al., *Datasheets for Datasets* (CACM 2021) · Bender & Friedman, *Data Statements* (TACL 2018) · Northcutt et al., *Pervasive Label Errors* (NeurIPS 2021) · Sambasivan et al., *Data Cascades* (CHI 2021) · Shumailov et al., *Model collapse* (Nature 2024) · Zheng et al., *Judging LLM-as-a-Judge* (NeurIPS 2023) · Penedo et al., *FineWeb* (arXiv:2406.17557)
