# Two tables a task, and the statistics that show what is missing

## What

A reviewed sample lands in **two** tables, written in one transaction.

- **`tool_decision_record`** keeps the whole of what the review answered — what arrived, what
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
having passed the whole review, so nothing in this store decides whether it is worth keeping. What
`tool_decision` stores, in which columns, is declared in `profile/tool_decision/schema.py` — its
own two tables. The SQL over them sits beside it, in the two files that are handed a session. What every text2text sample has in common, whatever the
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
- The DSN is read from `DATAFORCE_DATABASE_URL`, or handed to a `Database` directly. **Unset means
  a SQLite file beside the repository**, made on the way to the first session, so a deployment that
  configured nothing still has somewhere to put a row. A DSN that is set wins, which is how Postgres arrives. The *no store* state every caller
  handles is still reachable, by setting the variable to `off` — it has to stay reachable, because
  the review works without a store and a state nothing can reach is a state nothing tests.
- **There are no migrations.** `Base.metadata.create_all` is the only thing that makes a table, so
  it only ever *creates*. Changing a column on a database that already holds rows is a statement
  somebody writes by hand, which is the reason a new facet goes in `notes` rather than in a column.
- A column is added when a query groups by one. The record's envelope is declared at the boundary
  that receives it, so `record.document` is one JSON column that no query reads inside.
- Which tables exist is the profile's, and `sqlalchemy` is named in two places only:
  `edge/database.py` for the DSN, the engine and the session, `dataforce/tables.py` for the one
  declarative base, and each profile's own files for its tables and the SQL over them. Nothing
  under `modalities/` or `services/` imports it.
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
   `label_statistics.py` and `sample_building.py` are `adapter` and `H-8` sends those imports the
   other way.
4. **`edge/database.py` is the plumbing and declares no table**: the DSN, the engine and the
   session. The one declarative base every task's tables hang off is `dataforce/tables.py`, so one
   `MetaData` knows them all — a base is a noun, and keeping it out of the plumbing is what lets a
   profile's `schema.py` stay a `shape` that imports nothing which opens anything.
5. **A response shape is a noun, so it lives with this task's other nouns.**
   `ToolDecisionDatasetStatistics` is declared in `profile/tool_decision/schema.py`, beside the two
   tables: it says this task's words out loud, and nothing outside this endpoint has a use for it.
   What *fills it in* is `services/tool_decision/dataset_management.py`, which is `logic` and holds
   decisions rather than nouns, so it reads the shape from the profile the way the router does. The
   envelope a record arrives in is the exception: it is declared at the boundary that receives it,
   because the thirteen keys are the page's and no query reads inside them.

**`record` — what the review answered.**

6. One row per reviewed sample: `id`, `document`, `created_time`, `modified_time`. The key is `id`
   alone and it is a **UUID** — the table name is the task, so nothing has to be qualified by one.
   A corpus names its samples `s4471`, not with a UUID, so the key is **derived from the posted
   name** and never minted: one name answers to one key for as long as the corpus keeps calling it
   that, which is what makes requirement 8's *a second post replaces the row* true of the names
   samples actually have. The cost, stated: a row in the table that is sold joins back to the
   corpus it came from through `record.document` rather than through its own key, and two corpora
   reusing one sample name collide here exactly as they already collide in the name.
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
    - **A key in `notes` is read back and counted like any other facet.** It is not a column; it is
      not therefore invisible. `direction` and `have_conversation_flow` were ticked by a person,
      written, and then answered by no route at all — not by the page of rows, not by the row
      opened whole, not by the statistics — which made two of the five declared facets write-only.
      A row opened whole answers every facet it carries in one map, columns and notes keys
      together, and the per-facet distribution counts the notes keys beside the columns.
    - **That count is the scan this requirement priced, and it is done in Python.** Reading inside
      a JSON column is spelled differently in every dialect, and a `GROUP BY` written one way
      would make one file the place SQLite and Postgres stop being one code path — so the column
      comes back whole and the counting happens above it. The day the scan hurts is the day that
      facet earns a column, which is the sentence above unchanged.
    - **A row that predates the facet is counted under `none`**, on the same terms as an empty
      list: a facet declared today means every older row answered nothing, and a chart that
      dropped those rows would draw a corpus smaller than the totals report. *How many rows
      predate this question* is a figure somebody wants rather than one to hide.
