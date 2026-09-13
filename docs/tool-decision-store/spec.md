# tool_decision store: six columns, and the figures a corpus is judged by

## What

The flow is finished, so the thing it deferred can be decided. A reviewed record lands in one
table, one row per sample, and the row holds **what ships** — the input and the label as the
review left them — and not what arrived. Six columns: `id`, `task`, `created_time`,
`modified_time`, `input`, `label`.

Two halves come with it. **What the door refuses**, because a row that still holds a person's
phone number is a row that cannot be sold and a table that holds one is a liability rather than a
corpus. And **the figures**, because a corpus is bought and trained on by someone who has to
decide whether to trust it, and under Vietnamese law a seller has to publish them anyway
(Điều 17, Nghị định 314/2026/NĐ-CP — § *The law this is written against*).

This spec answers the whole of `docs/tool-decision-pipeline/spec.md` § *Out of Scope*'s first
paragraph: the table, the route that takes a record, which records are refused, and the schema
management under all of it.

## Context

What the repository already decided, and what this spec therefore does not:

- `pyproject.toml` carries `sqlalchemy>=2.0.52,<2.1` and `alembic>=1.19.1` for exactly this, both
  unimported today. SQLite and Postgres are one adapter with two DSNs, not two adapters.
- `alembic.ini` names `migrations/` and no `sqlalchemy.url`: the DSN is read once, from
  `DATAFORCE_DATABASE_URL`, and a credential-shaped line does not go in a public repository. The
  first schema is a migration and never a `create_all` side effect.
- `edge/store/` held `records.py` until `34ae87f` deleted it — *the store waits*. It kept one JSON
  `document` column under the record's id, and said why: "a column is added when a query needs
  one". A query now needs them. The figures below cannot be computed over an opaque document, and
  that is the whole of what changed.
- The store is an adapter in `edge/`. A service never imports it; it is handed to logic as an
  argument (`H-8`). Nothing in `modalities/` or `profile/` learns that a table exists.

### The law this is written against

Not background. Three of the requirements below exist only because of it, and a corpus built
without them is one that cannot be sold on the exchange the Vietnamese market is about to have.

- **Nghị định 314/2026/NĐ-CP**, in force **25/9/2026**, governs data exchanges (*sàn dữ liệu*).
  Điều 17: traded data must have `nguồn gốc hợp pháp, có hồ sơ chứng minh việc thu thập, tạo lập
  hoặc nhận chuyển giao quyền khai thác, sử dụng`, must be machine-readable, and **the seller must
  publish** `chất lượng, độ chính xác, tính đầy đủ, mức độ cập nhật và những hạn chế`.
- The same decree: `dữ liệu, sản phẩm, dịch vụ về dữ liệu có nguồn gốc từ dữ liệu cá nhân chỉ được
  giao dịch trên sàn dữ liệu khi đáp ứng điều kiện về khử nhận dạng` — data derived from personal
  data is tradeable **only once de-identified**. Khoản 6, Điều 4 forbids using an exchange to buy
  or sell personal data at all.
- **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15**, in force **1/1/2026**, prohibits the buying and
  selling of personal data outright, with an administrative fine of up to **10× the proceeds**.
- No licence is needed to *sell on* an exchange. What is needed is a lawfully established
  Vietnamese legal entity (or a foreign one with commercial presence), a VNeID level-2 trading
  account and a registered payment account (Điều 18), and a certificate only where the data
  service falls in a conditional business line. *Operating* an exchange is the licensed activity,
  and is restricted to public non-business units and state-owned enterprises (Luật Dữ liệu
  60/2024/QH15) — so this is a spec for a seller, never for an exchange.

A corpus of customer-support conversations is `dữ liệu có nguồn gốc từ dữ liệu cá nhân`. This
pipeline's redaction is what satisfies `khử nhận dạng`, and Requirements 9–12 are what make the
table able to prove it.

## Requirements

**The row.**

1. One table, `record`. One row is one reviewed sample. Six columns and no seventh: `id`, `task`,
   `created_time`, `modified_time`, `input`, `label`.
2. `id` is the sample's own — what the corpus called it and what the record at step 8 keeps.
   `task` is the task that produced the row, `tool_decision` for every row this flow writes. One
   table serves every task: the row's shape does not vary by task, and a table per task would be a
   second declaration of which tasks exist.
3. The primary key is `(task, id)`. A sample id is unique inside the corpus it came from and
   nothing makes two corpora agree; `task` is a column precisely so that one table holds more than
   one of them.
