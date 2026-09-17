# Two tables a task, and the statistics that show what is missing

## What

A reviewed sample lands in **two** tables, written in one transaction.

- **`tool_decision_record`** keeps the whole of what the eight steps answered — what arrived, what
  ships, the spans, the outcome, every juror's vote. It holds personal data verbatim, so it is never
  exported and never sold. It is the evidence for trusting the other table.
- **`tool_decision_dataset`** keeps what a buyer gets: the input and the label as the review left
  them, de-identified, plus the facets saying what kind of sample it is. It is queryable, it is
  counted, and it is the thing that goes on a *sàn dữ liệu*.

The two hold **the same rows** and differ by **what is in them**. `dataset` is computed from
`record` and nothing else writes to it, so it can be dropped and rebuilt at any time. That split is
the whole design: the table that must be protected and the table that is sold are different tables,
rather than one table and a promise about which columns anyone reads.

**The tables are the task's; the condition over them is the modality's.** A sample arrives here
having passed all eight steps, so nothing in this store decides whether it is worth keeping. What
`tool_decision` stores, in which columns, is declared in `profile/tool_decision/schema.py` — its
own two tables, and the SQL over them. What every text2text sample has in common, whatever the
task, is declared once in `modalities/text2text/dataset_management/`.

The facets are why this is worth more than a place to put rows. A corpus is scaled by knowing which
kinds of sample it is short of, and a label alone cannot say. The facets are what turn the
statistics from *how much data do we have* into *which cells are empty*.

This answers `docs/tool-decision-pipeline/spec.md` § *Out of Scope*: the tables, the route that
takes a record, and what is refused before one is written.

## Context

What the repository already decided, and what this spec therefore does not:

- `pyproject.toml` carries `sqlalchemy>=2.0.52,<2.1` for exactly this, unimported today. SQLite and
  Postgres are one code path with two DSNs, not two adapters.
- The DSN is read once, from `DATAFORCE_DATABASE_URL`. There is no default and no fallback file: a
  DSN that is unset or empty means *no store*, which every caller handles.
- **There are no migrations.** `Base.metadata.create_all` is the only thing that makes a table, so
  it only ever *creates*. Changing a column on a database that already holds rows is a statement
  somebody writes by hand, which is the reason a new facet goes in `notes` rather than in a column.
- A column is added when a query groups by one. The record's envelope is declared at the boundary
  that receives it, so `record.document` is one JSON column that no query reads inside.
- Which tables exist is the profile's, and `sqlalchemy` is named in two places only:
  `edge/database.py` for the DSN, the engine, the session and the one declarative base, and each
  profile's own `schema.py` for its tables. Nothing under `modalities/` or `services/` imports it.
- What a facet value *means* is the task's. `inbound`, `debt_collection` and `condition_met` are
  `tool_decision`'s nouns and are declared in `profile/tool_decision/`, which is what the split
  between the two layers is for. Nothing checks it: the check that used to is gone, so a name in
  `modalities/` written in one task's vocabulary is now a review finding and not a failing test.

### The law this is written against

Not background. Two requirements exist only because of it, and the dates are close.

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

**Where each piece is declared.**

1. **`modalities/text2text/dataset_management/` declares what every text2text task has in common**:
   the shape of a stored sample, how a finished review becomes one, what any label can be measured
   by, and how the same input appearing twice is grouped. No name in it is one task's: a label
   there is a sequence that may be absent and nothing more, so what a corpus *offered* and what it
   *called* are answered a layer down, where those words mean something. Nothing checks this any
   more — it is a review finding, not a failing test.
2. **`profile/tool_decision/` declares this task's two tables** in its own `schema.py`, and
   answers what the modality leaves open:
   - what `input` holds. For `tool_decision` that is `{messages, tools}`: a tool call is a call
     *against a catalog*, and a label stored apart from the catalog it was written for is a label
     nothing can check.
   - the facets computed from a document that only this task can read.
   - which facets a sample carries, as `FACETS` on the table whose columns they are. **Which
     values a person may tick is not declared here and nowhere below the edge**: that list belongs
     with the page that draws the tick boxes.
   - what this task's label can be measured by, which is every measurement that says `tool`.