15. `dataset` is computed from `record`. Every column in it comes from the `record` row of the same
    key, so it can be dropped and rebuilt at any time, and nothing writes to it except that
    computation. A `dataset` row that disagrees with its `record` is a bug with one possible cause.

**The precondition.**

16. **A sample whose steps did not run is refused, and nothing is written.** `personal_data` being
    `null`, or holding something nothing can read as a scan, means nobody scanned it — evidence that
    cannot be checked proves nothing. A handed-back span whose placeholder is **not standing where
    the span says it stands** means the redaction did not take: read over what ships, and not the
    three `new_` keys read literally, because a `new_` key that is `null` ships what arrived and a
    value surviving there reaches the corpus just the same. The reading is the rewrite read from
    the other side — the rewrite puts one placeholder into the string a span's `path` names, per
    span, so the guard counts them in that one string. A check looser than the rewrite would clear
    a value the rewrite left, and a stricter one would refuse records the rewrite had finished
    with, and *is this value a substring of what ships* is now the stricter one: replacement is per
    span, so a value the reviewer ticked off at one occurrence stands in the copy on purpose, and
    a guard reading it as a failure refuses the ordinary case.
    **And what ships may not have gained a claim.** The spans say *replace these places*; nothing
    on them says what a reviewer typed into the label afterwards, and the form they type it on is
    seeded from what arrived rather than from the copy. So a claimed value standing in a shipped
    part **oftener than it stood in the one that arrived** is the same refusal, counted per part:
    a value redacted out of the turns and typed into an argument reaches the corpus, and over the
    whole sample the two totals would agree. Counted over the record's strings and never over the
    sample serialised — JSON escapes a quote, a backslash and a newline, so a serialised search
    would clear a record still holding one. What is left, stated rather than discovered: a value
    standing where nobody ever handed back a span and what arrived already held it is not refused
    here — `outcome` is the evidence beside it, and card 1 is where the reviewer answered for it.
    Any of the three is a `422` naming the
    step — **and the span or the class, never the value**: a refusal that echoed it would put personal
    data in a response body and in whatever logs one, and the span's number and class, or the class
    and which of the three parts it stands in, is what a reviewer needs to go and tick it anyway. Neither is a row in either table: `khử nhận dạng` is a condition the `dataset` table
    has to be able to prove about every row it holds, and the cheapest proof is that a row failing it
    never arrived.
17. **The precondition is the modality's and no task writes its own.** What it reads — the
    handed-back spans, the field each one names, and the three `new_` keys — is a text2text shape, and
    the obligation behind it is the law's rather than one task's. It reads the spans and **not**
    `personal_data.outcome`: the outcome is what the redaction says about itself, and a record
    saying it is clean is not a record that is. The outcome rides along as evidence, measured
    over what ships, and nothing is gated on it. A second text2text task inherits it. A legal
    condition is the one rule here where a per-task copy must not exist, because a copy that drifts
    is a corpus sold in breach.
18. Nothing else about the *corpus* is refused. A reviewer who decides a sample should not be used
    does not post it, and the page is where that is decided. Two things are refused about the
    *document*, and both are a row that cannot exist rather than a sample that should not be kept: a
    label that never parsed, which the page carries as `{unparsed: …}` and the envelope will not
    take, and a declared facet the table has a column for and the review left unanswered. The second
    is named by name in the `422`, so a reviewer reads a facet to go and tick rather than a column
    that refused a value — § *`dataset`* wants that write to fail, and this is where it fails
    legibly.

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
      tool's required parameters. Computed here, and asked by the labelling page before the row is
      written at all (`docs/tool-decision-pipeline/spec.md` § *Requirements*): one function, read as
      a column on one side and as a sentence per broken call on the other. Two readings of it would
      let the page wave a label through and this table mark that same label broken.
22. **Declared, and the modality's**, because any text2text task asks them of any sample:
    - `language` — `vi` or `en`. The flow already declares it per request and then throws it away;
      it belongs on the row, because a scan, a juror and a buyer all need to know.
    - `ambiguous` — **how arguable the sample is: `LOW`, `MED` or `HIGH`.** A level and not a
      yes, because *arguable* is a matter of degree and a reviewer forced to pick one of two puts
      everything half-arguable on whichever side they lean. Two annotators differing on a `HIGH`
      one is signal about the task, not a mistake by either, and a corpus that cannot mark them
      will keep re-litigating the same rows. The column is text; which levels there are lives
      with the page, like every other declared facet.
