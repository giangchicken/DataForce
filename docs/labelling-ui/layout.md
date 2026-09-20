# Layout

Where each thing goes — on the screen and on disk. `spec.md` says what must be true, `plan.md`
schedules it, this says which region and which module each sentence lands in. No function bodies.

**This document is true until the tree is.** Once a module exists, the module is the answer; once
the screen is drawn, the screen is.

The sketches below are the screen **after** the redesign `spec.md` § *The screen* asks for. What is
already there today is marked, so a reader can tell a move from a change.

---

## The screen

### One idea

> **The left pane is what arrived. The right pane is what a person decides. Nothing crosses — and
> nothing is asked of a model until the person has approved what it will be shown.**

A reviewer never edits the conversation — that is what a customer said, and a page that let it be
retyped is a page that can make the sample agree with the label instead of the other way round. The
one thing they may rewrite is the label, and that box is on the right.

### The frame

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│  Tool decision    sqlite · dataforce.sqlite3    12 waiting · 340 stored · 18 empty cells       │ header
│                                                    [Samples] [Dataset] [Import] [Guide]        │ fixed
├───────────────────────────────────────────┬───────────────────────────────────────────────────┤
│  ← WHAT ARRIVED (read only) ──── scrolls →│ ← WHAT A PERSON DECIDES ──────────────── scrolls →│
│                                           │                                                    │
│  The sample          s1  [Paste a sample] │  ┌ 1 · Which of these are personal data? ────────┐ │
│                             Language [vi▾]│  │                            2 found · 1 kept   │ │ ← state
│  ┌─────────────────────────────────────┐  │  │  [Find personal data]   with (•)DeepSeek ( )… │ │ ← act at
│  │ assistant  Dạ em chào anh chị…      │  │  │                                                │ │   the head
│  │ user       anh muốn học QTKD        │  │  │  keep  what it is   the value        occurs    │ │
│  │ assistant  …anh cho em xin email    │  │  │  [x]   EMAIL     ▾  namng123@gmail…    ×2      │ │
│  │ user       nam nguyen 123 a còng…   │  │  │  [ ]   PERSON    ▾  nam                ×1      │ │
│  └─────────────────────────────────────┘  │  │                                                │ │
│                                           │  │  + the scan missed one:                        │ │
│  Tools offered                    5 tools │  │    [ paste the value here            ] [EMAIL▾]│ │ ← by value,
│  ┌─────────────────────────────────────┐  │  │    [Add it]   every occurrence is found for you│ │   never an
│  │ VerifyEmail_15d(email)              │  │  │                                                │ │   offset
│  │   kiểm tra tính hợp lệ của email    │  │  │  The conversation the reviewers will be handed │ │
│  │ GetTemperature_020(location)        │  │  │  ┌──────────────────────────────────────────┐  │ │
│  │ ReadTextFile_6a7(file_path)         │  │  │  │ user: email của anh là <EMAIL_1>         │  │ │
│  └─────────────────────────────────────┘  │  │  │ label: VerifyEmail_15d(email=<EMAIL_1>)  │  │ │
│                                           │  │  └──────────────────────────────────────────┘  │ │
│  ▸ The sample as it arrived               │  │  ▸ the spans this made, and what they replace  │ │
│                                           │  │ ─────────────────────────────────────────────  │ │
│                                           │  │  [Ask the reviewers]  jury [x][x] tuned (•)( ) │ │ ← act at
│                                           │  │   they read the text above, and nothing else   │ │   the foot
│                                           │  └────────────────────────────────────────────────┘ │
│                                           │                                                    │
│                                           │  ┌ 2 · Which call should this be? ───────────────┐ │
│                                           │  │                              2 of 3 agree     │ │ ← state
│                                           │  │  ╭ what the reviewers propose ───────────────╮ │ │
│                                           │  │  │ tool      VerifyEmail_15d                 │ │ │
│                                           │  │  │ email     <EMAIL_1>          ✓ required   │ │ │
│                                           │  │  ╰───────────────────────────────────────────╯ │ │
│                                           │  │  ╭ what arrived with the sample ─────────────╮ │ │
│                                           │  │  │ tool      VerifyEmail_15d                 │ │ │
│                                           │  │  │ ⚠ named, never called — no email argument │ │ │
│                                           │  │  ╰───────────────────────────────────────────╯ │ │
│                                           │  │  ( ) Take the reviewers' answer                │ │
│                                           │  │  ( ) Keep what arrived                         │ │
│                                           │  │  ( ) Write it myself    ▸ each vote, in the    │ │
│                                           │  │                           juror's own words    │ │
│                                           │  │  What kind of sample is this?                  │ │
│                                           │  │   domain      (•) telesale ( ) debt_collection │ │
│                                           │  │               ( ) bill_reminder ( ) …   [+add] │ │
│                                           │  │   call_trigger [x] user_utterance [ ] every_turn│ │
│                                           │  │   direction   (•) inbound ( ) outbound         │ │
│                                           │  │   ambiguous   ( ) LOW (•) MED ( ) HIGH         │ │
│                                           │  │   have_conversation_flow  [ ] yes              │ │
│                                           │  └────────────────────────────────────────────────┘ │
│                                           │                                                    │
│                                           │  ┌ What will be written ─────────────────────────┐ │ table
│                                           │  │ key           8f2a…                            │ │ not
│                                           │  │ label         VerifyEmail_15d(email=<EMAIL_1>) │ │ JSON
│                                           │  │ domain        telesale                         │ │
│                                           │  │ schema_valid  yes                              │ │
│                                           │  │ values kept   1 of 2, replaced in 2 places     │ │
│                                           │  │                            ▸ the raw record    │ │
│                                           │  └────────────────────────────────────────────────┘ │
├───────────────────────────────────────────┴───────────────────────────────────────────────────┤
│  [Skip]        2 left: ask the reviewers · tick a domain                  [Submit & next]       │ action
└───────────────────────────────────────────────────────────────────────────────────────────────┘ bar
```

Three things never move: the header, the action bar, and the fact that there are two panes. The two
panes scroll on their own, so submit is in the same place whatever the sample's length — a reviewer
doing this four hundred times reaches for it without looking.

**There is no panel for machine work.** Each act is a row at the point in a card where it is
needed — the scan at the head of card 1 because it is what fills it, the vote at the **foot** of
card 1 because that is where the hand already is when the spans are done, directly above the card it
fills. Each model picker travels with the button that spends it, which is what the store spec's
three columns were for. What a check said is the state word in the head of the card it filled, so
nothing is reported twice.

### The order the work happens in

```
  open a sample
        │
        ▼
  [Find personal data]  ── head of card 1 ──►  values claimed, each with a class
        │
        ▼
  untick what is not personal data  ·  type any value the scan missed
        │                                        │
        │                    every occurrence found for you, numbered by the
        │                    same function that numbered the scan's own
        ▼                                        ▼
  the record is redacted as you go, and the text below shows it
        │
        ▼
  [Ask the reviewers]  ── FOOT of card 1, where your hand already is
        │
        │  the jurors are handed the REDACTED conversation and the catalog — never the label
        ▼
  a proposed call, with <EMAIL_1> in the argument because that is what the turn says
        │
        ▼
  take it · keep what arrived · write it myself
        │
        ▼
  tick the facets ──► read the record as a table ──► [Submit & next]
