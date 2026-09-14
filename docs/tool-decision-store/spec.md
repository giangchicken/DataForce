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
   abnormal, llm, sft}` — in one JSON column. No query reads inside it (*what the evidence buys* is the one
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
9. **`class`** is one JSON column holding the facets named under § *`class`*. One column and not a
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
    - `number_turns` — how many messages the shipped conversation holds.
    - `number_label_tools` — how many tool calls the shipped label makes. `0` is the no-call
      sample, and `2` or more is a turn answered by several calls at once.
    - `number_provided_tools` — how many tools the catalog offers. One offered tool and five are
      not the same question asked of a model: above one, the sample is also a choice.
    - `schema_valid` — whether every call names a tool in this row's own catalog and supplies that
      tool's required parameters.
14. **Declared, by the person at step 7 or by the corpus:**
    - `direction` — `inbound` (the customer called) or `outbound` (the bot called). Nothing in a
      transcript says which reliably, so it is ticked.
    - `domain` — the **bot's business function**, not the customer's industry: `debt_collection`
      (đòi nợ), `telesale`, `bill_reminder` (nhắc cước), `customer_care` (tổng đài chăm sóc khách
      hàng). The list is the profile's and grows there when a bot does a job that is not one of
      these. An industry — banking, retail, insurance — is a different axis and is § *Open*.
    - `language` — `vi` or `en`. The flow already declares it per request and then throws it away;
      it belongs on the row, because a scan, a juror and a buyer all need to know.
    - `have_conversation_flow` — true where the sample is a step in a scripted conversation, one
      the bot walks through in order and where reaching a given step is what obliges a call.
    - `call_shape` — **how the call is triggered**, which is the verb of the sample and the facet a
      buyer is really shopping for. One value per call, so a sample holds the set of them:
      - `condition_met` — the bot calls it the moment the arguments and preconditions are there,
        without being asked.
      - `user_utterance` — it fires only because the customer said a particular thing.
      - `every_turn` — the flow obliges it on every turn, whatever was said.
      The list is the profile's and grows there, on the same terms as `domain`. Where the label
      calls nothing, there is no trigger to describe and the facet is empty — the no-call sample is
      `number_label_tools: 0`, and that is where it is counted.
    - `ambiguous` — the reviewer says this sample is genuinely arguable. Two annotators differing
      on one of these is signal about the task, not a mistake by either, and a corpus that cannot
      mark them will keep re-litigating the same rows.
15. **`call_shape` is declared because a flat sample cannot prove it.** Whether a tool fired
    because its arguments were finally complete, because the customer said one particular thing, or
    because the flow obliges it every turn is a fact about *the bot's design*, and the evidence for
    it is not inside one sample. The record holds this sample's turns, its catalog and its label,
    and no key joining it to the sample before it — so nothing can tell a tool that happens to be
    called here from a tool that is called every time. It is ticked by the person who knows the
    flow, and `conversation_id` under § *What else to add* is what would let it be checked.

**The figures.**

16. `GET /text2text/tool-decision/records/stats` answers the figures, per task, reading and keeping
    nothing. Every figure is a count with the denominator it came out of — never a bare
    percentage, because a share over nine rows and a share over nine thousand are different claims.
17. **How much, how fresh, and how much of it is sellable.** `record` rows; `dataset` rows; the
    difference, split by why — `withheld`, never scanned. Rows created in the last 7 and 30 days;
    newest and oldest `modified_time`. Điều 17's `tính đầy đủ` and `mức độ cập nhật`, and the first
    number anyone building the corpus needs: reviewed is not the same as sellable.
18. **The coverage matrix, which is the point of `class`.** Counts per facet — `direction`,
    `domain`, `call_shape`, `language`, `have_conversation_flow`, `number_turns` bucketed,
    `number_label_tools`, each `personal_data` class — and the cross of `domain` × `call_shape`.
    **The finding is the zeros.** A corpus with 4,000 `customer_care` rows and no `every_turn` call
    anywhere in `debt_collection` is a corpus that will fail in production in a way its size hides
    completely, and the page's job is to show that cell, empty, next to the full ones.
    **The no-call share** falls out of the same count and is worth naming on its own: how many rows
    label nothing, out of the total. A corpus that is all tool calls cannot teach a bot to keep its
    hands in its pockets and cannot measure whether it does — *irrelevance detection* is a
    first-class BFCL metric, and a corpus with no such rows scores it at zero by construction.
19. **What the evidence buys**, and it is only measurable because `record` keeps it:
    - `human_edit_rate` — the share of records whose `new_label` differs from `label`. The humans
      are correcting the machine this often.
    - `panel_disagreement` — the mean `llm.label_agreement`, and the share of records with
      `consensus: null`. Where it is high, either the labels or the guideline are in trouble.
    - `redaction_outcomes` — `redacted` / `reported` / `withheld`.
20. **The same input twice**, under the names `DuplicateGroups` already uses:
    - `duplicate_content_same_label` — redundancy. Safe to drop one, and worth dropping:
      deduplicating training data measurably reduces memorisation and speeds convergence (Lee et
      al., ACL 2022).
    - `duplicate_content_diff_label` — **the same input carrying a different label.** One of them
      is wrong, or the task is ambiguous where the guideline claimed it was not. A queue to
      inspect, not an error count (VariErr NLI, arXiv:2403.01931) — which is also why
      the declared `ambiguous` facet exists.
21. **Schema validity** — the share of `dataset` rows whose `class.schema_valid` is true. BFCL's
    AST check turned on the corpus rather than on a model: a label calling a tool the sample was
    never offered is not a hard example, it is a broken row.
22. **Tool coverage**, read out of `input.tools` and `label` rather than off a facet — distinct
    tools offered, distinct tools ever called, and the count per called tool. The tail is the
    finding: a corpus where two tools carry 90% of the calls trains a
    model that knows two tools.
23. **What is not shown, and is said so on the page.** **Inter-annotator agreement.**
    Krippendorff's α — ≥ 0.800 for a firm conclusion, ≥ 0.667 for a tentative one (Krippendorff,
    2004) — needs at least two people labelling one sample, and this flow puts one human in front
    of each record. The panel proxies above are not it and must not be drawn as it. The
    page says *not measured*, and § *What else to add* says what would change that.
24. No figure is stored. Each is a query when it is asked, so a panel cannot be stale.

**The page — a deck, not a scroll.**

25. The labelling page shows **one card at a time**: the guide first, then the eight steps. One bar
    under the card holds all of the navigation — `<`, the rail, `>` — so moving is one place and
    not three. `←` and `→` move a card as well, but only while the focus is outside a field: inside
    a textarea an arrow key moves the caret, and a page that steals it is a page nobody can type
    in.
26. **The deck is not a wizard.** Every card is reachable from every other, in any order, whatever
    has answered so far. The steps are independent — the pipeline spec's *every step is reachable on
    its own* — and a deck that gated one card behind another would put a rule on the screen that
    the service does not have.
27. **The rail gives back what the scroll was giving away for free.** Eight markings in flow order,
    one per step, each carrying that step's state — answered, waiting, edited, refused, not asked —
    and each a jump to its card. A page as tall as eight rectangles shows all eight states for
    nothing; a deck has to hand that back deliberately, or it is the same page with flipping added.
    The rail is also where the fan is drawn: 2, 3 and 4 are grouped, because they are handed the
    same sample and none of them feeds another.
28. **A jump is not a *back to*, and both stay.** The rail moves the reviewer and means nothing
    else. **back to** says *the answer this card was built on is wrong*: it drops the record, marks
    the card it lands on with *make the correction here*, and re-opens **assemble** and
    **approve**. Two different acts, so two different controls — one moves, one changes what will
    ship.
29. **The first card is the labelling guide**, written for the person labelling. What a
    `tool_decision` sample is; what makes a label right, the empty label included — *no tool call
    is needed* is an answer and not a skipped row; what to tick at the two human steps and what
    each declared facet means; what gets a sample refused. No route name, no file path, no sentence
    about how the page is wired.
30. **The guide says what to do; the drawing says why the flow is shaped this way.** That split is
    already the pipeline spec's — `edge/static/index.html` explains the flow, `ui/` labels with it
    — and every card's own note obeys it too: the note in a card is what to do *here*. A sentence
    that would have to be rewritten because a route was renamed is a sentence on the wrong page.
31. **The figures sit on the guide card, under the guide.** A coverage matrix read in a report is a
    report; read on the card a labeller opens before they start, it is an instruction — *this is
    what the corpus is short of*. That is why they are not a ninth card and not a panel somebody
    has to go looking for.
32. **A strip stays on every card**: sellable out of reviewed, rows written in the last 7 days, and
    **how many cells of the coverage matrix are still empty**. Three items, because the strip is
    read sideways while the reviewer is working on something else. The third is the one that
    changes what they do next, and *which* cells those are is the guide card's to show.
33. The figures are asked for on load and again after a record is written. Not on a timer, and not
    on every flip.
34. Where no database is attached the strip says so in the service's own words, the guide card
    shows the guide and no figures, and all eight steps work exactly as they do today. The store is
    a place to put the result, never a dependency of the review.
35. Step 7 grows the ticks for the declared facets, because that is where the human already is and
    a second form at the end would be a second place to describe one sample. **approve** posts the
    record, and the last card says which tables took it — or, for a `withheld` record, that
    `record` has it and `dataset` does not, and why.

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
own columns. *What the evidence buys* is the seam: three named keys read out of `document`,
and the day a fourth is wanted, that is the argument for a fourth column in `dataset` rather than
for a path expression into `record`.

**Why `class` is derived where it can be.** Every facet a person types is a facet that can be
wrong, and a corpus's description going quietly stale is the failure mode that makes people stop
trusting the numbers. So `personal_data`, `number_turns`, `number_label_tools`,
`number_provided_tools` and `schema_valid` are computed from the row every time it is written, and
the declared half is small, ticked once, and visibly a claim.

**One adapter, two DSNs.** `Session.merge` for both writes, inside one transaction — a read by
primary key then an insert or an update, so no dialect-specific upsert is reached for and a
developer's SQLite file and a deployment's Postgres are one code path. The figures are Core
queries over `dataset`, except the three evidence figures, which read `record.document` in Python over
the rows rather than in JSON path expressions — that is the part where the two dialects stop being
one adapter.

**Grouping by input.** The duplicate figures group rows by *the same input*. Two JSON columns are not
comparable for equality across dialects and no index can be built on that comparison. The options
are a stored `sha256` of the input canonicalised under one key ordering — fast, indexable, one
more column — or a scan hashed in Python, which is correct and instant at the size this corpus
starts from. This takes the scan and names the digest as the change to make when it stops being
instant, because the figure is identical either way.

**Why a deck.** Eight rectangles stacked is a page as tall as all eight, and a labeller works in
one at a time — the other seven are scenery on the way back to the one they are in. A card is
the unit the work is actually done in. The cost is stated, and it is the whole of the risk: a long
page hands over every step's state for free and a deck does not. The rail is that cost paid back,
and the day a state cannot be read off the rail, the deck is the wrong shape for this page rather
than the rail being one badge short.

**The frame's height.** Step 2 is a table of spans and step 3 is one word. A frame that resizes on
every flip reads as broken, so it has a floor and no ceiling: it does not collapse under a short
card, and a tall card scrolls inside it rather than pushing the navigation off the bottom of the
screen. Wherever the reviewer is in the deck, the arrows are in the same place.

**Motion.** The flip is the only thing on this page that moves by itself, and it is answering a
keypress: one slide, in the direction of travel, and nothing else. None of it under
`prefers-reduced-motion`, where the card simply changes.

**Why the header is a title and the strip.** Architecture prose — one call per rectangle, what
`config/model/` holds, where the record goes — is true and is not for the person labelling, who
needs to know what a good label is. It belongs on the page whose job is explaining the flow. Above
the deck there is a title and three numbers; the reading a labeller has to do is on the first
card.

**Why the figures are on a card and not in a dashboard.** A dashboard is a thing somebody opens on
purpose, which means on the day they remember to. These figures exist to change what gets labelled
next, so they are put where the labelling starts. The same argument is why the strip carries a
count of empty cells rather than a total: a total is a number to feel good about, and an empty cell
is a job.

## What else to add

Proposals, not decisions:

- **`conversation_id` and `turn_index`.** The single highest-value addition. `call_shape` and
  `have_conversation_flow` are both assertions today, and with a key joining a sample to the one
  before it they become checkable: `every_turn` is then a thing the corpus can be asked about
  rather than a thing someone ticked. No amount of extra samples fixes that — only this does.
- **A facet for what the *right answer* is**, which `call_shape` does not cover: the right tool is
  clear but a required argument is missing and the bot must ask for it, or nothing offered can do
  what was asked. Parameter-value errors dominate complex tool-calling failures — up to 78.8% on
  ComplexFuncBench — so a corpus holding none of these teaches a bot to invent arguments rather
  than ask. Related, and equally unrepresentable in a flat label array: one call whose result is an
  argument of the next, which is where models collapse hardest (NESTFUL reports 28% full-sequence
  accuracy).
- **`source`** — which corpus, batch or customer a sample came from. Điều 17 requires a
  `hồ sơ chứng minh việc thu thập, tạo lập`, and a per-row origin is what makes that dossier
  possible to assemble instead of being written from memory. It is also what lets you pull one
  customer's data back out if their contract ends.
- **`annotator`** — who reviewed the row. Cheap now, and the precondition for ever computing
  the agreement figure: the day two people review one sample, the store either knows who they
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
- **A `difficulty` or turn-band facet** derived once rather than bucketed in every query, if the
  coverage matrix turns out to be read by band more often than by count.

## Invariants

- No row in `dataset` holds a value the redaction was asked to remove and did not. It is checked at
  the one door rows come through (§ *The door*).
- `dataset` is a function of `record`. Drop it, rebuild it, get the same table.
- Every `dataset` row has a `record` row under the same key. The reverse does not hold, and the
  difference is itself a figure.
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
  `panel_disagreement` as a disagreement that did not happen. Either the corpus
  writes one spelling or `normalize_prediction` folds them. A task rule, and one with a consumer on
  either side of it: the panel's agreement, and this store's figures.
- **Which language the guide card is written in.** The repository is written in English and the
  labellers work in Vietnamese. The guide is the first page here whose reader is not a developer,
  so nothing before it has had to decide this, and the eight cards' own notes go the same way the
  guide does.

## Sources

Law:

- [Nghị định 314/2026/NĐ-CP, toàn văn (Cổng TTĐT Chính phủ)](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-314-2026-nd-cp-quy-dinh-hoat-dong-cua-san-du-lieu-119260817104316631.htm)
- [Điều kiện tham gia giao dịch trên sàn dữ liệu (Xây dựng chính sách, Chính phủ)](https://xaydungchinhsach.chinhphu.vn/dieu-kien-tham-gia-giao-dich-tren-san-du-lieu-119260818085308618.htm)
- [Luật Bảo vệ dữ liệu cá nhân 2025, số 91/2025/QH15 (Thư viện pháp luật)](https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx)
- [Luật Bảo vệ dữ liệu cá nhân có hiệu lực từ 01/01/2026 (Bộ Công an)](https://bocongan.gov.vn/chinh-sach-phap-luat/bai-viet/luat-bao-ve-du-lieu-ca-nhan-chinh-thuc-co-hieu-luc-thi-hanh-tu-ngay-01-01-2026-1767186124)
- [Luật Dữ liệu 2024, số 60/2024/QH15 (Công báo, chinhphu.vn)](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/luat60.pdf)

Tool calling:

- Patil, S.G., Mao, H., Yan, F., Ji, C.C., Suresh, V., Stoica, I. & Gonzalez, J.E. (2025). *The
  Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large
  Language Models.* ICML 2025, PMLR 267:48371–48392. *Irrelevance detection* — the share of no-call
  cases a model correctly abstains on — and the AST check behind `schema_valid`.
  [proceedings.mlr.press/v267/patil25a.html](https://proceedings.mlr.press/v267/patil25a.html) ·
  [leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)
- *NESTFUL: A Benchmark for Evaluating LLMs on Nested Sequences of API Calls.* arXiv:2409.03797
  (EMNLP 2025). Where `sequential` comes from, and why it is worth counting separately.
- *ComplexFuncBench: Exploring Multi-Step and Constrained Function Calling under Long-Context
  Scenario.* arXiv:2501.10132. Parameter-value errors as the dominant failure mode, which is the
  argument for `missing_parameter`.
- τ-bench, for the multi-turn simulated-user framing behind `every_turn` and a flow's policy.

Dataset quality:

- Northcutt, C.G., Athalye, A. & Mueller, J. (2021). *Pervasive Label Errors in Test Sets
  Destabilize Machine Learning Benchmarks.* NeurIPS 2021 D&B. arXiv:2103.14749 — ten widely used
  test sets average 3.3% label errors; the number to beat, and not to invent.
- Lee, K. et al. (2022). *Deduplicating Training Data Makes Language Models Better.* ACL 2022,
  8424–8445. arXiv:2107.06499
- Weber-Genzel, L. et al. *VariErr NLI: Separating Annotation Error from Human Label Variation.*
  arXiv:2403.01931
- Krippendorff, K. (2004). *Content Analysis: An Introduction to Its Methodology.* The α thresholds
  under *what is not shown* are his decision criterion.
- Gebru, T. et al. (2021). *Datasheets for Datasets.* Communications of the ACM 64(12), 86–92.
  DOI 10.1145/3458723 — what a published corpus states about itself, which Điều 17's disclosure
  list already resembles.

The Vietnamese callbot business functions under `domain` are drawn from what the local market
actually deploys — telesale, thu hồi nợ, nhắc cước và nhắc thanh toán, xác nhận đơn hàng, chăm sóc
khách hàng, khảo sát — rather than from a standard; there is no taxonomy to cite, and the list is
the profile's to keep.

The law is cited from the government portal and a legal publisher, not from the gazette text of the
decree; the article numbers should be checked against the official text before anything is sold
against them.