3. **`services/tool_decision/dataset_management.py` is one function per endpoint.** Its matrix is a
   **joint distribution of two variables named by the caller**, so a second cross, over any two
   facets, is another call rather than another function. Which pair *this* answer crosses is
   declared in the router beside the field that reports it: it is wanted once, at the call, and a
   socket for it buys a wider interface for nothing. It never holds a session — the profile's
   `schema.py` is an `adapter` and `H-8` sends that import the other way.
4. **`edge/database.py` is the plumbing and declares no table**: the DSN, the engine, the session,
   and the one declarative base every task's tables hang off, so one `MetaData` knows them all.
5. **The response shapes live in the router.** The totals, the per-facet counts, the joint
   distribution matrix and the duplicate groups are the shape of one HTTP answer, and nothing below
   the edge has a use for them.

**`record` — what the review answered.**

6. One row per reviewed sample: `id`, `document`, `created_time`, `modified_time`. The key is `id`
   alone and it is a **UUID** — the table name is the task, so nothing has to be qualified by one.
7. `document` is the record the page assembles, whole and unaltered —
   `{id, messages, tools, label, new_messages, new_tools, new_label, personal_data, duplicate,
   abnormal, llm, sft, class}` — in one JSON column. The `class` key carries the **declared facets
   only**, because those are part of what the review answered and there is nowhere else for them to
   arrive; the computed ones are derived at write time and are never posted. No query reads inside
   `document`, so no part of it becomes a column and the envelope stays declared where it is built.
8. `created_time` is when the row was first written and never changes. `modified_time` changes on
   every write. Both are this deployment's own clock, written and read without conversion, so a row's
   instant is only placeable by someone who knows where it runs — the trade taken instead of a
   timezone-aware column, and the one to revisit when a second region reads the same corpus. A
   second post under one `id` replaces the row,
   because a record posted twice is one sample reviewed twice — and the review it used to hold is
   gone, which is the cost of replacing and is stated rather than designed around.

**`dataset` — what a buyer gets.**

9. One row per stored sample, under the same `id`, so a row here always has its evidence there.
10. `input` is one column, holding what the profile says a sample of this task ships as. For
    `tool_decision` it is `{messages, tools}` — the turns and the catalog together.
11. `label` is the calls as they ship.
12. Both are what the review left, never what arrived: `new_messages`, `new_tools` where the human
    or the redaction made a new version and what arrived where neither did, and `new_label`. The raw
    `messages`, `tools` and `label` exist only in `record.document`. **This is what makes the table
    exportable**: its columns are computed from the redacted copies, so there is no raw transcript
    in it to find.
13. **A facet is a column only where it is true of every row in the table**: `language`,
    `personal_data`, `ambiguous`, `domain`, `call_trigger`, `number_turns`, `number_label_tools`,
    `number_provided_tools`, `schema_valid`.
14. **Everything else is a key in `notes`, one JSON column** — `have_conversation_flow` and
    `direction`, each true of a *group* of label sets rather than of the table. **A facet added
    later starts in `notes`**, always, and becomes a column only when something is grouping by it
    often enough for the scan to hurt.
15. `dataset` is computed from `record`. Every column in it comes from the `record` row of the same
    key, so it can be dropped and rebuilt at any time, and nothing writes to it except that
    computation. A `dataset` row that disagrees with its `record` is a bug with one possible cause.

**The precondition.**

16. **A sample whose steps did not run is refused, and nothing is written.** `personal_data` being
    `null` means nobody scanned it. A confirmed span's value still present in `new_messages`,
    `new_tools` or `new_label` means the redaction did not take. Either is a `422` naming the step,
    and neither is a row in either table: `khử nhận dạng` is a condition the `dataset` table has to
    be able to prove about every row it holds, and the cheapest proof is that a row failing it never
    arrived.
