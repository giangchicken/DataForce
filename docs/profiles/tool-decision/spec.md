# Profile: `tool_decision` — Tool Selection over Vietnamese Call-Centre Text

## What

The first profile for the [annotation pipeline](../../annotation-pipeline/spec.md), and the first real dataset through it: 21,172 Vietnamese call-centre conversations in `fc_train_final.json`, each pairing a tool catalog with a conversation, labelled with the set of tools that should fire.

This document specifies only what is specific to this dataset and this task. The fifteen stages, the gates, the jury, the triage buckets, the agreement statistics, and the release artifact are the core's, written once. This profile supplies **seven pieces** and composes with the `text` modality's **four**:

| Piece | Owner | This profile / modality |
|---|---|---|
| source adapter | profile | parse the `TOOLS:` block, preserving the marker DSL verbatim |
| answer schema | profile | `{"type":"array","items":{"type":"string","enum":<this record's catalog>}}` |
| `delta` | profile | `1 − |A∩B| / |A∪B|`, with `δ(∅,∅) = 0` |
| `consensus` | profile | tools included by a strict majority of valid votes |
| validity checks | profile | four checks, all provable without a human |
| question templates | profile | per [`guided-validation`](../../guided-validation/spec.md), focus by marker rule |
| exporter | profile | SFT JSONL in the source `messages` shape |
| content loader | `text` | system / user / assistant turns as text parts |
| embedder | `text` | `model2vec` `potion-multilingual-128M` |
| privacy detectors | `text` | Vietnamese spoken-form personal data |
| display control | `text` | escaped `HyperText` |

The prediction task is **never reformulated**. Every juror, every question, and every training target is the set-valued task the corpus already states: given a catalog and a conversation, name the set of tools that should fire — possibly the empty set.

## Context

### What the corpus contains

Measured over the whole file rather than sampled, most recently 2026-08-18:

| Property | Value |
|---|---:|
| Records | 21,172 |
| File size | 126 MiB |
| Answer cardinality 0 / 1 / 2 / 3 | 7,498 (35.4%) / 10,596 (50.0%) / 2,757 (13.0%) / 321 (1.5%) |
| Distinct tool names in labels | 14,411 |
| Most frequent single tool | 35 occurrences |
| Catalog size per record | 0–20 tools |
| Distinct catalog fingerprints | 17,596 (16,293 singletons; largest non-empty group 112) |
| Distinct `meta` key-sets | 13 |
| Labelled by `gemma-4-31B-it` | 14,241 (67.3%) |
| Carrying `orig_label` — already relabelled once | 1,358, of which 1,346 changed |
| Duplicate user turns | 491 records (2.32%) |
| Duplicate (system, user) pairs | 1 |
| Prompt size, system + user | mean 4,750 chars · p50 4,446 · p90 6,310 · p99 17,044 |
| Total prompt characters | 100,557,307 |

Three kinds of invalid record are detectable without a single human judgment, and a fourth was fixed in the source on 2026-08-17:

| Validity check | Count | Why a failure is fatal for SFT |
|---|---:|---|
| `label_assistant_mismatch` | **0** — was 48 (0.227%) | Fixed upstream. The gate stays, expecting 0: the assistant message *is* the training target, and a regression trains the model on the losing side of two disagreeing sources. |
| `label_not_in_catalog` | **722** (3.41%) | The target names a tool the record never offered. Unlearnable, and it teaches hallucination. |
| `empty_catalog` | **841** (3.97%) | Either genuinely toolless prompts or a parser miss. The two must be told apart by hand before either is trusted, so this is a quarantine for triage, not a verdict. |
| `label_cardinality_anomaly` | declared in `params.yaml` | Guards against a catalog or parser change inflating answer size. |

**The source file changed three times in four weeks, and that is the load-bearing observation.** Measured with one parser across the versions on disk, `label_assistant_mismatch` was 48 in the 2026-08-17 backup and is 0 in the current file. Every count here therefore describes one SHA-256, not "the corpus" — which is exactly why the core pins expected counts in `params.yaml` and hard-stops when they move.

