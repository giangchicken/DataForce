# tool_decision store: two tables, one projection, and the figures that show what is missing

## What

A reviewed sample lands in **two** tables, written in one transaction.

- **`record`** keeps the whole of what the eight steps answered — what arrived, what ships, the
  spans, the outcome, every juror's vote. It holds personal data verbatim, so it is never exported
  and never sold. It is the evidence for trusting the other table.
- **`dataset`** keeps what a buyer gets: the input and the label as the review left them,
  de-identified, plus one `class` column saying what kind of sample it is. It is queryable, it is
  counted, and it is the thing that goes on a *sàn dữ liệu*.

`dataset` is a **projection of `record`**, never an independent edit, and it exists only for
records the redaction actually finished. That split is the whole design: the table that must be
protected and the table that is sold are different tables, rather than one table and a promise
about which columns anyone reads.

The `class` column is why this is worth more than a place to put rows. A corpus is scaled by
knowing which kinds of sample it is short of, and a label alone cannot say. `class` is what turns
the figures from *how much data do we have* into *which cells are empty*.

This answers `docs/tool-decision-pipeline/spec.md` § *Out of Scope*: the tables, the route that
takes a record, which records are refused, and the schema management under all of it.

## Context

What the repository already decided, and what this spec therefore does not:

- `pyproject.toml` carries `sqlalchemy>=2.0.52,<2.1` and `alembic>=1.19.1` for exactly this, both
  unimported today. SQLite and Postgres are one adapter with two DSNs, not two adapters.
- `alembic.ini` names `migrations/` and no `sqlalchemy.url`: the DSN is read once, from
  `DATAFORCE_DATABASE_URL`, and a credential-shaped line does not go in a public repository. The
  first schema is a migration and never a `create_all` side effect.
- A column is added when a query needs one. Nothing but the boundary declares the record's
  envelope, so `record.document` is one JSON column — no query reads inside it — and `dataset`
  holds the columns the queries do need.
- The store is an adapter in `edge/`. A service never imports it; it is handed to logic as an
  argument (`H-8`). Nothing in `modalities/` or `profile/` learns that a table exists.
- What a `class` value *means* is the task's, not the store's. `inbound`, `debt_collection` and
  `parallel` are `tool_decision`'s nouns, and a layer that serves many cases may not be written in
  one case's vocabulary (`H-10`). The store writes the column and counts over it without ever
  reading a value.

### The law this is written against

Not background. Three requirements exist only because of it, and the dates are close.

- **Nghị định 314/2026/NĐ-CP**, in force **25/9/2026**, governs data exchanges (*sàn dữ liệu*).
  Điều 17: traded data must have `nguồn gốc hợp pháp, có hồ sơ chứng minh việc thu thập, tạo lập
  hoặc nhận chuyển giao quyền khai thác, sử dụng`, must be machine-readable, and **the seller must
  publish** `chất lượng, độ chính xác, tính đầy đủ, mức độ cập nhật và những hạn chế`.
- The same decree: `dữ liệu, sản phẩm, dịch vụ về dữ liệu có nguồn gốc từ dữ liệu cá nhân chỉ được
  giao dịch trên sàn dữ liệu khi đáp ứng điều kiện về khử nhận dạng` — data derived from personal
  data is tradeable **only once de-identified**. Khoản 6, Điều 4 forbids using an exchange to buy
  or sell personal data at all.
- **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15**, in force **1/1/2026**, prohibits buying and selling
  personal data outright, with a fine of up to **10× the proceeds**, and gives a data subject the
  right to demand deletion.
- No licence is needed to *sell on* an exchange: a lawfully established Vietnamese legal entity (or
  a foreign one with commercial presence), a VNeID level-2 trading account, a registered payment
  account (Điều 18), and a certificate only where the data service is a conditional business line.
  *Operating* an exchange is the licensed activity and is restricted to public non-business units
  and state-owned enterprises (Luật Dữ liệu 60/2024/QH15). This is a spec for a seller.

The two tables are the legal shape, not only a tidy one. `record` holds `dữ liệu cá nhân` and is
the table a deletion request under 91/2025/QH15 acts on. `dataset` holds the `khử nhận dạng`
result and is the only table anything is ever exported from.

## Requirements