4. `input` is the sample as it ships: `{messages, tools}`. The turns and the catalog together, in
   one column, because a tool call is a call *against a catalog* — a label stored apart from the
   catalog it was written for is a label nothing can check.
5. `label` is the calls as they ship.
6. Both are what the review left and never what arrived: `new_messages` and `new_tools` where the
   human or the redaction made a new version, what arrived where neither did, and `new_label` for
   the label. `messages`, `tools` and `label` as they arrived are not columns and are not written.
   That is not tidiness — it is Requirement 9.
7. `created_time` is when the row was first written and never changes. `modified_time` is when it
   was last written and changes on every write. Both UTC, both timezone-aware.
8. A second post under one `(task, id)` replaces the row and keeps its `created_time`: a record
   posted twice is one sample reviewed twice. The cost, stated: the review the row used to hold is
   gone, with no trace that it existed.

**What the door refuses.**

9. **A row is written only where the sample is de-identified.** The record's `personal_data`
   carries the replacement outcome, and two of the three are admissible: `redacted` — every value
   the detectors claimed resolved in the copy — and `reported` — nothing was claimed, so there was
   nothing to rewrite. `withheld` is refused: it means a rewrite was asked for and not finished,
   and `khử nhận dạng` is a condition, not an intention.
10. A record whose `personal_data` is `null` is refused. Nothing scanned it, so nothing says it is
    clean; a record nobody looked at is not the same as a record with nothing to find, and the
    difference is the one the exchange asks about.
11. A refusal is `422` naming the outcome it saw, on the same terms as every other refusal on this
    router: a declaration the service cannot act on, told to the caller in the service's own words.
12. What Requirements 9–11 buy is why there are six columns and not seven. **The admission rule is
    the evidence.** Every row in the table passed it, so the guarantee is a property of the table
    rather than a field inside a row that whoever wrote the row could have set. A corpus is
    exported by selecting from it; there is nothing to filter on and nothing to trust.

**The figures.**

13. `GET /text2text/tool-decision/records/stats` answers the figures over the table, per task. It
    reads and keeps nothing. Every figure is a count with the denominator it is a count out of —
    never a bare percentage, because a share over nine rows and a share over nine thousand are not
    the same claim.
14. **How much, and how fresh.** Rows in total; rows whose `created_time` falls in the last 7 and
    30 days; the oldest and newest `modified_time`. This is Điều 17's `tính đầy đủ` and
    `mức độ cập nhật`, and a corpus whose newest row is eleven months old is a fact a buyer is
    entitled to before the sale rather than after it.
15. **The same input twice**, split the two ways the codebase already names them
    (`DuplicateGroups`):
    - `duplicate_content_same_label` — the same input carrying the same label. Redundancy. Safe to
      drop one, and worth dropping: deduplicating training data measurably reduces memorisation
      and speeds convergence (Lee et al., ACL 2022).
    - `duplicate_content_diff_label` — **the same input carrying a different label**. The figure
      the labelling lead actually needs: one of the two is wrong, or the task is ambiguous where
      the guideline claimed it was not. It is a queue to inspect and not an error count — for a
      genuinely debatable input, two annotators differing is signal about the task rather than a
      mistake by either (Weber-Genzel et al., *VariErr NLI*, arXiv:2403.01931).
16. **The no-call share.** How many rows carry a label that calls nothing — `[]`, and `null` where
    the corpus spells it that way — out of the total. A tool-decision corpus with no such rows
    cannot teach a model to keep its hands in its pockets, and cannot measure whether it does:
    *irrelevance detection*, the share of no-call cases where a model correctly abstains, is a
    first-class metric on the Berkeley Function Calling Leaderboard (Patil et al., ICML 2025). A
    corpus that is 100% tool calls scores that metric at zero by construction.
17. **Schema validity.** The share of rows whose every call names a tool that is in that row's own
    catalog, and supplies that tool's required parameters. This is the leaderboard's AST check
    (*ibid.*) turned on the corpus rather than on a model: a label that calls a tool the sample was
    never offered is not a hard example, it is a broken row.
18. **Tool coverage.** How many distinct tools the catalogs offer, how many are ever called, and
    the count per called tool. The tail is the finding — a corpus where two tools carry 90% of the
    calls trains a model that knows two tools.