17. **The precondition is the modality's and no task writes its own.** What it reads —
    `personal_data.outcome` and the redacted copies — is a text2text shape, and the obligation
    behind it is the law's rather than one task's. A second text2text task inherits it. A legal
    condition is the one rule here where a per-task copy must not exist, because a copy that drifts
    is a corpus sold in breach.
18. Nothing else is refused. A reviewer who decides a sample should not be used does not post it,
    and the page is where that is decided.

**The facets, and which layer owns each one.**

19. A facet is **derived** or **declared**. A derived facet is computed from the record at write
    time and can be recomputed from it; nobody types one, so it cannot disagree with the sample. A
    declared facet is a claim a person made; nothing can check it, and **nothing can fill it in
    afterwards** — which is the whole argument for adding a declared facet to `notes` first.
20. **Derived, and the modality's**, because it reads a shape every text2text task has:
    - `personal_data` — the classes actually redacted, read off the confirmed spans'
      `personal_data_class`: `["EMAIL", "PHONE", "NAME"]`, `[]` where the sample had none. This is
      the patterns the scan redacts by, listed, and it is what tells a buyer what *kind* of
      personal data used to be in a corpus they are being told is clean.
21. **Derived, and the profile's**, because reading them means knowing what this task's input is
    made of:
    - `number_turns` — how many messages the shipped conversation holds. Not every text2text sample
      is a conversation, which is why the modality does not count this one.
    - `number_label_tools` — how many tool calls the shipped label makes. `0` is the no-call
      sample, and `2` or more is a turn answered by several calls at once.
    - `number_provided_tools` — how many tools the catalog offers. One offered tool and five are
      not the same question asked of a model: above one, the sample is also a choice.
    - `schema_valid` — whether every call names a tool in this row's own catalog and supplies that
      tool's required parameters.
22. **Declared, and the modality's**, because any text2text task asks them of any sample:
    - `language` — `vi` or `en`. The flow already declares it per request and then throws it away;
      it belongs on the row, because a scan, a juror and a buyer all need to know.
    - `ambiguous` — the reviewer says this sample is genuinely arguable. Two annotators differing
      on one of these is signal about the task, not a mistake by either, and a corpus that cannot
      mark them will keep re-litigating the same rows.
23. **Declared, and the profile's**, named in this task's vocabulary:
    - `domain` — the **bot's business function**, not the customer's industry: `debt_collection`
      (đòi nợ), `telesale`, `bill_reminder` (nhắc cước), `customer_care` (tổng đài chăm sóc khách
      hàng). **The list lives with the page**, which is where a labeller ticks it, and grows
      there when a bot does a job that is not one of these. Nothing below the edge holds a copy:
      a read of the store answers what the rows carry, never what they were allowed to carry. An
      industry — banking, retail, insurance — is a different axis and is § *Open*.
    - `call_trigger` — **how the call is triggered**, which is the verb of the sample and the facet a
      buyer is really shopping for. One value per call, so a sample holds the set of them:
      - `condition_met` — the bot calls it the moment the arguments and preconditions are there,
        without being asked.
      - `user_utterance` — it fires only because the customer said a particular thing.
      - `every_turn` — the flow obliges it on every turn, whatever was said.
      The list lives with the page and grows there, on the same terms as `domain`. Where the label
      calls nothing, there is no trigger to describe and the facet is empty — the no-call sample is
      `number_label_tools: 0`, and that is where it is counted.
    - `direction` — `inbound` (the customer called) or `outbound` (the bot called). In `notes`,
      because it describes a call bot and not every corpus this table will hold is one.
    - `have_conversation_flow` — true where the sample is a step in a scripted conversation, one
      the bot walks through in order and where reaching a given step is what obliges a call. In
      `notes`, because it is true of a group of label sets rather than of the table.