23. **Declared, and the profile's**, named in this task's vocabulary:
    - `domain` — the **bot's business function**, not the customer's industry: `debt_collection`
      (đòi nợ), `telesale`, `bill_reminder` (nhắc cước), `customer_care` (tổng đài chăm sóc khách
      hàng). **The list lives with the page**, which is where a labeller ticks it, and grows
      there when a bot does a job that is not one of these. Nothing below the edge holds a copy:
      a read of the store answers what the rows carry, never what they were allowed to carry.
      **The page carries a box that adds one**, and what makes an added domain outlast the tab it
      was typed in is that same read — the offered list is what is declared plus what the rows
      already hold, so a domain becomes permanent by being used. The cost, stated: nothing takes
      one away again, so a typo that reaches a row is offered until that row is fixed. An
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

**The page — one screen, two decisions.**

33. **The sample never leaves the screen.** The page is two panes: the sample on the left — the
    turns and the catalog, rendered as a conversation and not as JSON — and the review on the
    right. The left pane scrolls on its own and is never replaced, because every decision on the
    right is a judgement *about* what is in it. A page that hides the conversation while asking
    whether its label is right is asking the reviewer to answer from memory.
34. **Eight steps are two decisions.** Only three of the eight ever held one: which detected spans
    are real, whether the label ships as it arrived, and what the sample's facets are. The other
    five are machine work, and a screen per machine step is a screen with nothing on it to decide.
    The two decisions are the two panels on the right, in that order, and the facets belong to the
    second because they describe the label's sample and are ticked while the reviewer is already
    looking at it.
35. **One button runs both checks**: the personal-data scan, and the reviewers' vote. One click
    rather than two, and never on load — the vote costs a model call, so a sample opened and
    skipped must be able to cost nothing. The button says which check it is on while it runs, and
    one that fails names itself and stops the one after it.
    - **The duplicate and abnormal scans are off the screen.** Both routes answer as they always
      did and neither is asked from here. They come back when there is something for a reviewer
      to *do* with what they report; until then they are two calls per sample buying a line that
      reads *nothing to report*.
    - **The replacement is not a step.** A value the reviewer keeps is a value that has to come
      out, so it comes out as they tick: unticking a value, saying it is a different kind or adding
      one the scan missed makes the copy again by itself, and a copy that is wrong until somebody
      presses a button is a copy that ships wrong. An answer that arrives after a newer one is
      dropped rather than painted, because it is the copy of values that are no longer on the
      screen.
36. **The checks are two columns: the check, and what it said.** They were three, and the middle
    one — the model that answers — was the point: a picker somewhere further down the page is one
    nobody finds, and a run that stops on *tick a verifier first* with no tick box in sight is a
    dead end. That reason outgrew the table. Since the machine work is two acts rather than one
    run, **each picker travels with the button that spends it**, which is the same rule read at
    the only granularity that now exists — the row a picker sat on was standing in for a button
    that was somewhere else entirely.
    - **Each answer is a verdict and not a payload**: what was found, or that nothing was, in one
      cell. The reviewers' own JSON stays reachable behind a disclosure, because *what did the
      panel actually say* is the question that panel exists to answer. The personal-data routes'
      does not: what a reviewer needs from those is the text, not the keys it came wrapped in.