**`record` — what the review answered.**

1. One row per reviewed sample: `task`, `id`, `document`, `created_time`, `modified_time`. The
   primary key is `(task, id)`.
2. `document` is the record the page assembles, whole and unaltered —
   `{id, messages, tools, label, new_messages, new_tools, new_label, personal_data, duplicate,
   abnormal, llm, sft}` — in one JSON column. No query reads inside it (Requirement 20 is the one
   exception, and it reads three named keys, never a path expression), so no part of it becomes a
   column and the envelope stays declared where it is built.
3. A record is written whatever its outcome, the refused ones included. A sample whose redaction
   did not finish is a fact about the corpus worth keeping and worth counting; dropping it on the
   floor is how a pipeline comes to have no idea what it is failing at.
4. `created_time` is when the row was first written and never changes. `modified_time` changes on
   every write. Both UTC, both timezone-aware. A second post under one `(task, id)` replaces the
   row, because a record posted twice is one sample reviewed twice — and the review it used to hold
   is gone, which is the cost of replacing and is stated rather than designed around.

**`dataset` — what a buyer gets.**

5. One row per **sellable** sample: `task`, `id`, `input`, `label`, `class`, `created_time`,
   `modified_time`, keyed `(task, id)` — the same key, so a row here always has its evidence there.
6. `input` is the sample as it ships, `{messages, tools}` in one column. The turns and the catalog
   together, because a tool call is a call *against a catalog*, and a label stored apart from the
   catalog it was written for is a label nothing can check.
7. `label` is the calls as they ship.
8. Both are what the review left, never what arrived: `new_messages`, `new_tools` where the human
   or the redaction made a new version and what arrived where neither did, and `new_label`. The raw
   `messages`, `tools` and `label` exist only in `record.document`.
9. **`class`** is one JSON column holding the facets of Requirements 12–16. One column and not a
   column per facet: a facet is added by writing one, and a corpus that grows a new way of being
   described should not need a migration to say so.
10. `dataset` is a projection. Every column in it is computed from the `record` row of the same
    key, so it can be dropped and rebuilt from `record` at any time, and nothing writes to it
    except that computation. A `dataset` row that disagrees with its `record` is a bug with one
    possible cause.

**The door.**

11. **A `dataset` row is written only where the sample is de-identified.** The record's
    `personal_data.outcome` must be `redacted` — every claimed value resolved in the copy — or
    `reported` — nothing was claimed, so there was nothing to rewrite. `withheld` writes no
    `dataset` row, and neither does a record whose `personal_data` is `null`, which is a sample
    nobody scanned. The write of `record` still succeeds, and the response says which of the two
    tables took the row and why the other did not. `khử nhận dạng` is a condition, not an
    intention, and the table is what has to be able to prove it: every row in `dataset` passed this
    door, so an export is a `SELECT` and there is nothing to remember to filter.

**`class` — the facets, and which of them anything may derive.**

12. A facet is **derived** or **declared**, and the two are never mixed. A derived facet is
    computed from the record at write time and can be recomputed from it; nobody may type one, so
    it cannot disagree with the sample. A declared facet is a claim a person or the corpus made;
    nothing can check it, and it says who said so by existing in the other half.
13. **Derived, from the record alone:**
    - `personal_data` — the classes actually redacted, read off the confirmed spans'
      `personal_data_class`: `["EMAIL", "PHONE", "NAME"]`, `[]` where the sample had none. This is
      the patterns the scan redacts by, listed, and it is what tells a buyer what *kind* of
      personal data used to be in a corpus they are being told is clean.
    - `turns` — how many messages the shipped conversation holds.
    - `calls` — how many tool calls the shipped label makes. `0` is the no-call sample.
    - `tools_called` — the distinct tool names the label calls.
    - `tools_offered` — how many tools the catalog holds. One offered tool and five are not the
      same question asked of a model.
    - `call_shape` — the part of the trigger taxonomy a single sample can prove: `no_call`,
      `single`, `parallel` (two or more calls in one label). Whether the catalog forced a choice is
      `tools_offered > 1`, so it is read off that rather than stored twice.
    - `schema_valid` — whether every call names a tool in this row's own catalog and supplies that
      tool's required parameters.