24. **`call_trigger` is declared because a flat sample cannot prove it.** Whether a tool fired
    because its arguments were finally complete, because the customer said one particular thing, or
    because the flow obliges it every turn is a fact about *the bot's design*, and the evidence for
    it is not inside one sample. The record holds this sample's turns, its catalog and its label,
    and no key joining it to the sample before it — so nothing can tell a tool that happens to be
    called here from a tool that is called every time. It is ticked by the person who knows the
    flow, and `conversation_id` under § *What else to add* is what would let it be checked.

**The statistics.**

25. `GET /text2text/tool-decision/records/stats` answers them, reading and keeping nothing. Every
    statistic is a count with the denominator it came out of — never a bare percentage, because a
    share over nine rows and a share over nine thousand are different claims.
26. **How much.** How many rows each table holds. They agree, and a run where they do not is a bug
    rather than a statistic.
27. **The joint distribution matrix, which is the point of the facets.** A count per value of
    every facet column, and the cross of two of them — `domain` × `call_trigger`, named in the
    router at the call. The counts are `GROUP BY` in the profile's own `schema.py`, which is the
    only layer allowed to say a facet's name out loud.
    **The finding is the zeros.** A corpus with 4,000 `customer_care` rows and no `every_turn` call
    anywhere in `debt_collection` is a corpus that will fail in production in a way its size hides
    completely, and the page's job is to show that cell, empty, next to the full ones. A `GROUP BY`
    returns only the pairs that exist, so what the route answers is the **rectangle** those pairs
    make: every value either axis carries crossed with every value the other does, and a pair no
    sample makes reading `0`. A value one sample carries is in the grid the moment that sample
    lands, because the axes are read off the rows.
    **A value nobody has ticked yet has no cell, and that is the page's half.** The tickable list
    lives with the page (§ *The facets*), so crossing this grid against it -- and counting how many
    of those cells are still empty -- is arithmetic the page does with a list the store never sees.
    **A cell says whether the corpus has such a sample, not how it divides.** `call_trigger` is a
    set, so a sample triggered two ways is evidence for both cells and is counted in both — the
    cells sum past the row count wherever that happens, and a sample that triggers nothing is in no
    cell at all. Counting a set-valued facet *as a set* is the other reading and is what the
    per-facet count answers: which combinations occur.
    **The no-call share** is read off the `number_label_tools` column's own distribution, at `0`,
    over the total. It is not counted a second time from the labels: a second count would be a
    second definition of what a call is, free to disagree with the column the corpus is sold by. A
    corpus that is all tool calls cannot teach a bot to keep its
    hands in its pockets and cannot measure whether it does — *irrelevance detection* is a
    first-class BFCL metric, and a corpus with no such rows scores it at zero by construction.
28. **Schema validity** — the share of `dataset` rows whose `schema_valid` is true. BFCL's AST
    check turned on the corpus rather than on a model: a label calling a tool the sample was never
    offered is not a hard example, it is a broken row.
29. **Label diversity** — how many rows answered at all, and how many **distinct** answers the
    corpus holds between them, counted over the same canonical text the duplicate grouping compares
    by. A thousand rows carrying nine answers between them is a corpus that teaches nine things,
    and nothing about its size says so.
30. **Tools offered and tools called** — how many distinct tools the catalogs offer, and the count
    per tool, a tool never called included as `0`. Offered is counted off the catalogs and not off
    the names the answer lists: a label may name a tool it was never offered, which is a broken row
    rather than an offer, and letting it into the figure would inflate the number the zeros are
    read against. This reads inside `input` and `label` rather than off a facet, so it is the
    profile's and the router asks for it by name; a statistic that silently needs a facet nobody
    keeps is a statistic that breaks in a year. The tail is the finding: a corpus where two tools
    carry 90% of the calls trains a model that knows two tools.