The 722 and 841 figures are **parser-dependent** and are the numbers to reproduce with the adapter of requirement 1, not before it. An independent regex over `^\s*\[Name\]` reads 588 and 680 on both the current file and the 2026-07-24 backup, so the difference is a catalog-parsing convention rather than a corpus change. The adapter settles the convention, and `params.yaml` is populated from the adapter's own count on first run.

`source_index` is unique per record — 13,366 distinct over 13,366 records. It looks like a grouping key and is not one; splitting on it gives no leakage protection. Measured, not assumed.

That upstream fix also closed a discrepancy in our own documents: [`guided-validation`](../../guided-validation/spec.md) reports 7,486 zero-label records counted from the assistant message against 7,498 from `meta.label`, a 12-record difference that was the arithmetic of those 48. Both counts are now 7,498, and `guided-validation` has been corrected to match — its table read 7,486 / 10,608.

### Why this task has no fixed class space

14,411 distinct tool names with a modal frequency of 35 means no fixed class space exists. Confident Learning, label-error classifiers, and anything needing `predict_proba` over a label vocabulary cannot be applied to this corpus as it stands. The alternative is not to reshape the task until such a method fits — it is a method needing no class space at all, which is what a generative jury answering the real task is.

### Personal data in the corpus

The records are call-centre transcripts, and personal data appears in **spoken form**, which no off-the-shelf scrubber detects:

| Signal on the user turn | Records | Share |
|---|---:|---:|
| Run of ≥6 consecutive Vietnamese number words | 3,485 | 16.46% |
| Literal 9–12 digit run | 770 | 3.64% |
| Literal Vietnamese phone number | 435 | 2.05% |
| `@` or its spoken form | 238 | 1.12% |
| Literal email address | 97 | 0.46% |

The digit-word signal is a **superset** — it also matches prices, dates, and reference codes — so it bounds the population needing review rather than counting personal data. The literal signals are not a superset: they are personal data. Vietnam's Personal Data Protection Law 91/2025/QH15 has been in force since 1 January 2026, with Decree 356/2025/ND-CP as implementing guidance replacing Decree 13/2023. Redaction is a legal requirement here, not a nicety.

### The marker DSL

Each catalog entry carries clauses written in a small marker language — `{trigger}`, `{hold_other}`, `{hold_missing}`, `{constraint}`, `{turn_trigger}`, `{or}` — which is simultaneously the deterministic rule source, the annotator's only evidence, and the thing most easily destroyed in passing. Confirming the glossary in writing is the blocking prerequisite [`guided-validation`](../../guided-validation/spec.md) declares it to be, and the pilot is where that confirmation is obtained.

## Requirements

### The adapter

The four validity checks below are all provable by counting — no person decides any of them — which is why `remove_invalid` runs first. Together they move 1,563 records (7.4%) out of the main path before the jury spends a token on them.

1. The adapter parses the `TOOLS:` block into a structured catalog — name, purpose, `call_when`, `hold_when`, required parameters, per-parameter constraints — and **preserves every marker token byte-identically**. A parser that strips them would pass every other test while destroying the annotator's evidence.
2. `answer_space` per record is the list of catalog tool names. `validity_checks()` returns the four checks above. `group_key` is the catalog fingerprint, and never `source_index`.
3. `rid = compute_hash(system ‖ user ‖ assistant)[:16]`, so the identity is independent of position.
4. Fixtures cover all 13 observed `meta` key-sets, each answer cardinality, catalog sizes 0 / 1 / 8 / 20, and malformed `TOOLS:` blocks.

### The answer, δ, and consensus