14. **Declared, by the person at step 7 or by the corpus:**
    - `direction` — `inbound` (the customer called) or `outbound` (the bot called). Nothing in a
      transcript says which reliably, so it is ticked.
    - `domain` — the **bot's business function**, not the customer's industry: `debt_collection`
      (thu hồi nợ), `telesale`, `bill_reminder` (nhắc cước), `customer_care` (CSKH),
      `order_confirmation` (xác nhận đơn hàng), `appointment_reminder` (nhắc lịch hẹn),
      `survey` (khảo sát), `reactivation` (kích hoạt lại khách hàng không hoạt động),
      `technical_support` (hỗ trợ kỹ thuật), `kyc` (xác minh danh tính). The list is the profile's
      and grows there. An industry — banking, retail, insurance — is a different axis and is
      § *Open*.
    - `language` — `vi` or `en`. The flow already declares it per request and then throws it away;
      it belongs on the row, because a scan, a juror and a buyer all need to know.
    - `flow` — whether the sample is a step in a scripted conversation, and which one. See
      Requirement 15.
    - `trigger` — the call conditions a single flat sample cannot prove. See Requirement 16.
    - `ambiguous` — the reviewer says this sample is genuinely arguable. Two annotators differing
      on one of these is signal about the task, not a mistake by either, and a corpus that cannot
      mark them will keep re-litigating the same rows.
15. **A sample is not a conversation, and this is the gap that has to be closed.** "Has a
    conversation flow", "a tool that is called on every turn", and "which tool was called before
    this one" are properties of a *sequence* of samples. The corpus today is flat: one sample, its
    own turns, its own label, and no key joining it to the sample before it. So `class` carries
    `conversation_id` and `turn_index`, both declared, and with them those three facets become
    derivable later instead of being permanently unanswerable. Without them, the store can count
    what a corpus contains but never what a *dialogue* does, and the flow-shaped half of the
    taxonomy below stays a thing people assert.
16. **`trigger` — the taxonomy, and where each value comes from.** The vocabulary is the
    function-calling literature's, because a corpus described in the same words as the benchmarks
    it will be measured against is a corpus whose gaps are legible to a buyer.

    | value | what it is | derived? |
    |---|---|---|
    | `user_utterance` | the customer's turn is the whole trigger | yes — the default where nothing else holds |
    | `no_call` | no tool is appropriate; the right answer is to call nothing | yes — *irrelevance detection*, BFCL |
    | `choice` | several tools offered, one is right | yes — `tools_offered > 1` |
    | `parallel` | two or more calls for one turn | yes — `calls > 1` |
    | `sequential` | one call's result is an argument of the next | **no** — a flat label array cannot express it; nested sequences are where models collapse (NESTFUL: 28% full-sequence accuracy) |
    | `prior_call` | this turn's call depends on a tool called in an earlier turn | **no** — needs `conversation_id` (Requirement 15); BFCL's multi-turn, state-tracked |
    | `every_turn` | the flow obliges a tool on every turn | **no** — a property of the flow, not the sample |
    | `missing_parameter` | the right tool is clear, a required argument is not; the bot must ask | **no** — declared. Parameter-value errors dominate complex tool-calling failures (up to 78.8% on ComplexFuncBench), so a corpus with none of these teaches a bot to invent arguments |
    | `missing_function` | nothing offered can do what is asked | **no** — declared |

    The three *no*s in the middle are not an oversight to write around. They are the measurement
    that says this corpus is currently flat, and Requirement 15 is the one change that turns them
    on.

**The figures.**

17. `GET /text2text/tool-decision/records/stats` answers the figures, per task, reading and keeping
    nothing. Every figure is a count with the denominator it came out of — never a bare
    percentage, because a share over nine rows and a share over nine thousand are different claims.
18. **How much, how fresh, and how much of it is sellable.** `record` rows; `dataset` rows; the
    difference, split by why — `withheld`, never scanned. Rows created in the last 7 and 30 days;
    newest and oldest `modified_time`. Điều 17's `tính đầy đủ` and `mức độ cập nhật`, and the first
    number anyone building the corpus needs: reviewed is not the same as sellable.