37. **The reviewer's own two answers are the only required input.** The data panel lists the
    claimed **values** with a keep tick each — and a box to type one the scan missed, which is the
    one field on that panel: where a value stands, how many times and which `<CLASS_N>` it gets are
    the service's answers, so there is no offset to type; the label panel carries which of three
    acts they take, the label behind *write it myself*, and a tick for every declared facet.
    Nothing else on the screen is a field.
    - **What the data panel shows is the review text, as a text**: one string, with the line breaks
      the service wrote into it. A reviewer is judging a conversation, and a conversation printed
      as `{"review_text": "user: …\n…", "outcome": "withheld"}` is one they have to decode before
      they can judge it. Which keys the scan answered under, and how it decided, are the service's
      business.
    - **Which of three acts they take is an act, and none is ticked for them.** They were two,
      *correct* and *modify*, and the reason they were two was that there were two labels to
      choose between — what arrived and what the reviewer typed. There are three: **take the
      reviewers' answer**, **keep what arrived**, **write it myself**. The panel is a prediction
      arrived at from the conversation alone, and it is usually the better of the two that already
      exist, so a screen that made taking it mean *retype it into the box* is how a call two
      models had spelled out shipped as a bare name. The reason the two had stands unchanged:
      *correct* is a thing a person says about a label, not a thing a page assumes while they are
      still reading it.
      Saying which also remakes the copy on the panel above, because the label is rendered into the
      review text (pipeline spec, Requirement 6) — so the text shown is made from the record **as
      it will ship**, and a reviewer who rewrote the label reads the label they wrote. It follows a
      span unticked or a character typed, with an answer that lands after a newer one dropped
      rather than painted. Saying nothing is not refused: the record is redacted and posted either
      way. What is no longer true is that the redacted copy waits for this answer — it is on the
      screen from the moment the values are settled, because the panel is handed that copy and a
      vote spent on a text nobody was shown is a vote nobody can check.
    - **The record the page will post is on the screen while it is being made.** It is composed
      out of the copy above, so it is remade whenever that is, and a facet ticked reaches it too
      — a facet is the one part of a record nothing computes. Shown *before* the post and not
      after: a box that only fills in at the moment of posting, and is wiped by the next sample
      opening, never shows the one thing its name promises.
    - **The label is redacted with the turns, in the same placeholder.** A label is copied out of
      the conversation, so it carries what the conversation carried: a customer who gave a number
      is a `<PHONE_1>` in the turn *and* a `<PHONE_1>` in the argument the call takes. One
      placeholder per value across the whole record is what makes the pair still read as one
      person's number rather than two unrelated redactions, and the redacted review text is where
      a person can see that it did.
38. **The action bar is fixed to the bottom and holds exactly two acts**: skip this sample, and
    submit it. Submit posts the record and opens the next sample in one motion, because a reviewer
    who has to go and fetch the next one has been given a fourth decision. `Enter` submits while
    the focus is outside a field, and nothing else on the page is a keyboard shortcut.
39. **A sample is refused for the same two reasons it always was**, and the refusal lands on the
    panel that owns it rather than in a bar at the bottom: nobody ran the personal-data scan, or a
    value the redaction confirmed still sits in what ships. A declared facet nobody ticked is
    refused the same way, on the label panel, by name. Nothing is written and the reviewer stays on
    the sample.
40. **The guide is a panel the reviewer opens, not a card they pass through.** What a
    `tool_decision` sample is; what makes a label right, the empty label included — *no tool call
    is needed* is an answer and not a skipped row; what each declared facet means; what gets a
    sample refused. No route name, no file path, no sentence about how the page is wired. It opens
    over the screen and closes back to the same sample, because a reviewer who needs it needs it in
    the middle of a sample and not before the first one.
41. **A strip stays across the top**: how many samples are left in the queue, how many rows are
    stored, and **how many cells of the joint distribution matrix are still empty**, which the page
    counts by crossing its own tick lists against the grid the route answers. The third is the one
    that changes what the reviewer does next, and *which* cells those are is the guide panel's to
    show, under the statistics.
42. The statistics are asked for on load and again after a record is written. Not on a timer, and
    not on every sample.
43. **The values to tick are the page's own list**: a tickable value is a thing a person chooses,
    and the store has no use for one until a sample carries it. The cost, stated: a facet the page
    never draws a tick for is a column that is always `null`, and nothing but review catches that.

**Raw data in, and the queue it becomes.**

44. **A corpus is imported once and walked.** The page takes a `.jsonl` file — one sample per line
    — and every line becomes a row waiting to be labelled. A reviewer who has to paste JSON before
    each sample is doing data entry, and the time that costs is the whole of what makes a corpus
    expensive.
45. **Import is idempotent.** A row's key is `uuid5` over the line's own content, so importing the
    same file twice imports nothing the second time. The answer says how many lines were read, how
    many were new, how many were already held and how many were unreadable — and an unreadable line
    is counted and named by its number, never dropped in silence and never a reason to refuse the
    lines around it.
46. **The queue is a third table in this task's profile**, holding the raw line as it arrived, when
    it was imported, where it stands in the walk, and which of *waiting*, *done* or *skipped* it is. Raw, because the reviewer's
    corrections belong to `record` and a queue that held corrected samples could not be re-walked.
