# DataForce — Objective, Input, Record, and Output

**What this document is for.** This is the document to rebuild from. It states why DataForce exists,
exactly what goes in, exactly what one record looks like at every point, and for each of the fifteen
services: what it reads, what it writes, and what fails the run. If the source is deleted, nothing here
should need to be guessed.

---

## 1 · Why this exists

**The problem.** A function-calling training set exists whose labels were largely written by a language
model. Fine-tuning on labels a model wrote teaches the next model that model's mistakes, and nothing in
the file says which labels are right. Re-annotating everything by hand is not affordable, and a random
sample gives the error *rate* without telling you *which* records to fix.

**The claim this is built on.** Independent models disagreeing about a record is a usable signal for
where humans should look. Have several models answer the dataset's own task, measure how much they
agree with each other and how much they agree with the existing label, and send humans to the records
where those two numbers say something is wrong. That turns an unaffordable job into a designed subset —
the test split, an unbiased audit sample, and the flagged strata — and everything else ships labelled
`unvalidated` with a measured error bar rather than silently.

**What it produces.** Train / validation / test in the shape a trainer expects, a test split that is
100% human-validated, no scenario on both sides of a split, no personal data downstream, per-record
provenance for every record and every label, and one datasheet stating how it was made.

**What it is not.** Not a labelling platform, not a training pipeline. The step between them, and its
output is a dataset plus the evidence for trusting it.

---

## 2 · The input

Standard OpenAI chat-completion records with the tool catalog carried **as data**.

```json
{
  "id": "s4471",
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
    { "role": "user",   "content": "Gửi giúp mình sao kê tháng này qua email." }
  ],
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
  "meta": {
    "label": [ { "name": "SendStatement",
                 "arguments": { "ma_khach": "480215", "ky": "thang_nay" } } ],
    "human_checked": true
  }
}
```

### `meta.label` is the answer

**The answer is the `label` key, and nothing else is.** It is the training target, every count is taken
from it, and it is what the jury is compared against and what an annotator is asked about.

**Which key holds it is declared, not assumed.** The profile's manifest names it (`label`), so a
source calling it `target` or `gold` needs a manifest line and no code.

### `messages` — context, in order

Multi-turn is the normal case: a tool is declined once, called after the customer supplies what was
missing, and called again on the result. **Every turn is context**, including earlier `tool_calls` and
`tool` result turns. Nothing in `messages` is an answer.

### `tools` — the catalog, as data

Standard function objects, so `parameters` is a JSON Schema and is what an argument is checked against.
Two consequences run through everything: the set of *permitted* answers is derivable from the record's
own catalog, so **no record stores an answer space** — a stored copy is a second thing that can
disagree with the first. And a wrong *argument* is a different error from a wrong *tool*, because the
schema says what the argument had to be.

### `meta` — everything else, verbatim

Kept whole, read only where the manifest declares a key's meaning. What looks like noise now is what a
later question turns out to need, so nothing is dropped for being unrecognised.


### Personal data

Vietnamese call-centre transcripts, where personal data appears in **spoken form** that no
off-the-shelf scrubber detects: digits as words (`không` … `chín`, plus `mốt`, `tư`, `lăm`), `@` as
`a còng`, `.` as `chấm`. Detection runs against the raw text *and* a tone-stripped normalisation, so
`khong chin` is not missed while patterns stay written in correct Vietnamese.

Law 91/2025/QH15 has been in force since 1 January 2026, with Decree 356/2025/ND-CP as implementing
guidance. **Redaction is a legal requirement.** Three rules, none negotiable:

- **Replaced with stable typed placeholders, never deleted.** Deleting a value turns a correct call into
  what looks like a correct *"required value was missing"*, inverting the label on exactly the records
  this exists to get right. Placeholders are scoped per record, so a value used twice stays co-referent.
- **Two layers with opposite jobs.** Patterns maximise recall and are *allowed* to be noisy — a digit run
  is also a price, a date, an order reference. A model pass over a bounded window sets precision.
- **The placeholder-to-original map never enters version control**, and no service may read it.

---

## 3 · The record — one bus, one key per phase

Every service reads and writes the same shape: **records in, records out.** A service adds one key and
changes nothing else.

```
record[<phase>][<service>] = { … }
```