5. The answer is a **set of tool names drawn from that record's own catalog**, and the empty set is a first-class answer, not a missing value. No stage may substitute a per-tool binary, a coarse proxy class, or a cardinality bucket.
6. `delta(a, b) = 1 − |a ∩ b| / |a ∪ b|`, with **`delta(∅, ∅) = 0` by definition**. That convention is load-bearing: 35.4% of this corpus is the empty set, and a Jaccard implementation returning `0/0 → NaN`, or treating two empty sets as maximally distant, would make the zero-label population — the part carrying the corpus's real difficulty — look like the part with least agreement.
7. `consensus` is the set of tools a strict majority of valid votes included. It can be a set no individual juror proposed, which is acceptable for a ranking signal and is why the core forbids it from becoming a label on its own.
8. Marker-DSL rules — missing required parameter, `{hold_missing}` satisfied, `{trigger}` keyword in the last turn, `{constraint}` violated, `{turn_trigger}` scope violation — act as hard validity constraints and as the validity checks of requirement 2. They may additionally be admitted as one **rule juror** producing a set, but only if their gold set-F1 clears the same floor as any other juror.

### The text modality's privacy detectors

9. Detectors cover, in both literal and Vietnamese spoken form: phone numbers, email addresses, national ID numbers, bank account numbers, and full personal names in the customer turn. Spoken-form coverage includes digit words (`không`…`chín`, plus `mốt`, `tư`, `lăm`), spoken `@` (`a còng`), and spoken punctuation (`chấm`, `gạch dưới`).
10. Detection runs against both the raw text and `string_utils.normalize_text(text, remove_tone_marks=True)`, so a transcript spelling `khong` or `chin` is not missed while patterns stay written in correct Vietnamese. Offsets resolve back onto the original; the normalized form is a matching aid and is never stored.
11. Verification uses a ±80-character window through `llm.complete_structured` against a fixed classification schema, deciding personal data versus price, date, or reference code. The regex layer sets recall; the LLM layer sets precision. The digit-word signal fires on 3,485 records, so the findings report is read to tune the patterns and the prompt, and `enable_redact` is turned on once it looks right.
12. Placeholders are stable within a record, so a phone given in turn 3 and confirmed in turn 7 is `<PHONE_1>` both times. **This is why replacement, not deletion, is specified:** the ground truth of this corpus turns on whether a required value was *supplied*, so deleting a phone number converts a correct call into what looks like a correct `{hold_missing}`, silently inverting the label on ~2% of records.

### The jury panel

13. The panel excludes the `gemma` family from primary duty: 14,241 records (67.3%) were labelled by `gemma-4-31B-it`, so a `gemma` juror measures lineage rather than correctness. One runs as an explicitly tagged **control**, and the gap between its agreement with the corpus and the panel's is a direct estimate of how much of this dataset is one model's opinion.
14. The prompt lives at `config/prompts/jury_vote.v1.txt` and asks the corpus's task in Vietnamese, with the record's system message and conversation filled in by `slot_filling`.
15. Juror weights are mean set-F1 against human-validated labels, with a declared floor below which a juror is dropped for that release.
16. Escalation is a 3-juror sweep over the corpus, then 7 jurors on records showing conflict or low cohesion.

### Thresholds and the ladder

17. The release's primary metric is **exact-set-match accuracy** against the gold set on the human-validated test split only. Secondary: abstention (zero-label) precision and recall, and macro set-F1. All three are declared in `params.yaml` before the first stage runs and do not change without a new release version.
18. The pipeline emits deterministic 25% / 50% / 100% subsamples of the training split, group-disjoint and recorded in the manifest, as the inputs to a learning curve. Running the training is out of scope.
19. Rung sizes and quotas:

| Rung | Records | Questions | Annotators | Jury | Proves |
|---|---:|---:|---|---|---|
| **S0 smoke** | 50 | ~70 | 1 | 3, stubbed then live | The plumbing, in one sitting. Verifies `maximum_annotations`, key-pool failover, cache determinism. |
| **S1 pilot** | 500 | ~700 | 2 at 100% overlap | 3, real | The instruments — and whether each triage bucket predicts what humans find. |
| **S2 scale** | ~3,500 annotated of 21,172 | ~4,500 | 3–5, mixed overlap | staged 3 → 7 | The release. |