```

**Why the redaction is in the middle and not at the end.** A juror handed the raw conversation
writes the customer's real address into the argument, and the placeholder that ends up in the stored
label is then this service's substitution rather than the model's reading. Handed the redacted one
it writes `<EMAIL_1>`, because `<EMAIL_1>` is the only thing in the turn it is reading from. One
value, one placeholder, in the turn and in the call — and the model was never shown the address.

**Why the second button is at the bottom of the first card.** Because that is where the work that
unlocks it ends. A button at the top of the pane makes a reviewer who has just finished ticking
scroll back up to press it, and reads as belonging to something other than what they just did.

### A span is a value, not a pair of numbers

What a reviewer touches:

```
  keep  what it is      the value                occurs
  [x]   EMAIL      ▾    namng123@gmail.com        ×2      ← found in the turn and in the label
  [ ]   PERSON     ▾    nam                       ×1      ← unticked: stays in the text as it is

  + the scan missed one:
    [ namng123@gmail.com                    ]  [EMAIL ▾]  [Add it]
                       every occurrence is found for you
```

What the service answers, and nobody types: where that value stands, how many times, which
occurrences have a word character against them and do not count, which nested span is dropped, and
which `<CLASS_N>` it gets. Those are `order_claims_by_class` and `find_and_number_spans` — the same
two the detector runs — so a value the reviewer added is numbered by the rule that numbered the
rest, rather than by a second rule written for people who add things.

**Three controls go with the offsets.** The table behind *The spans, by offset*; *Re-read the rows*,
which existed only to re-slice what somebody typed; and the **`auto` tick box** — *drop any span
inside a longer one* is what `find_and_number_spans` does unconditionally, so the tick box was the
page holding a second copy of that rule. `app.js`'s `inside` is that copy, character for character,
and it goes too.

What is left as a disclosure is *the spans this made, and what they replace* — read-only, for
somebody checking the redaction rather than editing it.

### The label, written by hand

Chosen by *Write it myself*, and built out of the sample's own catalog. No JSON anywhere in it.

```
┌ Write the call ───────────────────────────────────────────────────┐
│  tool   [ VerifyEmail_15d                                     ▾]  │ ← the 5 tools this sample offers
│         kiểm tra tính hợp lệ của một địa chỉ email                │ ← the catalog's own description
│                                                                   │
│  email  [ <EMAIL_1>                                            ]  │ ← required, marked
│         Địa chỉ email cần kiểm tra. Đúng định dạng email.         │ ← the parameter's own description
│                                                                   │
│  [+ another call]                          [x] this turn needs no │
│                                                 tool at all       │
└───────────────────────────────────────────────────────────────────┘
```

The fields are the picked tool's `parameters.properties`, each with its own `description`, and the
ones in `required` are marked. **No call is an answer**, so the box that says the turn needs none is
on the form and not a thing you achieve by deleting text.

### What each region is for

| region | holds | who writes it | editable |
|---|---|---|---|
| **header** | the brand, which database, the corpus counts, the four sheet buttons | the service | no |
| **left pane** | the conversation, the tool catalog, the raw sample | the corpus | **never** |
| **the two acts** | *Find personal data* at the head of card 1, *Ask the reviewers* at its foot | — | the model pickers beside each, and pressing them |
| **card 1** | the claimed values, which are kept, any the reviewer adds, and the conversation the reviewers will be handed | the scan, then the person | the keep ticks, a value's class, and a value typed in |
| **card 2** | what the panel proposes, what arrived beside it, which of the two ships, and the facets | the panel, then the person | which answer ships, the call itself, the facets |
| **the record table** | every key that will land in a row, in words | the page | no — it is read and confirmed, never typed |
| **action bar** | what is still unanswered, and the two acts | the page | no |
| **sheets** | the guide, import, the samples list, the stored corpus | the routes | import and the list's picks |

**The data half** is the left pane: everything there arrived and nothing in it can be edited. The
two acts sit inside card 1 rather than in a region of their own, because an act belongs where the
work it follows ends. **The labelling half** is the two cards: the keep ticks, which answer ships, the call
itself where they write it, and the facet ticks. Those four are the whole of what a review adds to a
sample, and the record table at the bottom is those four read back before anything is written.

### A sheet, open over the screen

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░ the screen, dimmed and still there ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐    │
│   │  Samples in the queue                                                     [Close]    │    │
│   ├─────────────────────────────────────────────────────────────────────────────────────┤    │
│   │  [ ]  key        state      the opening turn                                         │    │
│   │  [x]  a1f2…      waiting    xin chào, cho em hỏi về gói vay…                         │    │
│   │  [ ]  b7c3…      done       anh muốn học quản trị kinh doanh                         │    │
│   │  [x]  c9d1…      skipped    tôi cần kiểm tra đơn hàng                                │    │
│   ├─────────────────────────────────────────────────────────────────────────────────────┤    │
│   │  [Label the selected]  [Clear selection]                          2 rows selected    │    │
│   └─────────────────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

All four sheets are this box: a head with the title and **Close**, a scrolling body, and an action
row only where the sheet has an act. They open over the screen and close back to the same sample,
because a reviewer who needs the guide needs it in the middle of a sample and not before the first.
`Escape` closes whichever is open.

### Narrow

```
┌─────────────────────┐   The panes stack, the sample first: it is
│ header (wraps)      │   what every question below is about, so it
├─────────────────────┤   cannot be the thing you scroll past.
│ the sample          │
│ tools offered       │   Nothing else changes shape, because the acts
├─────────────────────┤   already sit inside the cards rather than in
│ card 1              │   a row of three columns that a phone cannot
│   ├ find            │   hold. A model picker wraps under its own
│   ├ the values      │   button and stays with it.
│   └ ask             │
│ card 2              │   The action bar stays fixed at the bottom.
│ what will be written│
├─────────────────────┤
│ [Skip]  [Submit]    │
└─────────────────────┘
```

## Every control, and what it does

### The header

| control | what it does |
|---|---|
| `store` *(text)* | names the database a record will land in — a file name, or a dialect, a host and a name. **Never the DSN**: a connection string carries a password. Says so, and names the variable to set, where nothing is attached |
| `strip` *(text)* | how many samples are waiting, how many rows are stored, and how many cells of the joint distribution are still empty. The third is the one that changes what the reviewer does next |
| **Samples** | opens the queue sheet and asks `GET /queue` |
| **Dataset** | opens the stored-corpus sheet and asks the first page of `GET /records` |
| **Import** | opens the import sheet. A file, not a paste — a file is not a thing anybody tries to paste |
| **Guide** | opens the guide: what a sample is, what makes a label right, what each facet means, what gets a sample refused |

### The left pane — what arrived

| control | what it does |
|---|---|
| `sample-name` *(text)* | the key this sample is stored under. A pasted sample is named by the service before it opens |
| **Paste a sample** | opens the paste box, in *this* pane — a person looking for somewhere to put a sample looks at the thing labelled *the sample*. Opens by itself when the queue has nothing waiting |
| `language` `vi` / `en` | declared, never guessed. Rides to the personal-data scan and to the jurors' prompt. Defaults to `vi`, the language this corpus is in |
| **Use this sample** | names the pasted lines through the service and opens the first one here. Works with the store turned off |
| **Add to the queue instead** | sends the same lines to `POST /queue/import`, so one sample pasted twice is one row |
| **Cancel** | puts the box away. What was typed stays until the next sample opens |
| `turns`, `catalog` | the conversation and the tools offered, drawn as themselves. Read-only, always |
| ▸ **The sample as it arrived** | the raw JSON, collapsed |

### The two acts, and where each one sits

| control | where | what it does |
|---|---|---|
| **Find personal data** | head of card 1 | the scan, on the sample as it arrived. **Never on load.** What it claims fills the table under it |
| `verifier-ticks` *(one of)* | beside that button | which model confirms the claimed values |
| **Ask the reviewers** | **foot of card 1** | the panel, on the **redacted** record — so a juror reads `<EMAIL_1>` and writes `<EMAIL_1>`. **Disabled until the scan has run and the values are settled**, and says so while it is. Never on load: the vote costs a model call, so a sample opened and skipped costs nothing |
| `jury-ticks` *(any of)* · `sft-ticks` *(one of)* | beside that button | which models vote, and which finetuned model answers beside them |
| the state word in each card's head | — | what that check said: *2 found · 1 kept*, *2 of 3 agree*. One place, not two |

The three lists are drawn from `GET /models`, which is `config/model/` read as a directory. A model
picked and still served keeps its tick when the list is redrawn.

### Card 1 — which of these are personal data?

| control | what it does |
|---|---|
| `keep-table` *(tick per row)* | one row per claimed **value**: keep it or leave it, what kind it is, and how many times it occurs. What you untick stays in the text exactly as it arrived |
| the class picker on a row | what a value is, where the scan guessed wrong. Changing it renumbers, because `<CLASS_N>` counts per class |
| **the value box + class + Add it** | a value the scan missed. Type it once; **every occurrence is found for you**, because that is what `find_and_number_spans` does with any value handed to it |
| `review-text` *(text)* | the sample as one string, with its own line breaks. Two versions, and the label above says which: *the text the scan reads* before anything is kept, and **the conversation the reviewers will be handed** after — which is the thing a person most needs to see before spending a model call on it |
| ▸ **the spans this made, and what they replace** | read-only: each occurrence, its placeholder, and the text it stands in for. For checking a redaction, not for editing one |
| `data-refusal` | why a submit was refused, in the service's own words, on the card that owns it |

**Nothing here is asked for.** A value kept is a value that has to come out, so the copy that ships
is remade as you tick — there is no second button, and an answer that lands after a newer one is
dropped rather than painted. Renumbering costs no model call: the route that answers it runs two
pure functions and nothing else.

### Card 2 — which call should this be?

| control | what it does |
|---|---|
| **what the reviewers propose** *(table)* | the panel's own answer, as a call: the tool, then one row per argument with its value. Beside the heading, how much of the panel agreed. The arguments carry placeholders because the jurors read a redacted conversation |
| **what arrived with the sample** *(table)* | the corpus's label, in the same form, so the two can be compared without reading either as JSON. A label that names a tool and never calls it says so here in words |
| `label-fault` | a warning, never a gate: the call names a tool the catalog does not offer, or leaves out an argument it requires. What the label ought to be is the reviewer's to say |
| **Take the reviewers' answer** | the proposal becomes what ships, in one click. This is the act the panel exists for, and it is why a full call is drawn instead of a bare name |
| **Keep what arrived** | the corpus's label ships as it is. Still an act a person performs; nothing is ticked for them |
| **Write it myself** | opens the form. The tool is picked from the tools this sample offers, each argument is a field labelled by the catalog's own description, and *this turn needs no tool at all* is a box rather than an empty text area |
| **+ another call** | a label is a list of calls, so a second one is a second block on the form |
| ▸ **Each vote, in the juror's words** | one row per juror: which model, what it answered, and **why** — the `reason` its prompt asks for. This is what a disagreement is read off. The raw JSON is under it |
| `domain-ticks` + **Add domain** | the facet a corpus grows. A domain added is offered from that moment, and still offered after a reload once one sample carries it |
| `facet-ticks` | one tick group per declared facet — `call_trigger`, `direction`, `ambiguous`, `have_conversation_flow` — each with what it means beside it. Nothing is pre-ticked: a default would be a claim nobody made |
| `label-refusal` | a declared facet nobody ticked, named |

**The three acts are what the screen already asks for, spelled honestly.** Today it is two radios
plus a button called *Rewrite it as the reviewers did*, which is three acts wearing two shapes — and
the one that takes the panel's full call is the one hidden behind the button.

### What will be written

| row | holds |
|---|---|
| **key** | what the record is stored under — the name the service gave this sample |
| **label** | the call that ships, written the way the catalog writes it: `VerifyEmail_15d(email=<EMAIL_1>)` |
| **the facets** | one row each, in words, exactly as ticked |
| **schema_valid** | yes or no, and this is the row worth reading twice: it is the store's own rule, asked before the row is written rather than found by somebody reading the corpus days later |
| **spans kept** | how many of what was found is replaced, so the redaction is visible as a number |
| ▸ **the raw record** | the JSON, for whoever wants it. Collapsed, and never the first thing |

Read and confirmed, never typed. It is remade whenever anything above it changes, and it is on the
screen **before** the post — a box that only fills in at the moment of posting never shows the one
thing its name promises.

### The action bar

| control | what it does |
|---|---|
| `submit-note` *(text)* | **what is still unanswered**, counted across both cards, live. Not a refusal — this is the same fact said early, where it changes what happens next |
| **Skip** | marks the queue row *skipped* and opens the next. A state, not a deletion: a corpus can be asked what was passed over |
| **Submit & next** | posts the record and opens the next sample in one motion. `Enter` does the same while the focus is outside a field, and nothing else on the page is a shortcut |

### The four sheets

| sheet | holds | acts |
|---|---|---|
| **Guide** | what a sample is, what makes a label right, what each facet means, what gets one refused. No route name, no file path | Close |
| **Import** | a `.jsonl` file, one sample per line. The answer says how many were read, new, already held and unreadable — an unreadable line is named by its number | **Import**, Close |
| **Samples** | every queue row in walk order with its state and its opening turn. Clicking one opens it; ticking rows walks just those, in the order they arrived | **Label the selected**, **Clear selection**, Close |
| **Dataset** | **what the database holds right now**: which database it is, the counts, the statistics grid with its empty cells, and a page of stored rows — the facets, not the samples. Narrowable to the rows nothing could validate. One row opens whole. **Only `tool_decision_dataset`, the redacted half** — there is no route to `tool_decision_record` and this sheet does not ask for one, because that table keeps what arrived un-redacted | **Show more**, *only invalid*, Close |

---

## What changes on the screen, and what does not

| | today | after |
|---|---|---|
| the two panes, and what is in them | ✔ | unchanged |
| the checks | one button running both, in `<article class="panel">` identical to the two decisions | **no panel at all**: two acts, each at the point in a card where it is needed — and the vote may not run until the values are settled |
| where the next button is | at the top of the pane, whatever you were doing | **at the foot of card 1**, where the work that unlocks it ends |
| a span | `start` and `end`, typed into a table of integers | **a value and a class.** Type the value once; every occurrence is found and numbered by the service |
| the nesting rule | in Python **and** in JavaScript, character for character | **in Python only.** The `auto` tick box and `inside` both go |
| what the panel says | `consensus` as a string, behind *Rewrite it as the reviewers did* | **the proposal at the head of card 2, as a call** — tool, then one row per argument |
| what the jurors read | the raw conversation; the label redacted afterwards | **the redacted conversation**, so the argument carries the placeholder because the model read one |
| the verdict | *Correct* / *Modify*, plus a button that is a third act | **three acts, named**: take the reviewers' answer · keep what arrived · write it myself |
| editing a label | a `<textarea>` of JSON | **a form** built from the sample's own catalog, with each argument's description beside it |
| the record | `<pre>` of JSON behind a disclosure | **a table**, in words, with the raw JSON under it |
| the two decisions | headed `1 The data`, `2 The label` | headed by the **question** each asks |
| what is unanswered | said as a refusal, after submit | said in the bar, **before** — and still as a refusal after |
| spacing | 20 distinct pixel values | **6 tokens**: 4 / 8 / 12 / 16 / 24 / 32 |
| type | 5 sizes, one of them `12.5px` | **3 sizes** |
| *a small grey line* | `note`, `lab`, `lab tight`, `lead`, `verdict`, `said` | **one** name |
| waiting | one string, on the strip | a skeleton in every table about to fill |
| disclosures | 4, all correct | unchanged, and the only collapsed things |

---

## The source

### The tree

```
src/dataforce/ui/
├── index.html          the frame, and the one place an id is declared      (CHANGED)
├── style.css           tokens · primitives · components · screens          (CHANGED)
├── app.js              wiring  · the composition root                      (CHANGED)
├── wire.js             adapter · one call, one reading of a refusal        NEW
├── screen.js           adapter · that the page is a DOM at all             NEW
├── held.js             shape   · what the page holds between two samples   NEW
├── conversation.js     adapter · a turn, a call and a label, drawn         NEW
├── checks.js           adapter · the two acts, and which may run yet       NEW
├── models.js           adapter · which models answer                       NEW
├── personal-data.js    adapter · card 1                                    NEW
├── label.js            adapter · card 2, above the facets                  NEW
├── facets.js           adapter · card 2, the facets                        NEW
├── record.js           logic   · the one thing this page composes          NEW
├── queue.js            adapter · which sample is on screen, and the list   NEW
├── importing.js        adapter · how a corpus gets in                      NEW
└── corpus.js           adapter · what is already stored                    NEW