```json
{
  "record_id": "",
  "source_id": "s4471",
  "branch": { "modality": "text2text", "profile": "tool_decision" },

  "content": [
    { "type": "text", "role": "system", "text": "Choose which tool(s) to call next, with arguments." },
    { "type": "text", "role": "user",   "text": "Cho mình xem số dư tài khoản." },
    { "type": "text", "role": "assistant", "text": "Bạn cho mình mã khách hàng nhé." },
    { "type": "text", "role": "user",   "text": "Mã của mình là <ID_1>." },
    { "type": "text", "role": "assistant",
      "text": "[{\"arguments\":{\"ma_khach\":\"<ID_1>\"},\"name\":\"LookupBalance\"}]" },
    { "type": "text", "role": "tool",   "text": "{\"so_du\": 1250000}" },
    { "type": "text", "role": "assistant", "text": "Số dư của bạn là 1.250.000 đồng…" },
    { "type": "text", "role": "user",   "text": "Gửi giúp mình sao kê tháng này qua email." }
  ],
  "content_version": 2,

  "label": [ { "name": "SendStatement",
               "arguments": { "ma_khach": "<ID_1>", "ky": "thang_nay" } } ],
  "meta": {"human_checked": true},

  "data_quality": {
    "data_quality_config":    { "use_exact_match": True, "use_similar_embedding": True, "embedding_config": {"embedding_model": "potion-multilingual-128M", "dim": 256}, "redacted_pii": True},
    "pii_check": {"spans": [ { "part": 3, "start": 16, "end": 22, "class": "CUSTOMER_ID",
                                  "verified": true, "placeholder": "<ID_1>" } ],
                     "classes": ["CUSTOMER_ID"], "unverified": 0 },
    "duplicate_check":       {"duplicate_content_diff_label": ["record_id_1", "record_id_2"], "duplicate_content_same_label": ["record_id_3", "record_id_4"]}
  },

  "ai_review": {
    "ai_review_config": {"judge_llm_models": [{"model_name": "", "max_tokens": 4096, "temperature": 0.1,...}, {...}], "finetuned_model": {}},
    "jury": {
      "panel_version": 2, "prompt_version": "jury_vote.v1",
      "llm_votes": [
        { "model_name": "glm5.2", "label_is_right": true,
          "answer": string answer,
          "reasoning": "khách yêu cầu sao kê tháng này" },
        { "model_name": "Qwen3.6-35B-A3B", "label_is_right": true,
          "answer": string answer,
          "reasoning": "…" },
        { ...}
      ],
      "llm_prediction": "",
      "plurality": [ { "name": "SendStatement",
                       "arguments": { "ma_khach": "<ID_1>", "ky": "thang_nay" } } ],
      "final_prediction": ""
                  
    },

  "human_review": {
    "human_config": {annotators: [{"annotator_id": "", "name": "",...}, {...}], "question_generator": {"model_name":...}},
    "question_generate": [{"question_id": "","question_name": "", "content": "", "enum": [(multiple choices)], ...}],
    "publish":   {},
    "annotator_answers": { "responses": [
                     { "annotator_id": "u_14", "question_id": "", "verdict": multiple_choices or null, "note": null,
                       "submitted_at": "…" },
                     { "annotator_id": "u_14", "question_id": "", multiple_choices or null, "note": null,
                       "submitted_at": "…" } ] },
    "aggregate": { "verdict": "",
                   "method": "majority_gold_weighted", "confidence": 0.94, "overlap": 2 },
    "curate":    { "status": "original",
                   "label": [ { "name": "SendStatement",
                                "arguments": { "ma_khach": "<ID_1>", "ky": "thang_nay" } } ],
                   "validators": ["u_14", "u_09"], "adjudicated_by": null, "decided_at": "…" }
  },

  "release": {}
}
```

---

## 7 · The services

Each reads records and writes records. **Reads** lists the keys it may look at; anything else is none of
its business. **Writes** is the one key it owns. **Gate** fails the run rather than passing bad data on.

### `data_quality` — everything checkable without an opinion

| Service |
|---|
| **`validity`** |
| **`pii_check`** | `content` | `data_quality.pii_replace = {decision, spans[], classes[], unverified}` — **and rewrites `content`, bumping `content_version`** | every high-recall hit verified or `decision == "withheld"`; zero literal personal data in `content` afterwards |
| **`duplicate_check`** |

### `ai_review` — the first opinion about the corpus

| Service |
|---|
| **`jury`** |

### `human_review` — where the project learns whether the questions are answerable

| Service |
|---|
| **`question_generate`** |
---

## 8 · Running it: in-process and as services

Every service has the same signature — **records in, records out** — so there is one implementation and
two ways to drive it:

- **In-process.** Chain the functions. This is what the tests exercise and what a developer runs.
- **As independent services.** Each reads a JSONL of records, adds its key, writes a JSONL of records.
  Same function, a different shell around it.

That is why both are affordable: a service is a second *shell*, never a second implementation of any
check. Nothing in a service's logic may name a file, a config location, or a data path — every path is a
parameter supplied at the edge — which is exactly what makes the same function work in both.

**Three rungs with exit gates. You do not climb without passing.** Sizes are each profile's; the shape
is not.