20. This profile's `likely_label_error` bucket-precision floor is **0.30**: if fewer than three in ten flagged records are actually wrong, the jury is sending humans on a walk and the panel changes before 21,172 records depend on it. The other four pilot-gate thresholds are the core's.
21. The zero-label population is deliberately **oversampled** into the queue, because it carries the corpus's real difficulty. Strata are `likely_label_error`, `hard_record`, zero-label, the uniform random audit sample (default `n = 500`, from `p = 0.05, e = ±0.02 → 457`), and the entire test split.
22. Bucket thresholds start as guesses in `params.yaml` and get exactly one re-tuning pass from the pilot's measurement.

### Annotation surface

23. The correction control is a dynamic `<Choices value="$tool_choices" choice="multiple">` populated from that record's own catalog plus an explicit "no tool" option, so a correction is a set drawn from the catalog by construction.
24. Question generation follows [`guided-validation`](../../guided-validation/spec.md) unchanged in substance: focus chosen by marker rule, batch pre-generation, token budget as a hard ceiling, idempotence on `(rid, prompt_version, model)`. Only the rendering surface changes, from a bespoke React card to a generated Label Studio config.
25. `slot_filling` uses `{{double-brace}}` placeholders while the marker DSL uses `{single-brace}` tokens, so filling a template can never consume `{trigger}` or `{hold_missing}`. This non-collision is asserted by test, not assumed.

### Export

26. Export emits SFT JSONL in the source `messages` shape, with the curated label in both the assistant message and `meta.label`, asserted equal on the way out.
27. The datasheet states the machine-labelled share explicitly: 14,241 of 21,172 (67.3%) by `gemma-4-31B-it`, and 1,358 already relabelled once. Given the model-collapse result, a corpus that is two-thirds machine-labelled must be documented as such, and the human-validated test split is the mitigation that makes the release measurable at all.

## Design

### The answer schema is the catalog constraint

```python
schema = {"type": "array",
          "items": {"type": "string", "enum": [t.name for t in record.catalog]}}
value, info = await complete_structured(
    prompt, schema, mode="prompt",
    model=juror.model, api_key=key.api_key, base_url=juror.base_url, temperature=0,
)
```

The `enum` enforces requirement 5's catalog constraint inside the library. `info.ok is False` *is* the abstention: the profile stores `info.error`, `.raw`, `.repaired`, `.strategy`, and `.reasoning` and moves on. There is no bespoke parse-and-check step and no path where a malformed response becomes a truncated set.

### δ, in full

```python
def delta(a: set[str], b: set[str]) -> float:
    if not a and not b: return 0.0          # two abstentions agree perfectly
    return 1.0 - len(a & b) / len(a | b)
```

### The jury prompt

```
{{system_message}}
{{conversation}}

Trả về DUY NHẤT một JSON array gồm tên các tool cần gọi, theo đúng thứ tự gọi.
Nếu không cần gọi tool nào, trả về [].
Chỉ được dùng tên tool xuất hiện trong danh sách trên.
```

`{{system_message}}` carries the `TOOLS:` block and its markers verbatim.

### Redaction, in two layers

```
"số của em là không chín không một …"     ← regex hit, LLM: PHONE      → "<PHONE_1>"
"đơn hàng hai không hai bốn sáu tám"        ← regex hit, LLM: ORDER_REF → unchanged
```

### Cost, estimated

100,557,307 prompt characters. At 3 characters per token — an assumption, since Vietnamese diacritics tokenize unevenly — one pass is ~34M input tokens:

| Pass | Records | Input tokens |
|---|---:|---:|
| 3-juror sweep, whole corpus | 21,172 | ~101M |
| escalate to 7 jurors on ~15% | ~3,200 | ~+20M |
| **staged total** | | **~121M in, ~3M out** |