31. **The same input twice**, grouped by `dataset_management` over the whole corpus rather than over
    one posted batch:
    - `duplicate_content_same_label` — redundancy. Safe to drop one, and worth dropping:
      deduplicating training data measurably reduces memorisation and speeds convergence (Lee et
      al., ACL 2022).
    - `duplicate_content_diff_label` — **the same input carrying a different label.** One of them
      is wrong, or the task is ambiguous where the guideline claimed it was not. A queue to
      inspect, not an error count (VariErr NLI, arXiv:2403.01931) — which is also why the declared
      `ambiguous` facet exists.
32. No statistic is stored. Each is a query when it is asked, so a panel cannot be stale.

**The page — a deck, not a scroll.**

33. The labelling page shows **one card at a time**: the guide first, then the eight steps. One bar
    under the card holds all of the navigation — `<`, the rail, `>` — so moving is one place and
    not three. `←` and `→` move a card as well, but only while the focus is outside a field: inside
    a textarea an arrow key moves the caret, and a page that steals it is a page nobody can type
    in.
34. **The deck is not a wizard.** Every card is reachable from every other, in any order, whatever
    has answered so far. The steps are independent — the pipeline spec's *every step is reachable on
    its own* — and a deck that gated one card behind another would put a rule on the screen that
    the service does not have.
35. **The rail gives back what the scroll was giving away for free.** Eight markings in flow order,
    one per step, each carrying that step's state — answered, waiting, edited, refused, not asked —
    and each a jump to its card. A page as tall as eight rectangles shows all eight states for
    nothing; a deck has to hand that back deliberately, or it is the same page with flipping added.
    The rail is also where the fan is drawn: 2, 3 and 4 are grouped, because they are handed the
    same sample and none of them feeds another.
36. **A jump is not a *back to*, and both stay.** The rail moves the reviewer and means nothing
    else. **back to** says *the answer this card was built on is wrong*: it drops the record, marks
    the card it lands on with *make the correction here*, and re-opens **assemble** and
    **approve**. Two different acts, so two different controls — one moves, one changes what will
    ship.
37. **The first card is the labelling guide**, written for the person labelling. What a
    `tool_decision` sample is; what makes a label right, the empty label included — *no tool call
    is needed* is an answer and not a skipped row; what to tick at the two human steps and what
    each declared facet means; what gets a sample refused. No route name, no file path, no sentence
    about how the page is wired.
38. **The guide says what to do; the drawing says why the flow is shaped this way.** That split is
    already the pipeline spec's — `edge/static/index.html` explains the flow, `ui/` labels with it
    — and every card's own note obeys it too: the note in a card is what to do *here*. A sentence
    that would have to be rewritten because a route was renamed is a sentence on the wrong page.
39. **The statistics sit on the guide card, under the guide.** A distribution read in a report is
    a report; read on the card a labeller opens before they start, it is an instruction — *this is
    what the corpus is short of*. That is why they are not a ninth card and not a panel somebody has
    to go looking for.
40. **A strip stays on every card**: how many rows are stored, and **how many cells of the joint
    distribution matrix are still empty**, which the page counts by crossing its own tick lists
    against the grid the route answers. Two items, because the strip is read sideways while the
    reviewer is working on something else. The second is the one that changes what they do next,
    and *which* cells those are is the guide card's to show.
41. The statistics are asked for on load and again after a record is written. Not on a timer, and
    not on every flip.
42. Where no database is attached the strip says so in the service's own words, the guide card shows
    the guide and no statistics, and all eight steps work exactly as they do today. The store is a
    place to put the result, never a dependency of the review.
43. Step 7 grows a tick for **every declared facet**, and the values to tick are the page's own
    list: a tickable value is a thing a person chooses, and the store has no use for one until a
    sample carries it. The cost, stated: a facet the page never draws a tick for is a column that
    is always `null`, and nothing but review catches that. That is where the human already is, and
    a second form at the end would be a second place to describe one sample. **approve**
    posts the record, and the last card says it landed — or names the step that did not run.

## Design

**Why two tables and not one with a filter.** A filter is a thing every future reader has to
remember. Selling a corpus is a `SELECT` someone writes in a hurry, possibly a year from now,
possibly not the person who wrote this. If the personal data is one `WHERE` away from the export,
one day it will be in the export. Two tables make the mistake impossible to make silently: the
export reads `dataset`, and `dataset` holds no raw transcript to find.