19. **What is not shown, and is said so on the page.** Two figures a buyer will ask for and these
    six columns cannot answer:
    - **Label error rate.** It needs a second opinion per row, and the row keeps none. The
      published yardstick is that ten widely used test sets average **3.3%** label errors, ImageNet
      validation about 6% (Northcutt et al., NeurIPS 2021 D&B) — worth knowing as the number to
      beat, and worth not inventing.
    - **Inter-annotator agreement.** Krippendorff's α is the metric for it — α ≥ 0.800 for a firm
      conclusion, ≥ 0.667 for a tentative one (Krippendorff, 2004) — and it needs at least two
      people labelling the same sample. This flow puts one human in front of each record. Until
      two see one record, this panel shows *not measured*, never a number.
    The page names both as gaps rather than leaving a blank a reader fills in optimistically.
20. No figure is stored. Each is a query at the time it is asked, so a panel cannot be stale and
    there is nothing to keep in step with the table.

**The page.**

21. The figures are a band under the header of `ui/`, above step 1 — not a ninth rectangle. The
    eight rectangles are one sample's journey; this is the corpus, and a step that is not part of
    the flow must not be drawn as one.
22. It is asked for on load, and again after a record is written. Not on a timer.
23. Where the service answers no figures — no database attached, nothing migrated — the band says
    so in the service's own words and the eight steps work exactly as they do today. The store is
    an adapter, and a flow that cannot label without one would have made it a dependency of the
    review rather than a place to put the result.
24. **approve** is where the record is posted, and step 8 is the only rectangle that changes
    (pipeline spec, Requirement 53). It says which id it wrote, or shows the refusal.

## Design

**Why the columns and not the document.** The deleted `records.py` kept the record as one JSON
blob under its id, for a stated reason: nothing but the boundary declares the envelope, and a
relational schema for it would put that declaration in the layer furthest from where the record is
built. That reason still holds for everything the record carries *about the review* — the votes,
the agreement, the spans, the outcome. It stops holding for the two things the corpus **is**.
`duplicate_content_diff_label` is a group-by on the input; the no-call share is a predicate on the
label; schema validity reads the catalog against the calls. None of those is expressible over an
opaque column in both SQLite and Postgres. So exactly two parts of the record become columns, and
the rest becomes the admission rule at the door.

**Where the evidence goes.** Nowhere, and that is the decision. The record's `llm`, `sft` and
`personal_data` halves are read by the route and not written down: `personal_data` decides whether
the row is admitted at all, and the reviewers' verdicts were the human's aid in deciding the label
that is now in the `label` column. Stated plainly because it is a real loss: **after this store,
you cannot ask a row what the panel thought of it.** Requirement 12 is what is bought with it, and
§ *Open* carries the alternative.

**One adapter, two DSNs.** `Session.merge` for the write — a read by primary key then an insert or
an update — so no dialect-specific upsert is reached for and a developer's SQLite file and a
deployment's Postgres are one code path. The figures are SQLAlchemy Core queries over the same
table; the two that read inside `input` and `label` (Requirements 17 and 18) are computed in
Python over the rows rather than in JSON path expressions, because that is the part where the two
dialects stop being one adapter.

**The digest, and why it is not a seventh column yet.** Requirement 15 groups rows by *the same
input*. Two JSON columns are not comparable for equality across dialects, and no index can be
built on that comparison. The honest options are a stored `sha256` of the input canonicalised
under one key ordering — fast, indexable, and a seventh column — or a full scan hashed in Python,
which is correct and is fine at the size this corpus is starting from. This spec takes the second
and names the first as the change to make when the scan stops being instant, because the figure is
the same figure either way and a column added before a query needs it is the mistake the deleted
store already documented.

## Invariants

- No row holds a value the redaction was asked to remove and did not. Requirement 9 is checked at
  the one door rows come through.
- `created_time` never moves. `modified_time` never precedes it.
- The table is the corpus. Anything true of the corpus is a query over it, and nothing is a figure
  someone wrote down.
- Nothing below `edge/` knows the table exists.

## Out of Scope

- Reading rows back out. This spec writes them and counts them. An export — which is what selling
  one actually needs, with its manifest and its licence file — is its own decision.
- Deleting a row, and what a data subject's deletion request does to a corpus already sold. It is a
  real obligation under 91/2025/QH15 and it is not a column; it is a process.
- Auth on the write route. Today's flow has none anywhere, and adding it at one route would be the
  only guarded door in an unguarded building.
- The provenance dossier itself (`hồ sơ chứng minh việc thu thập, tạo lập`). It is per corpus, not
  per row, and it is a document rather than a table.