19. **The coverage matrix, which is the point of `class`.** Counts per facet — `direction`,
    `domain`, `call_shape`, `trigger`, `language`, `turns` bucketed, `calls`, each
    `personal_data` class — and the cross of `domain` × `call_shape`. **The finding is the
    zeros.** A corpus with 4,000 `customer_care` rows and no `parallel` call in `debt_collection`
    is a corpus that will fail in production in a way its size hides completely, and the page's
    job is to show that cell, empty, next to the full ones.
20. **What the evidence buys**, and it is only measurable because `record` keeps it:
    - `human_edit_rate` — the share of records whose `new_label` differs from `label`. The humans
      are correcting the machine this often.
    - `panel_disagreement` — the mean `llm.label_agreement`, and the share of records with
      `consensus: null`. Where it is high, either the labels or the guideline are in trouble.
    - `redaction_outcomes` — `redacted` / `reported` / `withheld`.
21. **The same input twice**, under the names `DuplicateGroups` already uses:
    - `duplicate_content_same_label` — redundancy. Safe to drop one, and worth dropping:
      deduplicating training data measurably reduces memorisation and speeds convergence (Lee et
      al., ACL 2022).
    - `duplicate_content_diff_label` — **the same input carrying a different label.** One of them
      is wrong, or the task is ambiguous where the guideline claimed it was not. A queue to
      inspect, not an error count (VariErr NLI, arXiv:2403.01931) — which is also why
      Requirement 14's `ambiguous` exists.
22. **Schema validity** — the share of `dataset` rows whose `class.schema_valid` is true. BFCL's
    AST check turned on the corpus rather than on a model: a label calling a tool the sample was
    never offered is not a hard example, it is a broken row.
23. **Tool coverage** — distinct tools offered, distinct tools ever called, and the count per
    called tool. The tail is the finding: a corpus where two tools carry 90% of the calls trains a
    model that knows two tools.
24. **What is not shown, and is said so on the page.** **Inter-annotator agreement.**
    Krippendorff's α — ≥ 0.800 for a firm conclusion, ≥ 0.667 for a tentative one (Krippendorff,
    2004) — needs at least two people labelling one sample, and this flow puts one human in front
    of each record. The panel proxies in Requirement 20 are not it and must not be drawn as it. The
    page says *not measured*, and § *What else to add* says what would change that.
25. No figure is stored. Each is a query when it is asked, so a panel cannot be stale.

**The page.**

26. The figures are a band under the header of `ui/`, above step 1 — not a ninth rectangle. The
    eight rectangles are one sample's journey; this is the corpus.
27. Asked for on load and again after a record is written. Not on a timer.
28. Where no database is attached the band says so in the service's own words and all eight steps
    work exactly as they do today. The store is a place to put the result, never a dependency of
    the review.
29. Step 7 grows the ticks for the declared facets of Requirement 14, because that is where the
    human already is and a second form at the end would be a second place to describe one sample.
    **approve** posts the record, and step 8 says which tables took it — or, for a `withheld`
    record, that `record` has it and `dataset` does not, and why.

## Design

**Why two tables and not one with a filter.** A filter is a thing every future reader has to
remember. Selling a corpus is a `SELECT` someone writes in a hurry, possibly a year from now,
possibly not the person who wrote this. If the personal data is one `WHERE` away from the export,
one day it will be in the export. Two tables make the mistake impossible to make silently: the
export reads `dataset`, and `dataset` holds no raw transcript to find.

**Why `record` is one opaque column and `dataset` is many.** The record's envelope is declared at
the boundary that receives it, and mirroring it into columns would put that declaration in the
layer furthest from where it is built — so the review stays a document. Every query this store
answers is about the *corpus* and not about the *review*, and those get their own table with their
own columns. Requirement 20 is the seam: three named keys read out of `document` for three figures,
and the day a fourth is wanted, that is the argument for a fourth column in `dataset` rather than
for a path expression into `record`.

**Why `class` is derived where it can be.** Every facet a person types is a facet that can be
wrong, and a corpus's description going quietly stale is the failure mode that makes people stop
trusting the numbers. So `personal_data`, `turns`, `calls`, `call_shape` and `schema_valid` are
computed from the row every time it is written, and the declared half is small, ticked once, and
visibly a claim. Requirement 15 exists to move three more facets across that line.