**Why the tables belong to the task.** Each task's samples are described by different facets, and a
facet is worth a column when something groups by it. One shared table would make every facet a
nullable column that most rows leave empty, or a JSON blob nothing can index. A table per task
costs a `create_all` per task and buys a schema that says what this corpus actually is.

**Why the refusal is an error and not a row.** A sample arrives here having passed eight steps in
front of a person, so *should this be kept* has already been answered. The only thing left to check
is whether the steps ran at all, and that is a broken request rather than a fact about the corpus.
The cost is stated: nothing counts what the pipeline is failing at, because a failing sample is
never stored. The day that number is wanted, it comes from the flow's own logging and not from a
table of rows that could not be sold.

**Why `record` is one opaque column and `dataset` is many.** The record's envelope is declared at
the boundary that receives it, and mirroring it into columns would put that declaration in the
layer furthest from where it is built — so the review stays a document. Every query this store
answers is about the *corpus* and not about the *review*, and those get their own table with their
own columns.

**Why a facet added later starts in `notes`.** The question a new column has to survive is what
happens to the rows already in the table. A derived facet is recomputed from `record` and loses
nothing. A declared facet cannot be recomputed by anything — a person ticked it once, on a page that
has moved on — so every sample stored before the column existed is blank forever, and a statistic
over it measures when the facet was introduced rather than what the corpus holds. With no
migrations, a column is also a hand-written statement against a live database, where a key in
`notes` is nothing at all.

**Why the facets are derived where they can be.** Every facet a person types is a facet that can be
wrong, and a corpus's description going quietly stale is the failure mode that makes people stop
trusting the numbers. So `personal_data`, `number_turns`, `number_label_tools`,
`number_provided_tools` and `schema_valid` are computed from the row every time it is written, and
the declared half is small, ticked once, and visibly a claim.

**One code path, two DSNs.** `Session.merge` for both writes, inside one transaction — a read by
primary key then an insert or an update, so no dialect-specific upsert is reached for and a
developer's SQLite file and a deployment's Postgres behave the same. The statistics are Core
queries over `dataset` columns, which both dialects group by identically.

**Grouping by input.** The duplicate statistics group rows by *the same input*, and they belong to
`dataset_management`: a duplicate is a fact about a corpus, not about the batch a sample arrived in.
`data_quality/` used to hold a second duplicate check — an embedding call over one posted batch —
that answered `None` and could not be constructed; it is deleted, and this is the only one.
Two JSON columns are not comparable for equality
across dialects and no index can be built on that comparison. The options are a stored `sha256` of
the input canonicalised under one key ordering — fast, indexable, one more column — or a scan hashed
in Python, which is correct and instant at the size this corpus starts from. This takes the scan and
names the digest as the change to make when it stops being instant, because the statistic is
identical either way.

**Why `sample_building` is left open.** The steps a finished review goes through to become a stored
row have not been watched happening to a real sample. Drawing them first is how a shape gets
invented rather than observed, and the shape that gets invented is the one every task afterwards has
to implement. The module fixes the placement and declares nothing until there is something to
declare.

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
the deck there is a title and two numbers; the reading a labeller has to do is on the first card.

**Why the statistics are on a card and not in a dashboard.** A dashboard is a thing somebody opens
on purpose, which means on the day they remember to. These statistics exist to change what gets
labelled next, so they are put where the labelling starts. The same argument is why the strip
carries a count of empty cells rather than a total: a total is a number to feel good about, and an
empty cell is a job.

## What else to add

Proposals, not decisions:

- **Freshness.** Rows created in the last 7 and 30 days, and the newest and oldest `modified_time`.
  Điều 17 requires the seller to publish `mức độ cập nhật`, so this is the one item on this list
  that a sale needs rather than wants.