- `DuplicateDataChecking.duplicate_groups`. Step 3 finally has a corpus to compare a sample
  against, and the shape it should return is still undeclared. Nothing here invents one.

## Open

- **Whether the evidence is kept.** Six columns lose the reviewers' verdicts and the span record.
  The alternative is a seventh JSON column holding the rest of the record — which brings back
  exactly what the deleted store held, next to the two columns that replaced it, and makes the
  row able to answer *why should I believe this label* per row rather than per table. It is not
  written here because the schema asked for is six columns, and the loss is stated above rather
  than designed around.
- **Whether `(task, id)` is the key, or `id` alone.** Alone is simpler and is what the deleted
  store did. It assumes ids are unique across every corpus this table ever holds, which nothing
  enforces and no corpus promised.
- **What a `null` label means.** `[]` and `null` both read as *no tool call is needed* in the
  corpus, and Requirement 16 counts both. The pipeline does not treat them as one answer:
  `label: null` canonicalises as the text `null` and never matches a panel that answered `[]`, so
  `label_agreement` reads 0.0 for a sample the panel agreed with. Either the corpus writes one
  spelling, or `normalize_prediction` folds them — a task rule, and undecided here.

## Sources

Law:

- [Nghị định 314/2026/NĐ-CP, toàn văn (Cổng TTĐT Chính phủ)](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-314-2026-nd-cp-quy-dinh-hoat-dong-cua-san-du-lieu-119260817104316631.htm)
- [Điều kiện tham gia giao dịch trên sàn dữ liệu (Xây dựng chính sách, Chính phủ)](https://xaydungchinhsach.chinhphu.vn/dieu-kien-tham-gia-giao-dich-tren-san-du-lieu-119260818085308618.htm)
- [Nghị định 314/2026/NĐ-CP về hoạt động của sàn dữ liệu từ 25/9/2026 (LuatVietnam)](https://luatvietnam.vn/tin-van-ban-moi/da-co-nghi-dinh-314-2026-nd-cp-ve-hoat-dong-cua-san-du-lieu-tu-ngay-25-9-2026-186-111449-article.html)
- [Luật Bảo vệ dữ liệu cá nhân 2025, số 91/2025/QH15 (Thư viện pháp luật)](https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx)
- [Luật Bảo vệ dữ liệu cá nhân có hiệu lực từ 01/01/2026 (Bộ Công an)](https://bocongan.gov.vn/chinh-sach-phap-luat/bai-viet/luat-bao-ve-du-lieu-ca-nhan-chinh-thuc-co-hieu-luc-thi-hanh-tu-ngay-01-01-2026-1767186124)
- [Luật Dữ liệu 2024, số 60/2024/QH15 (Công báo, chinhphu.vn)](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/luat60.pdf)

Measurement:

- Patil, S.G., Mao, H., Yan, F., Ji, C.C., Suresh, V., Stoica, I. & Gonzalez, J.E. (2025). *The
  Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large
  Language Models.* ICML 2025, PMLR 267:48371–48392.
  [proceedings.mlr.press/v267/patil25a.html](https://proceedings.mlr.press/v267/patil25a.html) ·
  [leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)
- Northcutt, C.G., Athalye, A. & Mueller, J. (2021). *Pervasive Label Errors in Test Sets
  Destabilize Machine Learning Benchmarks.* NeurIPS 2021 Datasets & Benchmarks. arXiv:2103.14749 ·
  [labelerrors.com](https://labelerrors.com)
- Lee, K. et al. (2022). *Deduplicating Training Data Makes Language Models Better.* ACL 2022,
  8424–8445. arXiv:2107.06499
- Weber-Genzel, L. et al. *VariErr NLI: Separating Annotation Error from Human Label Variation.*
  arXiv:2403.01931
- Krippendorff, K. (2004). *Content Analysis: An Introduction to Its Methodology.* The α thresholds
  used in Requirement 19 — ≥ 0.800 satisfactory, ≥ 0.667 tentative — are his decision criterion.
- Gebru, T. et al. (2021). *Datasheets for Datasets.* Communications of the ACM 64(12), 86–92.
  DOI 10.1145/3458723 — what a published corpus states about itself, and the shape Điều 17's
  disclosure list already resembles.

The law is cited from the government portal and a legal publisher, not from the gazette PDF of the
decree itself; the article numbers above should be checked against the official text before
anything is sold against them.