47. **A submitted sample is marked done in the same transaction that writes the two tables.** Three
    writes or none. A queue row marked done against a record that was never written is a sample
    nobody will ever be shown again, which is the one failure a corpus cannot detect later.
48. **Skipping is a state, not a deletion.** A skipped row stays, so a corpus can be asked what was
    passed over — and a reviewer who skips is usually saying *not me, not now*, which is a fact
    about the sample and worth keeping.
49. **A sample can also be pasted, into the pane that holds the sample.** An object, an array of
    them, or one per line. Pasting is not a worse import: it is the only way a sample from
    somewhere else arrives, and **it is the only way this page works with the store turned off**,
    because a queue is rows in a table. So a pasted sample is opened and labelled where it is,
    carrying no queue key — nothing was waiting for it, and there is nothing to mark done. The same
    paste can be added to the queue instead, as the same lines a file becomes, so one sample pasted
    twice is one row.
    **Where the box is, is the requirement.** A person looking for somewhere to put a sample looks
    at the thing labelled *the sample*; a paste box behind a button in a panel about importing is
    one nobody finds, whatever it can do. A file is different and stays in that panel — a file is
    not a thing anybody tries to paste.
    A queue with nothing waiting opens the box rather than only reporting that there is nothing,
    because a screen whose only content is *there is no work* offers no next move.
    **A pasted sample is named before it is opened, and the service names it.** A raw corpus line
    is `{messages, tools, label}` and carries no `id`; every route from the scan onward reads a
    sample by name, and the key a record is stored under *is* its name, so an unnamed sample can
    be neither checked nor stored. The name is the same one an import gives — the content's — so
    pasting a sample the corpus already holds lands on that row instead of beside it, and a name
    the line carried is kept, because what a corpus calls its own rows is not this service's to
    overwrite. It is asked for rather than computed on the page: a key made in the browser would
    be a second definition of one, in another language, and the two would drift silently. The
    route that answers it opens no database, which is what keeps this path working with the store
    turned off.
    **And no route demands a name it does not read.** One place in this service reads a sample's
    name — the key a record is stored under. The scans, the replacement, the redaction and the
    vote read the text and nothing else, so a raw line was being refused by them for a field that
    would have gone straight back out unread. Only `POST /records` insists, and it says so in a
    sentence naming where to get a name: a body the service could not read comes back as a
    validation list with the whole sample echoed inside it, and *which field* is then buried in a
    panel holding the reviewer's own conversation. The page reads such a list the same way — the
    field and the message, never the echo.
50. **The queue is a list a reviewer picks from, not only an order they are marched through.**
    Every row, in walk order, whatever state it is in: *what has already been done* is half of
    what somebody scanning the list is looking for, and a list of only the waiting ones cannot
    answer whether a sample was skipped or labelled by someone else. A row carries the opening turn
    as a preview and not the conversation — a list of three hundred transcripts is a page nobody
    can read.
51. **Clicking a row opens it; ticking rows walks just those.** Two acts, because they answer two
    questions — *this one* and *this group*. A ticked group is walked in the order the rows
    arrived, not the order they were ticked: ticking is choosing a subset, never an ordering. A
    reviewer who never opens the list is marched through the queue's own order, which is what they
    get today.
52. **The page says which database a record will land in, and never the DSN.** A connection string
    carries a password and the page is readable by anyone who can open it, so what is shown is the
    database named — a file name, or a dialect, a host and a name — and nothing that would let a
    reader connect. It is shown rather than chosen: a page that could set the DSN would let anyone
    who opens it point this service at any database it can reach, which is a much larger thing
    than telling them where they are. There is always one to name: a deployment that named
    nothing still writes somewhere, so the answer is never *none*.
53. **The corpus can be read back, and only the redacted half of it.** Between the queue, which
    says what is *waiting*, and the statistics, which say what the whole comes to, a row somebody
    had written was readable nowhere — and a sample pasted straight in never had a queue row at
    all, so it went invisible the moment it stored. `GET /records` answers a page of
    `tool_decision_dataset` and `GET /records/{key}` one row of it whole; there is **no route to
    `tool_decision_record`**. That table keeps what arrived un-redacted, because that is what
    makes a review auditable, and serving it would put a person's number on the screen of anyone
    who can open the page — which is the thing this whole part exists to prevent.
    - **What a page of it carries is the facets, not the samples.** A page of three hundred rows
      would be three hundred conversations; what somebody scans a corpus for is which rows are
      short, which are arguable, and which ones nothing could validate. The sample itself comes
      back only for the row they open.
    - **`schema_valid` is the column worth the trip.** A label that names a tool the catalog does
      not offer, or leaves out an argument it requires, reads false — and false beside
      `number_label_tools` zero is a label that *named* a tool without calling it, which is how a
      corpus writing `["VerifyEmail_15d"]` shows up. It is told from a sample correctly labelled
      as needing no tool, which is zero beside true. The list can be narrowed to those rows,
      because finding them is the reason to open it.