- **`conversation_id` and `turn_index`.** The single highest-value addition. `call_trigger` and
  `have_conversation_flow` are both assertions today, and with a key joining a sample to the one
  before it they become checkable: `every_turn` is then a thing the corpus can be asked about
  rather than a thing someone ticked. No amount of extra samples fixes that — only this does.
- **A facet for what the *right answer* is**, which `call_trigger` does not cover: the right tool is
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
  inter-annotator agreement: Krippendorff's α needs at least two people labelling one sample, and
  this flow puts one human in front of each record. The day two people review one sample, the store
  either knows who they were or the number cannot be computed retroactively.
- **`reviewed_at`** distinct from `created_time` — when the human answered, as against when the row
  landed. They differ when a backlog is posted, and any per-annotator quality statistic needs the
  former.
- **A `consent` or lawful-basis marker** on `record`. 91/2025/QH15 gives the data subject rights
  over the personal data in that table; which basis each source was collected under is the thing
  nobody can reconstruct later.
- **`industry`** as a second axis beside `domain` — banking, retail, insurance, logistics,
  healthcare, education. `domain` is what the bot is *doing*; industry is who it is doing it for,
  and the same `debt_collection` flow differs between a bank and a telco.

## Invariants

- No row in `dataset` holds a value the redaction was asked to remove and did not. It is checked
  before either row is written (§ *The precondition*).
- `dataset` is a function of `record`. Drop it, rebuild it, get the same table.
- Every `dataset` row has a `record` row under the same key, and the two counts agree.
- No derived facet was ever typed by a person; no declared facet is ever computed.
- `created_time` never moves; `modified_time` never precedes it.
- `sqlalchemy` is named in `edge/database.py` and in each profile's `schema.py`, and nowhere under
  `modalities/` or `services/`.
- No name in `modalities/text2text/dataset_management/` is one task's.

## Out of Scope

- The export itself — the manifest, the licence file, the format a buyer receives. Selling needs
  it; it is its own decision and it reads only `dataset`.
- Deleting a row, and what a deletion request under 91/2025/QH15 does to a corpus already sold. It
  is a real obligation and it is a process, not a column.
- Auth on the write route. Today's flow has none anywhere, and one guarded door in an unguarded
  building is theatre. It becomes urgent the moment `record` holds real transcripts.
- The provenance dossier itself. Per corpus, not per row, and a document rather than a table —
  though `source` above is what it would be assembled from.
- Altering a table that already holds rows. There are no migrations, and what replaces them is a
  decision to take when the first column has to change.

## Open

- **What happens to rows already written when the `domain` list grows.** A closed list catches
  typos and needs an edit to extend; an open one never blocks a labeller and drifts into `cskh`,
  `CSKH` and `cham_soc_kh` being three domains. The list lives with the page; closed-versus-open is
  a decision about how the labelling team works, not about the code. Nothing refuses a value the
  store has not seen before, so a typo becomes a row of the joint distribution matrix and is visible
  there.
- **`industry` as a second axis** — see above. It is a column or a key in `notes` or neither.
- **What a `null` label means.** `[]` and `null` both read as *no tool call is needed*, and
  `number_label_tools` counts both as `0`. The pipeline does not treat them as one answer:
  `label: null` canonicalises as the text `null` and never matches a panel that answered `[]`, so
  `label_agreement` reads 0.0 for a sample the panel agreed with. Either the corpus writes one
  spelling or `normalize_prediction` folds them.
- **Whether this spec's directory keeps its name.** It is `docs/tool-decision-store/`, and what it
  describes is a modality package and a service module both named `dataset_management`. Renaming is
  a move plus one cross-reference in the pipeline spec; leaving it is a directory that names the
  reader's second guess.
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
  (EMNLP 2025). Why a nested call sequence is worth counting separately.
- *ComplexFuncBench: Exploring Multi-Step and Constrained Function Calling under Long-Context
  Scenario.* arXiv:2501.10132. Parameter-value errors as the dominant failure mode.
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
  behind *what agreement would need* are his decision criterion.
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