**One adapter, two DSNs.** `Session.merge` for both writes, inside one transaction — a read by
primary key then an insert or an update, so no dialect-specific upsert is reached for and a
developer's SQLite file and a deployment's Postgres are one code path. The figures are Core
queries over `dataset`, except Requirement 20's three, which read `record.document` in Python over
the rows rather than in JSON path expressions — that is the part where the two dialects stop being
one adapter.

**Grouping by input.** Requirement 21 groups rows by *the same input*. Two JSON columns are not
comparable for equality across dialects and no index can be built on that comparison. The options
are a stored `sha256` of the input canonicalised under one key ordering — fast, indexable, one
more column — or a scan hashed in Python, which is correct and instant at the size this corpus
starts from. This takes the scan and names the digest as the change to make when it stops being
instant, because the figure is identical either way.

## What else to add

Proposals, not decisions:

- **`conversation_id` and `turn_index`** (Requirement 15). The single highest-value addition. Three
  of the facets you named are unanswerable without it, and no amount of extra samples fixes that —
  only this does.
- **`source`** — which corpus, batch or customer a sample came from. Điều 17 requires a
  `hồ sơ chứng minh việc thu thập, tạo lập`, and a per-row origin is what makes that dossier
  possible to assemble instead of being written from memory. It is also what lets you pull one
  customer's data back out if their contract ends.
- **`annotator`** — who reviewed the row. Cheap now, and the precondition for ever computing
  Requirement 24's agreement: the day two people review one sample, the store either knows who they
  were or the number cannot be computed retroactively.
- **`reviewed_at`** distinct from `created_time` — when the human answered, as against when the row
  landed. They differ when a backlog is posted, and any per-annotator quality figure needs the
  former.
- **A `consent` or lawful-basis marker** on `record`. 91/2025/QH15 gives the data subject rights
  over the personal data in that table; which basis each source was collected under is the thing
  nobody can reconstruct later.
- **`industry`** as a second axis beside `domain` — banking, retail, insurance, logistics,
  healthcare, education. `domain` is what the bot is *doing*; industry is who it is doing it for,
  and the same `debt_collection` flow differs between a bank and a telco.
- **A `difficulty` or `turns`-band facet** derived once rather than bucketed in every query, if the
  coverage matrix turns out to be read by band more often than by count.

## Invariants

- No row in `dataset` holds a value the redaction was asked to remove and did not. It is checked at
  the one door rows come through (Requirement 11).
- `dataset` is a function of `record`. Drop it, rebuild it, get the same table.
- Every `dataset` row has a `record` row under the same key. The reverse does not hold, and the
  difference is a figure (Requirement 18).
- No derived facet was ever typed by a person; no declared facet is ever computed.
- `created_time` never moves; `modified_time` never precedes it.
- Nothing below `edge/` knows a table exists, and the store never reads a `class` value it counts.

## Out of Scope

- The export itself — the manifest, the licence file, the format a buyer receives. Selling needs
  it; it is its own decision and it reads only `dataset`.
- Deleting a row, and what a deletion request under 91/2025/QH15 does to a corpus already sold. It
  is a real obligation and it is a process, not a column.
- Auth on the write route. Today's flow has none anywhere, and one guarded door in an unguarded
  building is theatre. It becomes urgent the moment `record` holds real transcripts.
- The provenance dossier itself. Per corpus, not per row, and a document rather than a table —
  though `source` above is what it would be assembled from.
- `DuplicateDataChecking.duplicate_groups`. Step 3 finally has a corpus to compare a sample
  against, and the shape it returns is still undeclared. Nothing here invents one.

## Open

- **Whether `(task, id)` is the key, or `id` alone.** Alone is simpler, and it assumes ids are
  unique across every corpus these tables hold — which nothing enforces and no corpus promised.
- **Who declares the `domain` list, and what happens to rows already written when it grows.** A
  closed list catches typos and needs an edit to extend; an open one never blocks a labeller and
  drifts into `cskh`, `CSKH` and `cham_soc_kh` being three domains. The list belongs in
  `profile/tool_decision/`, but closed-versus-open is a decision about how the labelling team
  works, not about the code.