54. **A row can be taken back out, and taking it out reaches both tables.** Reviewing is not only
    adding: a sample labelled against the wrong catalog, a line imported from a file somebody meant
    to fix first, a duplicate nobody saw until it had landed — each is a row the corpus is worse for
    holding, and a corpus with no way to take one out is one that gets corrected by dropping the
    whole database. The rows are ticked on the sheet that lists them and `DELETE /records` takes
    the keys, which is the same shape the list already uses for *this group* rather than a second
    idea of how a group is named.
    - **Both tables in one transaction, or neither.** Requirement 47 read backwards. `dataset` is
      computed from `record` (Requirement 15), so a delete that took only the redacted half would
      be undone by the next rebuild — and the half it left standing is the one holding what
      arrived, un-redacted, which is the half a deletion demand under 91/2025/QH15 is actually
      about.
    - **The queue is not touched, and that is said here rather than left to be found.** A queue row
      holds the raw line as it was imported, un-redacted, and it is keyed by the line's own content
      rather than by the record's key. So deleting a stored sample takes it out of the corpus and
      leaves the row saying it was imported and labelled — which is true, and is what keeps the
      sample reachable from the list for anyone who wants to label it again. **A deletion demand is
      therefore not finished by this route**: the queue is the un-redacted staging table and
      emptying it is a different act, which this service does not offer today and which the person
      running the deployment has to know is still theirs to do.
    - **It cannot be undone, so it is armed and then confirmed.** `record` is the only copy of what
      arrived; there is no recycle bin to put it in and nothing to restore it from but a backup of
      the database. One click arms the act and names what will go, a second does it, and the words
      say both tables rather than *this row*.
    - **A key the corpus does not hold is not a refusal.** Two people with the sheet open and one
      of them deletes: the other's tick names a row that is already gone, and refusing the whole
      call would leave every row that *is* there standing for no reason. A call naming no key at
      all is refused, because that one can only be a mistake.
    - **The route answers no body.** `204`, and the sheet reloads. A delete has nothing to say that
      the caller does not already know: it named the keys, and the page of rows under the act is
      what shows the corpus moved. Counting the rows that went, or naming the ones nothing held,
      would be a second reading of the same fact — and two figures free to disagree.
55. **The tables are made on the way to a session, not once at startup.** `create_engine` does not
    connect, so a database is only ever *named* until something reads it — and one named at startup
    can be gone by the afternoon. A SQLite file is deleted, restored from a copy, or cleared by a
    suite run beside the service. What answered then was `500 Internal Server Error`, at the end of
    the one flow a reviewer cannot repeat from memory, with no way back but a restart. Now the
    session that finds them gone makes them again and the write lands.
    - **An unlinked file has to be noticed, not just made again.** A file lives on behind every
      connection still holding it, so a pool opened before the delete goes on reading and writing a
      path nothing can find. Making the tables again on *that* is worse than the fault it replaced:
      the write answers 200 and is gone with the process. The pool is dropped when the file the URL
      names is not on disk, which is what makes the next connection open the name and find nothing.
    - **Every session asks, and nothing remembers having asked.** Against a SQLite database that
      already holds the tables the ask costs 0.11ms, which is less than anything else in the
      request. A memo would only ever save a round trip on a server dialect, and no deployment can
      name one today — so it was a cache guarding a case nobody can reach. Remembering is the thing
      to add back the day a URL can be handed in from outside, and not before.
    - **No suite removes a database to check itself.** This repository's own cleared the default
      file in the checkout before every test, which is how the corpus behind a running service was
      lost and how all of this was found. What a test may not do is *reach* that database, and the
      engine is where reaching one is decided, so that is where it is refused.