Against a flat 7-juror sweep at ~235M, staging saves about half, and the cache makes a re-run after a panel change cost only the new juror. The p99 prompt is ~17,000 characters (~5.7k tokens) from the 20-tool catalogs, so no context-window concern on any current model.

Every figure above is an estimate. `agent-toolkit`'s `Completion` carries no `usage`, and `count_tokens` drifts −33% to +64% on Vietnamese by the library's own measurement, so the budget in `params.yaml` carries headroom and the run labels its numbers "estimated".

### Why S2 does not annotate everything

21,172 questions at one minute each is 353 hours, ~44 person-days. The designed subset — 1,000 test + 500 audit + ~2,000 jury-flagged — is ~58 hours, ~7 person-days, and buys more: a fully validated test split, an unbiased residual-error estimate on everything untouched, and human attention where the jury says it is needed. Full manual validation ships the same corpus six weeks later with **no** error bar, because nothing was sampled to estimate one from.

## Decisions

**The task is never reformulated.** *Alternatives:* recast as per-(record, tool) binary "call or not", making 98,766 two-class examples and unlocking classifier tooling; recast as cardinality buckets. *Why:* the reformulation buys methods needing a fixed class space and pays by measuring something the model will never do — a per-tool decision in isolation, without the set-level interactions the marker DSL is largely about, since `{hold_other}` means *another tool covers this*, which is a statement about the set. *Reversible:* the binary view is reconstructible from jury votes as a diagnostic, so nothing is lost by not adopting it.

**An LLM jury, not Confident Learning.** *Alternatives:* Cleanlab over a proxy label space; a multi-label classifier; a single strong judge. *Why:* Cleanlab needs a fixed class space this corpus lacks, so adopting it requires reshaping the task. One judge is cheaper and rejected because a single model's agreement is indistinguishable from a single model's bias — and this corpus was already labelled by a single model. *Reversible:* yes; Cleanlab can be added later over whatever label space the first release establishes.

**`δ(∅,∅) = 0`.** *Alternatives:* exact-set-match only; per-tool micro-averaging; the empty set as a distinct class. *Why:* exact match discards the difference between "one tool too many" and "completely wrong", which is most of the useful gradient. The convention is load-bearing on 35.4% of the corpus. *Reversible:* no in practice — cohesion and conflict under a different convention are not comparable across releases.

**Jurors are called with `mode="prompt"`.** *Alternatives:* `"auto"` (the library default); `"grammar"` on vLLM endpoints. *Why:* the panel is a measuring instrument, and `"auto"` silently gives different jurors different constraint mechanisms depending on their endpoint — a juror whose tokens were constrained is not comparable to one whose were not. The library's own docstring records a case where a decode-time constraint made the answer worse. *Reversible:* one config field, but changing it invalidates cross-release cohesion comparisons, so it bumps `prompt_version`.

**No `gemma` juror in the primary panel.** *Alternatives:* include every available model; N samples from one model at temperature > 0. *Why:* 67.3% of the corpus is one family's output, and that juror would ratify exactly the errors this exercise exists to find. Temperature sampling from one model produces correlated jurors that agree on shared errors, so cohesion stops meaning confidence. Running `gemma` as a labelled control turns the liability into a measurement. *Reversible:* yes, panel config.

**Bucket thresholds are provisional until the pilot measures them.** *Why:* every threshold is currently a guess, and a guess deciding which 3,500 of 21,172 records humans see is worth one measurement. The bucket-precision gate is the only thing between "the jury found the errors" and "the jury found something". *Reversible:* yes, and expected to change exactly once.

**The key pool lives here, not in `agent-toolkit`.** *Alternatives:* add it to the library; express it as a `ConfigResolver`. *Why:* the library has one consumer for it, and growing a shared library for a single caller is how libraries acquire features nobody wants. The resolver route is not merely inelegant but unavailable: `set_config_resolver` installs one resolver process-wide keyed by model name, so per-call rotation cannot be expressed through it. *Reversible:* it graduates when a second consumer appears.