- **`industry` as a second axis** — see above. It is a column or a facet or neither.
- **What a `null` label means.** `[]` and `null` both read as *no tool call is needed*, and
  `class.calls` counts both as `0`. The pipeline does not treat them as one answer: `label: null`
  canonicalises as the text `null` and never matches a panel that answered `[]`, so
  `label_agreement` reads 0.0 for a sample the panel agreed with — which would then feed
  Requirement 20's `panel_disagreement` as a disagreement that did not happen. Either the corpus
  writes one spelling or `normalize_prediction` folds them. A task rule, and one with a consumer on
  either side of it: the panel's agreement, and this store's figures.

## Sources

Law:

- [Nghị định 314/2026/NĐ-CP, toàn văn (Cổng TTĐT Chính phủ)](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-314-2026-nd-cp-quy-dinh-hoat-dong-cua-san-du-lieu-119260817104316631.htm)
- [Điều kiện tham gia giao dịch trên sàn dữ liệu (Xây dựng chính sách, Chính phủ)](https://xaydungchinhsach.chinhphu.vn/dieu-kien-tham-gia-giao-dich-tren-san-du-lieu-119260818085308618.htm)
- [Luật Bảo vệ dữ liệu cá nhân 2025, số 91/2025/QH15 (Thư viện pháp luật)](https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx)
- [Luật Bảo vệ dữ liệu cá nhân có hiệu lực từ 01/01/2026 (Bộ Công an)](https://bocongan.gov.vn/chinh-sach-phap-luat/bai-viet/luat-bao-ve-du-lieu-ca-nhan-chinh-thuc-co-hieu-luc-thi-hanh-tu-ngay-01-01-2026-1767186124)
- [Luật Dữ liệu 2024, số 60/2024/QH15 (Công báo, chinhphu.vn)](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/luat60.pdf)

The taxonomy of Requirement 16:

- Patil, S.G., Mao, H., Yan, F., Ji, C.C., Suresh, V., Stoica, I. & Gonzalez, J.E. (2025). *The
  Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large
  Language Models.* ICML 2025, PMLR 267:48371–48392. Single / multiple / parallel / parallel-multiple,
  live and non-live, multi-turn with state tracking, relevance and irrelevance detection, and the
  augmented categories — missing function, long context.
  [proceedings.mlr.press/v267/patil25a.html](https://proceedings.mlr.press/v267/patil25a.html) ·
  [leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)
- *NESTFUL: A Benchmark for Evaluating LLMs on Nested Sequences of API Calls.* arXiv:2409.03797
  (EMNLP 2025). Where `sequential` comes from, and why it is worth counting separately.
- *ComplexFuncBench: Exploring Multi-Step and Constrained Function Calling under Long-Context
  Scenario.* arXiv:2501.10132. Parameter-value errors as the dominant failure mode, which is the
  argument for `missing_parameter`.
- τ-bench, for the multi-turn simulated-user framing behind `every_turn` and flow policy.

Measurement:

- Northcutt, C.G., Athalye, A. & Mueller, J. (2021). *Pervasive Label Errors in Test Sets
  Destabilize Machine Learning Benchmarks.* NeurIPS 2021 D&B. arXiv:2103.14749 — ten widely used
  test sets average 3.3% label errors; the number to beat, and not to invent.
- Lee, K. et al. (2022). *Deduplicating Training Data Makes Language Models Better.* ACL 2022,
  8424–8445. arXiv:2107.06499
- Weber-Genzel, L. et al. *VariErr NLI: Separating Annotation Error from Human Label Variation.*
  arXiv:2403.01931
- Krippendorff, K. (2004). *Content Analysis: An Introduction to Its Methodology.* The α thresholds
  in Requirement 24 are his decision criterion.
- Gebru, T. et al. (2021). *Datasheets for Datasets.* Communications of the ACM 64(12), 86–92.
  DOI 10.1145/3458723 — what a published corpus states about itself, which Điều 17's disclosure
  list already resembles.

Vietnamese callbot business functions in Requirement 14 are drawn from what the local market
actually deploys — telesale, thu hồi nợ, nhắc cước và nhắc thanh toán, xác nhận đơn hàng, chăm sóc
khách hàng, khảo sát — rather than from a standard; there is no taxonomy to cite, and the list is
the profile's to keep.

The law is cited from the government portal and a legal publisher, not from the gazette text of the
decree; the article numbers should be checked against the official text before anything is sold
against them.