56. **A store that answers badly refuses in the service's own words.** `create_all` cannot reach a
    host behind a typo or a firewall, a database this service has no rights on, or a disk that is
    full — so those remain, and what used to answer them was the statement's own error. They answer
    **503**, and the words name the database that did not answer.
    - **Neither the URL nor the statement reaches the screen.** The first for Requirement 52's
      reason. The second for one particular to this service: SQLAlchemy prints an error with its
      bound parameters attached, and on a write those parameters are the sample, un-redacted half
      included. The log is given the driver's own message, which is the fault without the row.
    - **The database answering badly is this state; this service asking badly is not.** A fault in
      the SQL written here is a bug in this repository, and answering it with a database to check
      would send somebody to read their deployment for it. Those still answer 500.

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

**Why the refusal is an error and not a row.** A sample arrives here having passed the review in
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

**Why two panes and not a sequence.** A sequence — a card per step, or a page as tall as all of
them — makes the reviewer navigate between the thing being judged and the judgement. Every such
shape has the same fault: at the moment the label is decided, the conversation it is a label *of*
is somewhere else. Two panes fix the fault rather than the symptom. What a sequence is good at,
showing where the work has got to, is handed back by the panels being open at once: every step's
state is readable without going anywhere.

**Why the machine steps are two buttons.** Five of the eight steps are calls the reviewer cannot
influence — they read the sample and answer. Their being separate was a fact about the service's
routes leaking onto the screen, and for as long as nothing was decided between them one button was
the honest shape. Something is decided between them now: **which values are personal data is a
human answer, and the panel is handed the record as it reads once those values are out.** A single
button would run the vote against spans nobody had approved, and would show a model the customer's
number — so the scan is one act and the vote is another, each with the picker that spends it and
each where its work is: the scan at the head of the card it fills, the vote at the foot of the card
that feeds it and directly above the card it fills. Neither is automatic on load, for the reason one button
was not: the vote spends a model call, and a corpus is walked by people who skip. Free work could
run on load; work that costs money waits to be asked.

**Why the verdict and not the payload.** A route answers JSON and the old page showed it, which
made every step's panel the same size whatever it said. A reviewer needs *nothing was found* in one
line and the whole payload only when they doubt it. The disclosure is not a tidying-up: a verdict
nobody can check is worse than a payload nobody reads.

**The height.** The two panes scroll independently and the strip and the action bar do not scroll
at all. Whatever the sample's length, submit is in the same place — a reviewer doing this four
hundred times reaches for it without looking, and a button that moves costs more than it looks like
it should.

**Motion.** Panels open and close, and nothing else moves by itself. None of it under
`prefers-reduced-motion`.

**Why the header is a title and the strip.** Architecture prose — one call per rectangle, what
`config/model/` holds, where the record goes — is true and is not for the person labelling, who
needs to know what a good label is. It belongs on the page whose job is explaining the flow. Above
the panes there is a title and three numbers; the reading a labeller has to do is in the guide.

**Why the statistics are in the guide and not in a dashboard.** A dashboard is a thing somebody
opens on purpose, which means on the day they remember to. These statistics exist to change what
gets labelled next, so they sit behind the one panel a reviewer already opens when they are unsure,
and their headline — the count of empty cells — is on the strip where it cannot be missed. That is
also why the strip carries empty cells rather than a total: a total is a number to feel good about,
and an empty cell is a job.

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
- `sqlalchemy` is named in `edge/database.py`, in `dataforce/tables.py` and in each profile's own
  files, and nowhere under `modalities/` or `services/`. A profile's `schema.py` names the column
  types; the files handed a `Session` name the statements.
- No name in `modalities/text2text/dataset_management/` is one task's.

## Out of Scope

- The export itself — the manifest, the licence file, the format a buyer receives. Selling needs
  it; it is its own decision and it reads only `dataset`.
- What a deletion demand under 91/2025/QH15 does to a corpus **already sold**, and what it does to
  the queue. Requirement 54 takes a row out of the two tables this service owns, which is as far as
  a route reaches: a copy in a buyer's hands is a process and a contract, and the raw line in the
  queue is a table this page has no act on. Both are real obligations and neither is a column.
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
- **Which language the guide is written in.** The repository is written in English and the
  labellers work in Vietnamese. The guide is the first page here whose reader is not a developer,
  so nothing before it has had to decide this, and the panels' own notes go the same way the guide
  does.

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