**Group split on catalog fingerprint ∪ dedup cluster.** *Alternatives:* random split; split on `source_index`. *Why:* `source_index` is unique per record and gives no protection — measured. Records sharing a catalog are near-variants of one scenario, largest such group 112 records, and a random split puts variants on both sides, inflating every metric. *Reversible:* yes, but every metric produced before the fix would be void.

**Assumption:** `potion-multilingual-128M` embeds Vietnamese well enough for near-duplicate detection. Checked by a retrieval sanity test on 200 hand-paired records, with a sentence-transformer fallback.

**Assumption:** 3 characters per token for Vietnamese, cross-checked against `count_tokens`. Neither is a measurement; see the cost section.

**Assumption:** enough API keys exist across ≥3 families recognised by `model_family` to run a 3-juror sweep of ~101M estimated input tokens in the release window. If keys concentrate in one family, the core's diversity requirement binds and the panel — not the requirement — changes.

**Assumption:** the residual-error estimate from the audit sample is reported as a property of the release and consumers read it. The alternative, refusing to ship anything unvalidated, is not on the table at 44 person-days.

**Assumption:** annotators are internal Vietnamese speakers on a self-hosted Label Studio inside the network boundary.

## Versions

| Component | Pinned | Source |
|---|---|---|
| Python | 3.12.14 | [endoflife.date, 2026-08-12](https://endoflife.date/python) — 3.12 for widest library compatibility |
| agent-toolkit | `agent-toolkit[llm] @ git+https://github.com/giangchicken/agent-toolkit.git@v0.1.0` | Not on any registry; direct-URL dependency pinned to the tag. Needs `git` on the installing machine. |
| model2vec | 0.9.0 | PyPI, 2026-08-12; model `potion-multilingual-128M` |

Everything else — Label Studio, SemHash, crowd-kit, krippendorff, pandera, DVC, mlcroissant — is pinned in the [core spec](../../annotation-pipeline/spec.md).

`agent-toolkit[llm]` brings `openai`, `tenacity`, `aiohttp`, `tiktoken`, and `jsonschema`; no module here imports them directly. `tiktoken` fetches its vocabulary over the network on first use, so CI sets `TIKTOKEN_CACHE_DIR` against a populated cache.

Dropped, and worth noting because it shrinks the dependency surface: **cleanlab** (needs a fixed class space this corpus lacks), **scikit-learn** (only there for cleanlab's cross-validated probabilities), **snorkel** 0.10.0 (last released 2024-02-27; the marker rules are ~200 lines of plain Python and do not justify pulling torch and tensorboard).

## Invariants

Beyond the core's seventeen:

1. **Marker tokens survive templating and parsing.** Any `{trigger}`, `{hold_other}`, `{hold_missing}`, `{constraint}`, or `{turn_trigger}` token in the source system message is present byte-identically in the adapter's output and in the rendered juror prompt. *Check:* a test rendering a template whose fill values contain marker tokens and asserting `slot_filling` altered none, alongside the adapter's verbatim-marker test.
2. **`δ(∅,∅) = 0` and δ is a metric.** *Check:* the core's conformance suite, plus a property test over random set pairs asserting symmetry, identity including the empty case, range, and no `NaN`.
3. **Every answer is a subset of that record's catalog.** *Check:* pandera on every artifact carrying a label — a second line behind the schema `enum`.
4. **Label and assistant agree on the way out.** For every exported record, `meta.label` equals the parsed assistant message. *Check:* export gate, running the same assertion that counted 48 of these before the source was fixed.
5. **The largest catalog group stays intact through splitting.** The 112-record group is wholly in one split. *Check:* the split gate's group assertion, with that group as a named fixture.

## Error Behavior

Beyond the core's table:

| Situation | Behavior |
|---|---|
| Adapter finds no `[ToolName]` block | `empty_catalog` quarantine. **Not** a verdict — 841 records is large enough that a parser miss and a genuinely toolless prompt must be told apart by hand before either is trusted. |
| A label names a tool outside the catalog | `label_not_in_catalog` quarantine. Never truncated to the catalog: that would be a guess about which of two disagreeing sources is right, applied at scale, invisibly. |
| `label_assistant_mismatch` count rises above 0 | Hard stop. Upstream drove this class to zero; a return means a curation step wrote one field and not the other. |
| Marker token altered by the adapter | Hard stop at the adapter's own test, before any run. |
| `likely_label_error` precision below 0.30 at the pilot gate | Hard stop. The panel or the thresholds change before the full corpus depends on them. |
| A record cannot be redacted with confidence | Quarantined to `quarantine/pii/uncertain.jsonl`, excluded from the release, counted in the datasheet. |

## Testing Strategy

Beyond the core's suite, and beyond the conformance suite this profile must pass:

- **Adapter.** All 13 observed `meta` key-sets, each answer cardinality, catalog sizes 0 / 1 / 8 / 20, malformed `TOOLS:` blocks. One test asserts marker tokens survive **verbatim**.
- **Validity gate.** A fixture with one record failing each check, asserting each lands in the right quarantine file with the right label and that the main path count drops by exactly the expected number.
- **δ and consensus.** Property tests for the metric axioms including the empty case. Consensus against hand-worked vote sets, including where consensus differs from every individual vote.
- **Set-valued α.** Against a hand-computed example, plus the degenerate check that α with an identity distance equals the `krippendorff` package's nominal α on the same data.
- **Templating.** A template whose fill values contain `{trigger}` and `{hold_missing}`, asserting `slot_filling` returned them untouched — invariant 1. A second asserts an uncovered `{{placeholder}}` is left in place rather than blanked.
- **Vietnamese privacy.** A hand-built fixture of spoken phone numbers, spoken emails, national IDs, prices, dates, and order references — asserting recall on the first three and *no* replacement on the last three. A tone-stripped variant asserts `normalize_text` matching catches `khong chin khong mot`. Placeholder stability via a record mentioning one number twice.
- **Jury answers.** A stubbed endpoint returning a clean array, a fenced array, prose-wrapped JSON, an out-of-catalog name, a non-array, and empty — each becoming a valid set or a clean abstention, with `repaired` true for exactly the fenced and prose-wrapped cases.
- **Dedup and grouping.** Known duplicate pairs from the corpus; `source_index` rejected as a group key; the 112-record catalog group intact through splitting.
- **Corpus profile.** `dataforce profile` reproduces every count in the Context section from the file named in `params.yaml`, and CI fails when a count drifts — which is how the 2026-08-17 change would have been noticed the day it happened.

## Out of Scope

- **Image, audio, and video** for this dataset. The corpus is text.
- **Full behavioural parity with `voice-agent-toolkit`** and the `agent-evaluation` migration. DataForce is greenfield and carries no parity obligation.
- **Confident Learning** over a proxy label space for this profile. Revisit after the first release establishes a label space and the jury's bucket precision is known.
- **Synthetic data generation.** The corpus is already two-thirds machine-labelled; generating more before the existing labels are validated is the model-collapse failure. Revisit after the first release measures residual error, and only for long-tail strata.
- **Automatic write-back to `fc_train_final.json`.** Export produces an artifact; putting it anywhere is a human step — and the source has already moved three times without one.
- **Multi-language.** Vietnamese only, for the corpus, the questions, and the privacy detectors.
- **Cross-border transfer review.** Sharper here than in the core, because the jury sends call-centre transcripts to several external LLM endpoints. It must happen before the first jury run against any offshore endpoint.

---

**Grounded in:** measurements over the full corpus, reproducible with `dataforce profile` · Vietnam Personal Data Protection Law 91/2025/QH15 and Decree 356/2025/ND-CP · [`guided-validation`](../../guided-validation/spec.md) for the question model · Shumailov et al., *Model collapse* (Nature 2024) · Northcutt et al., *Pervasive Label Errors* (NeurIPS 2021)