| Rung | Annotators | Jury | What it proves |
|---|---|---|---|
| **Smoke** | 1 | stubbed, then live | The plumbing, in one sitting |
| **Pilot** | 2 at 100% overlap | real | The **instruments** — is the question answerable, is the guideline right, do two people agree, does each bucket predict what humans find |
| **Scale** | several, mixed overlap | staged, expanding on conflict | The release |

**Scale annotates a designed subset, deliberately**: the full test split, the audit sample, the flagged
strata. The remainder ships as `unvalidated` **with a measured error bar** — an honest artifact, where
full manual validation ships the same corpus much later with no error bar at all, because nothing was
sampled to estimate one from. **Bucket thresholds are provisional until the pilot measures them** and get
exactly **one** re-tuning pass; a bucket whose precision the pilot cannot establish gets **no quota**.

**Two blocking prerequisites that are not code.** A cross-border data-transfer review before the first
jury call to any offshore endpoint — real, and sharper because the jury sends transcript content to
external providers. And a written glossary of any domain notation an annotator must read, before the
first question is generated: if two annotators read a marker differently, the agreement statistic
measures the glossary's ambiguity rather than the records' difficulty, and no threshold change fixes it.

---

## 9 · How a person interacts with it

**Batch.** The services, over a corpus, each gated.

**Annotation.** A self-hosted Label Studio whose config the pipeline *generates*, composed from the
modality's display half and the profile's capture half — neither may emit the other's. One generated
question at a time about one record, with the evidence and the glossary. The annotator answers correct /
incorrect / unsure, and answering incorrect **requires** the corrected value.

**Why the third surface exists separately.** No model output may reach an annotator, so the annotation
UI can *never* show a record's votes, cohesion, or bucket. Without a reader outside that UI, auditing one
decision means reading raw JSONL — and in practice nobody does.

**A web view is a later task, not a missing piece.** One router and one page over the same function, on
the house pattern already in use internally: a FastAPI app with a router per feature, and a Vite +
TypeScript SPA served from the same compose file.

---

## 10 · Decisions worth not re-deriving

**Buy the annotation UI, build the pipeline.** Users, task serving, locking and overlap are solved.
Building our own UI first inverts the order of risk — it spends a quarter before anyone has answered
whether the questions are answerable. Our own platform is **deferred, not cancelled**; the pilot decides.

**No record stores its answer space.** The profile settles the answer *type*; the record's catalog
settles the *space*. Both are present already, so a stored space is a copy — and it is the copy that goes
stale. Where a schema is needed it is materialised from the record at that moment and never persisted.

**One writer per key.** §3's ownership rule is what lets the record be a bus rather than a merge
conflict, and it is what makes a service independently re-runnable.

**No service touches the filesystem in its logic.** Every path is a parameter supplied at the edge, and
nothing is constructed at import time. This is what makes the in-process path, the service path, and the
single-record path one implementation instead of three.

**Every name contains its result.** A conversion is `Y_from_X` or is named for the result alone. `X_to_Y`
was tried and rejected on evidence: `tools_to_catalog` returned text while `catalog_to_tools` returned a
catalog object, so each name promised what the other gave and neither could be read at a call site. No
function shares a name with a service.

**Thresholds live in configuration, never in code**, so changing one is a committed, attributable
decision whose digest every run records.

**Two profiles is the only real proof the core is generic, and there is one.** Import guards prove no
service imports a concrete profile, but nothing catches a service *assuming* one profile's answer shape.
The next real dataset is that proof, and its first task is to notice this paragraph.

---

## 11 · What this is deliberately not

Model training and evaluation — this produces a dataset, a metric definition, and a zero-shot jury
baseline. Real image, audio or video modalities: the seam is specified and unenforced. Synthetic data
generation. Active learning. Fine-tuning a juror. Automatic write-back to any source file — export
produces an artifact, and putting it anywhere is a human step. Confident Learning, which needs a fixed
class space this task does not have. And a metadata format for public dataset catalogues, because the
release goes to named partners handed the datasheet directly.

---

**Grounded in:** Vietnam Personal Data Protection Law 91/2025/QH15 and Decree 356/2025/ND-CP · Label
Studio (task model, predictions, ML-backend contract) · CVAT (job stages, honeypots) · Gebru et al.,
*Datasheets for Datasets* (CACM 2021) · Bender & Friedman, *Data Statements* (TACL 2018) · Northcutt et
al., *Pervasive Label Errors* (NeurIPS 2021) · Sambasivan et al., *Data Cascades* (CHI 2021) ·
Shumailov et al., *Model collapse* (Nature 2024) · Zheng et al., *Judging LLM-as-a-Judge* (NeurIPS 2023)
· Krippendorff's α for incomplete overlap designs