tests/ui/
├── dom.js              CHANGED — links ES modules instead of one script
├── page.js             CHANGED — how the page is loaded, and nothing else
├── reading.js          CHANGED — the same
└── test_page.py        CHANGED — the flag, and the id sweep over the directory
```

### What each module is for

| module | tag | hides | ids it owns |
|---|---|---|---|
| `app.js` | `wiring` | the composition root: every handler, the keyboard, the first paints, and the two transitions that repaint everything — `openSample`, `forgetEverything` | the frame and the sheet buttons: `pane-sample`, `pane-review`, `open-list`, `open-dataset`, `open-import`, `open-guide`, `sheet-guide` |
| `wire.js` | `adapter` | one call and one reading of a refusal — including that FastAPI's 422 echoes the whole sample back, so the field and the message are read and the echo is not | none |
| `screen.js` | `adapter` | that the page is a DOM: `$`, `show`, `say`, `esc`, the tick boxes, and the code-point slicing the offsets need | none |
| `held.js` | `shape` | what the page holds between one sample and the next, and the two constants that say what a check and a facet are | none |
| `conversation.js` | `adapter` | what a turn, a tool call and a label look like drawn — read by the sample pane **and** by a stored row opened out of the corpus | `turns`, `catalog`, `tool-count`, `raw-sample`, `calls`, `calls-which` |
| `checks.js` | `adapter` | the two-check run, in order, and the row each one reports on | `run-detect`, `run-review`, `run-note`, `said-detect`, `said-review` |
| `models.js` | `adapter` | which models answer, and that `config/model/` is a directory a deployment edits while the service is up | `verifier-ticks`, `jury-ticks`, `sft-ticks` |
| `personal-data.js` | `adapter` | the values the reviewer keeps, the ones they add, and the copy that ships. **Not** where a value stands in the text — that is answered | `panel-data`, `keep-table`, `value-new`, `value-class`, `value-add`, `value-note`, `scan-raw`, `review-text`, `text-which`, `data-verdict`, `data-refusal` |
| `label.js` | `adapter` | which of two calls ships, and the form that writes a third — the panel's proposal, what arrived, the three acts, and the catalog-built editor | `panel-label`, `proposed-call`, `arrived-call`, `v-take`, `v-keep`, `v-write`, `call-form`, `call-add`, `call-none`, `label-fault`, `label-verdict`, `out-6`, `label-refusal` |
| `facets.js` | `adapter` | which facets a person ticks, and where a value that is not declared comes from | `facet-ticks`, `domain-ticks`, `domain-new`, `domain-add`, `domain-note`, `domain-said`, `guide-facets` |
| `record.js` | `logic` | the one thing this page composes, read back as a table, and which panel a refusal belongs to | `record`, `record-table`, `submit`, `skip`, `submit-note` |
| `queue.js` | `adapter` | which sample is on screen, how much of the corpus is left, and the rows a reviewer picked to walk | `sheet-list`, `list-walk`, `list-none`, `list-rows`, `list-note`, `sample-name` |
| `importing.js` | `adapter` | how a corpus gets in: one sample pasted, or a file of lines | `pasting`, `paste-open`, `paste-text`, `paste-now`, `paste-queue`, `paste-cancel`, `paste-note`, `sheet-import`, `file`, `drop`, `drop-said`, `import-run`, `import-note`, `import-said` |
| `corpus.js` | `adapter` | what is already stored: the dataset sheet, the statistics grid, and which database a record lands in | `sheet-dataset`, `dataset-rows`, `dataset-bad`, `dataset-one`, `dataset-more`, `dataset-note`, `stats`, `strip`, `store` |

**Every id is named exactly once in that column.** What the flow adds: `run-detect` and `run-review`
in place of `run-checks`, the value box (`value-new`, `value-class`, `value-add`), `proposed-call`,
`arrived-call`, the three verdict ticks, the form, and `record-table`. What it removes: `span-table`,
`span-check`, `span-add`, `span-note`, `auto`, `v-correct`, `v-modify`, `take-consensus`,
`consensus-line`, `consensus-note`, `label-text`, `label-check`, `label-note`, `label-editor`,
`calls`, `calls-which` — sixteen ids, because sixteen controls stopped existing. That is
Requirement 4 read as a table, and it is what the sweep extending `test_page.py` will check. The guide sheet is
the one place two modules paint into one sheet — `facets.js` writes what each facet means and
`corpus.js` writes the statistics under it — because both are already drawn elsewhere on the
screen and a second spelling would let the two disagree.

**Two seams named but not cut.** `personal-data.js` holds two decisions — which spans are real, and
what the copy is — and stays one file while the copy has no consumer but that card and the record.
`corpus.js` holds the dataset sheet and the statistics, and stays one while both read `/records`.

### The import direction

```
held.js ──────────────► nothing
   ▲
   │                    screen.js ──► nothing
   │                        ▲
   │   ┌────────────────────┘
   │   │
  the eleven adapters ──► wire.js, screen.js, held.js, conversation.js
   ▲
   │
app.js (wiring) ──────► everything · nothing imports it
```

`record.js` is the only `logic`, so it imports `held.js` and nothing else. An adapter importing
another adapter is allowed and happens twice — `conversation.js` is read by the sample pane and by
`corpus.js`, and `checks.js` calls into `personal-data.js` and `label.js` to run them.

### `style.css`, in four bands

| band | holds |
|---|---|
| **tokens** | the colour set that is already there, plus the spacing scale and the three type sizes |
| **primitives** | `button`, `input`, `select`, `textarea`, `table`, `pre` — the bare elements |
| **components** | the card, the question head, the state word, the act row, the note, the disclosure, the table, the tick list, the form field, the skeleton. **One rule per role** |
| **screens** | the header, the two panes, the action bar, the four sheets, and the narrow layout |

A component defined twice shows up as two rules in the same band, which is the whole reason the
bands are in this order.
