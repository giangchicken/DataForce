# Build plan

`spec.md` says what must be true. `layout.md` says which region and which module each sentence
lands in. This schedules it.

Five phases, in this order and not another.

**The file is cut while the screen is frozen, then the screen changes on the cut file.** The reason
is the evidence: a move is proved by a suite that passes unedited, a screen change by a person
looking at it, and a commit that does both has neither proof. The 1763-line file is exactly the
condition under which nobody can tell which half broke something.

**Then the scale, then the flow, then the form.** The tokens go in before anything new is drawn,
because new markup should be drawn against them. The flow goes next, because it rewrites the whole
of card 2 and polishing a card about to be rewritten is work thrown away. What is left of the form
comes last, over a screen that has stopped changing shape.

---

## How to read this

**One task is one commit.** Each is sized for one session with no prior context: read the task,
read what its *Source* points at, do it, run its *Verify*, commit.

| Part | Answers |
|---|---|
| **Goal** | What is true once this is done |
| **Context** | Why it is not true today, and what will bite |
| **Approach** | The shape of the change — present only where the task needs one of its own |
| **Acceptance criteria** | The outcome to check. Never the steps |
| **Source** | Where in `spec.md` or `layout.md` the requirement it serves lives |
| **Verify** | A command that runs as written |
| **Out of scope** | What belongs to a different task |

| Written | Lives in |
|---|---|
| § *The screen* | a named section or a bold requirement heading in `spec.md` |
| `H-8`, `C-7`, `T-2` | a rule in `AGENTS.md` |
| `T4` | a task in this file. The number is its name, not its place in the order |
| card 1, card 2, the two acts | the regions `layout.md` § *The frame* draws |
| the two behaviour specs | `docs/tool-decision-pipeline/spec.md` § *The labelling UI* and `docs/tool-decision-store/spec.md` § *The page* |

---

## Decisions this plan takes once

Five shapes span several tasks. They are settled here so no task settles them differently.

**Every task in Phase 1 keeps the same green suite.** `tests/ui/page.js` and `tests/ui/reading.js`
are not edited once `T1` has landed. A move that needs a check rewritten is not a move — it is a
behaviour change wearing one, and the point of the whole phase is being able to tell those apart.

**Leaves first.** The extraction order is fixed by the import graph: a module is cut out only once
everything it needs already exists as a module. So each task only ever *adds* an import, and no
task rewires one it wrote earlier. `layout.md` § *The import direction* is that order read upwards.

**A module declares its ids the day it is created.** Not later, not in a sweep at the end: the list
at the top of the file is the thing that makes the split real, and a module written without one is
a module that will have reached into three panels by the time anybody checks.

**No source moves after Phase 1.** Phases 2 to 4 change the screen inside modules that already
exist. A task that finds itself wanting to move a function between files has found a Phase 1
mistake, and the fix is its own commit — with one stated exception: `T19` adds a field to a router
shape, which is the one thing in this plan that is not `ui/` at all.

**`make check` is the gate, and node is what makes the UI half of it real.** `tests/ui/test_page.py`
skips loudly where node is absent, so a run without node is a run that proved nothing about this
work. Node 22 is what the linker in `T1` is written against.

---

## Phases

| # | Phase | Done when |
|---|---|---|
| 0 | The harness can load a module | `index.html` loads `app.js` as a module, the node harness links one, and `app.js` is otherwise the same 1763 lines |
| 1 | The file is cut, and the screen does not move | Fourteen modules, every one tagged, every id owned once — and `page.js` and `reading.js` never edited after `T1` |
| 2 | One scale, and one name per role | Six spacing tokens, three type sizes, four bands in `style.css`, and one class per role |
| 3 | The spans are approved before a model is asked, and nothing on the screen is JSON | A span is a value, two acts sit where their work ends, the jurors are handed the redacted conversation, the panel's call is the proposal, the label is a form, and the record is a table |
| 4 | The screen says what kind of thing each thing is | Two cards headed by their questions and nothing else pretending to be one, a bar that says what is unanswered, and nothing that goes quiet while it waits |

---

## The tasks

| | Phase 0 |
|---|---|
| `T1` | `app.js` becomes a module, and the harness links one |

| | Phase 1 — the cut |
|---|---|
| `T2` | `wire.js` and `screen.js` — the two leaves everything needs |
| `T3` | `held.js` — seventeen bindings get one home |
| `T4` | `conversation.js` — the thing already drawn twice |
| `T5` | `models.js` and `checks.js` |
| `T6` | `personal-data.js` |
| `T7` | `label.js` and `facets.js` |
| `T8` | `record.js` — the one `logic` on the page |
| `T9` | `queue.js` and `importing.js` |
| `T10` | `corpus.js`, and `app.js` is wiring alone |
| `T11` | The documents stop saying three files |

| | Phase 2 — one scale |
|---|---|
| `T12` | One spacing scale, one type scale, four bands |
| `T13` | One name per role |

| | Phase 3 — the flow |
|---|---|
| `T25` | A span is a value, and the service is what numbers it |
| `T19` | `/ai-review` answers the consensus as calls, not as a string |
| `T20` | The spans are approved, and only then are the reviewers asked |
| `T21` | The panel's call is the proposal, and it is a table |
| `T22` | A label is written on a form, not in JSON |
| `T23` | The record is confirmed as a table |
| `T24` | The dataset sheet says what the database holds |

| | Phase 4 — the form |
|---|---|
| `T14` | Two cards, and nothing else shaped like one |
| `T15` | Each decision is headed by its question |
| `T16` | The bar says what is still unanswered |
| `T17` | Everything a person waits for says it is working |
| `T18` | The narrow layout, read again |

---

## Phase 0 · The harness can load a module

### T1 · `app.js` becomes a module, and the harness links one

**Goal.** `index.html` loads `<script type="module" src="app.js">`, `tests/ui/dom.js` links ES
modules, and `app.js` still holds every line it holds today.

**Context.** This is the one risky step and it is worth having alone. `dom.js` runs the page with
`vm.runInContext`, which takes a classic script and cannot resolve an `import`; `test_page.py` reads
`app.js` as one text, `reading.js` takes one app path on the command line, and `page.js` calls a
page function by name through `vm.runInContext`. If the linker is
wrong, it is wrong here, against a file nothing has moved yet — so a failure means *the loader*,
never *the split*. Doing it inside the first extraction would make those two indistinguishable.

**Approach.** `vm.SourceTextModule` with a linker that resolves a relative specifier against the
page's own directory and caches by resolved path, so a module imported twice is instantiated once.
The stub stays exactly what it is; it is installed on the context as globals, as now. `test_page.py`
passes `--experimental-vm-modules` to node. A module executes asynchronously, so `build()` returns
after `evaluate()` resolves rather than after `runInContext` returns — that is the one shape change
in the harness, and `settled`/`waited` already exist for it.

**Acceptance criteria.**
- `app.js` has no `import` and no `export` yet, and its line count is unchanged.
- `page.js` and `reading.js` pass with **no edit but the loader's own**: `build` is awaited, and
  the file picker is reached through its element — `page.run` reached a page function by name, and
  a module keeps its declarations, which is what a browser does too.
- `GET /ui/` still serves a page that works in a browser: the module is fetched, not blocked.
- A module that throws at import time fails the run loudly rather than passing with an empty page.

**Source.** `spec.md` § *The source*, Requirements 7 and 8.

**Verify.** `uv run pytest tests/ui -q`

**Out of scope.** Cutting anything out of `app.js`. Splitting `page.js`.

---

## Phase 1 · The file is cut, and the screen does not move

Every task below has the same three acceptance criteria on top of its own, and they are not
repeated in each:

- The module opens with one of `H-8`'s five tags and imports only what that tag allows.
- It names the ids it owns at its top, and names no other module's — `layout.md` § *What each
  module is for* is the table it is read against.
- `page.js` and `reading.js` are **not edited**, and `make check` is green.

### T2 · `wire.js` and `screen.js` — the two leaves everything needs

**Goal.** One call and one reading of a refusal live in `wire.js`; everything that touches the DOM
directly lives in `screen.js`. Both import nothing.

**Context.** `app.js`'s § *plumbing* is 66 lines holding two unrelated decisions: what a route
answers and how a refusal reads, and that the page is a DOM at all. They go first because every
other module needs one or both, and a leaf extracted first is an import every later task only adds.

**Approach.** `wire.js` takes `ask`, `call`, `sayDetail`. `screen.js` takes `$`, `show`, `say`,
`esc`, `json`, `same`, `wordFor`, `chars`, `sliced`, `tickBox`, `sayInTicks`, `readTick`.
`sayDetail` stays with `wire.js` and not with `screen.js`: what a refusal *reads as* is a fact about
what the service answered, and the 422 whose `input` echoes the whole sample back is the reason that
function exists.

**Acceptance criteria.**
- `wire.js` and `screen.js` import nothing.
- No `fetch` anywhere but `wire.js`; no `document.` anywhere but `screen.js`.

**Source.** `layout.md` § *What each module is for*.

**Verify.** `uv run pytest tests/ui -q`

### T3 · `held.js` — seventeen bindings get one home

**Goal.** What the page holds between one sample and the next is one `shape` module.

**Context.** 17 module-level mutable bindings and 116 references to `held` are the reason the file
has no interior boundary: any of the 135 declarations can reach any of them. Gathering them is what
makes every later extraction possible, and it is the task most likely to find something surprising —
a binding two sections both write is a coupling nobody has had to look at.

**Approach.** `held`, `ticked`, `checked` and the constants that say what a check and a facet are:
`CHECKS`, `DECLARED_FACETS`, `PICK_SAID`, `NO_CALL`, `TICK_LISTS`, `STATE_SAID`, `DATASET_PAGE`,
`COPY_AFTER`. The per-module bindings that are nobody else's — `copyAt`, `faultAt`, `drawn`,
`domainsDrawn`, `listed`, `stored`, `counted` — stay with the module that will own them and move
with it, in its own task. A binding that turns out to have two owners is written in the task's
report rather than silently given to one.

**Acceptance criteria.**
- `held.js` imports nothing, and holds no function that calls a route or touches the DOM.
- Every remaining module-level binding in `app.js` is named in the task's report with the module it
  is going to.

**Source.** `spec.md` Decision 7 — *the state stays one object, and stays mutable*.

**Verify.** `uv run pytest tests/ui -q`

### T4 · `conversation.js` — the thing already drawn twice

**Goal.** A turn, a tool call and a label are drawn by one module, read by the sample pane and by a
stored row opened out of the corpus.

**Context.** The comment at `app.js`'s § *the sample, rendered as itself* already says two places
draw one, and that two spellings would let them disagree with nothing to say so. This is the one
extraction where the module existed as an idea before the file did.

**Acceptance criteria.**
- `drawTurns`, `drawCalls`, `drawLabel`, `paintTurns`, `paintCatalog`, `paintCalls` are all here.
- A stored row opened from the dataset sheet draws through this module and not a second copy.

**Source.** `layout.md` § *What each module is for*.

**Verify.** `uv run pytest tests/ui -q`

### T5 · `models.js` and `checks.js`

**Goal.** Which models answer, and the two-check run that spends them, are two modules.

**Context.** They are adjacent on the screen and separate in what they hide: `models.js` hides that
`config/model/` is a directory a deployment edits while the service is up — a redraw that would
write the same list is skipped, because rewriting markup takes the focus out of a box and loses a
tick. `checks.js` hides the order the two checks run in and the row each reports on.

**Acceptance criteria.**
- `checks.js` holds `CHECKS` and the row each check reports on.
- Reticking survives a redraw of a list whose contents did not change.

**What landed instead, and why.** Two commits, not one. `checks.js` cannot hold `RUNS`: `detect`
and `review` live in the panels, the panels call `mark` on the copy path and not only at a run's
start, so the import runs panel → `checks.js` and `RUNS` in `checks.js` would close a cycle.
`RUNS` and `runChecks` sit in `app.js`, which is the only module allowed to know both panels. The
step numbers stay named in the panels with it; binding a reporter per check would be machinery
around a mechanism `T14` and `T20` delete.

**Source.** `layout.md` § *The two acts, and where each one sits*.

**Verify.** `uv run pytest tests/ui -q`

### T6 · `personal-data.js`

**Goal.** Card 1 is one module: the spans as the reviewer edits them, which they keep, and the copy
that ships.

**Context.** The biggest of the fourteen at ~300 lines, and the two decisions inside it — which
spans are real, and what the copy is — stay one file (`C-7`, `T-2`): the copy has no consumer but
this card and the record. The seam is named in `layout.md` so the next person does not have to
rediscover it.

**Acceptance criteria.**
- The debounce, the newest-answer-wins counter and the *copy could not be made* path are all here.
- Nothing outside this module reads `held.detected` or `held.rows`.

**Source.** `spec.md` § *The modules* — *two seams named but not cut*.

**Verify.** `uv run pytest tests/ui -q`

### T7 · `label.js` and `facets.js`

**Goal.** Card 2's two halves are two modules: what the label is, and what kind of sample it is.

**Context.** They share a panel and nothing else. The facets are ticked while the reviewer is
already looking at the label (store spec § *The page*), which is a fact about the screen, not about
the source — and `facets.js` also paints the guide's list of what each facet means, from the same
declaration, so the panel and the guide cannot disagree.

**Acceptance criteria.**
- `DECLARED_FACETS` is read from `held.js` by `facets.js` and by nothing else.
- The guide's facet list and the tick list come from that one declaration.

**Source.** `layout.md` § *Card 2*.

**Verify.** `uv run pytest tests/ui -q`

### T8 · `record.js` — the one `logic` on the page

**Goal.** The record this page composes, the post, the skip, and which panel a refusal belongs to.

**Context.** Pipeline Requirement 46 says the page computes no answer of its own; the record is the
one exception that spec already names. Tagging this module `logic` and every other one `adapter` is
what turns that requirement into something a reader can check by looking at the top of fourteen
files.

**Acceptance criteria.**
- `record.js` is the only file under `ui/` tagged `logic`.
- It imports `held.js` and nothing else that is not `screen.js` or `wire.js`.

**Source.** `spec.md` Requirement 3.

**Verify.** `uv run pytest tests/ui -q`

### T9 · `queue.js` and `importing.js`

**Goal.** Which sample is on screen and which rows are being walked is one module; how a corpus gets
in is another.

**Context.** They were one section in flow order and they are two decisions: the queue hides the
walk — a picked row the queue no longer holds is said rather than skipped in silence — and importing
hides that a paste and a file become the same rows, and that pasting is the one path that works with
the store turned off.

**Acceptance criteria.**
- The paste box lives with `importing.js` though it is drawn in the sample pane, because where a box
  *is* on the screen is the store spec's requirement and not a claim about which module owns it.
- A queue with nothing waiting opens the paste box, as now.

**Source.** `layout.md` § *The left pane* and § *The four sheets*.

**Verify.** `uv run pytest tests/ui -q`

### T10 · `corpus.js`, and `app.js` is wiring alone

**Goal.** The last extraction, and `app.js` holds only the composition root.

**Context.** What is left in `app.js` after this is every handler, the keyboard, the first paints
and the two transitions that repaint the whole screen. That is `wiring` by `H-8`'s definition, and
nothing imports it.

**Acceptance criteria.**
- `app.js` is under 200 lines, draws nothing, and nothing imports it.
- `corpus.js` holds the dataset sheet, the statistics grid and the store line; the seam between the
  first two is named and not cut.
- Fourteen files, and the tag census is eleven `adapter`, one `shape`, one `logic`, one `wiring`.

**Source.** `spec.md` Requirements 1–5.

**Verify.** `make check`

### T11 · The documents stop saying three files

**Goal.** Nothing in `docs/` describes a `ui/` that no longer exists.

**Context.** A document that disagrees with the tree is a stale document. These are the passages the
cut makes untrue, and they are rewritten rather than appended to.

**Acceptance criteria.**
- `docs/tool-decision-pipeline/spec.md` Requirement 45 says the file count the tree has, and still
  says no build step, no npm, nothing from a CDN.
- Its Decision 15 keeps its conclusion and loses the half-reason that expired — the page is not a
  skeleton meant to be deleted.
- Its Design § *The labelling UI* no longer reasons from three files.
- Its file table lists what `layout.md` § *The tree* lists.
- `README.md` is checked for the same claim — it names the UI by its URL today, not by its
  files, so it may need nothing.

**Source.** `spec.md` § *What this rewrites*.

**Verify.** `grep -rn "three files\|Three files" docs/ README.md`

---

## Phase 2 · One scale, and one name per role

Nothing from here on moves a function between files. Every task below changes `style.css`,
`index.html` and the module that paints the region — and, unlike Phase 1, each one **is** expected
to edit checks in `page.js`, one requirement at a time, deliberately.

### T12 · One spacing scale, one type scale, four bands

**Goal.** `style.css` is tokens, primitives, components, screens — in that order — and every
padding, margin and gap in it is one of six values.

**Context.** 20 distinct spacing values and 5 font sizes today, one of them `12.5px`. There is no
scale; there are twenty numbers, each chosen next to the thing it spaces. The four bands are what
makes the next task possible: a component defined twice shows up as two rules in one band.

**Approach.** `--space-1` … `--space-6` = 4 / 8 / 12 / 16 / 24 / 32, and three type sizes beside the
colour tokens already in `:root`. Each of the twenty values snaps to the nearest token. That *is* a
visual change — a few things move by one or two pixels — and it is why this task is first in the
phase and looked at in a browser rather than asserted in a test.

**Acceptance criteria.**
- No raw pixel value in a `padding`, `margin` or `gap` anywhere in `style.css`.
- Three font sizes, and `12.5px` is not one of them.
- The four bands are in order, each with a banner naming it.
- The page is opened at `/ui/` and read at desktop and phone width before this is committed.

**Source.** `spec.md` Requirement 13; `layout.md` § *`style.css`, in four bands*.

**Verify.** `make check`, then `uv run uvicorn dataforce.edge.main:app --port 8000` and read
<http://localhost:8000/ui/>.

### T13 · One name per role

**Goal.** The six spellings of *a small line of secondary text* become one, and the component band
holds one rule per role.

**Context.** `note` ×12, `lab` ×4, `lab tight` ×3, `lead` ×3, `verdict` ×3, `said` ×2 — six names,
six sets of rules, and nothing that says which to reach for. Law of Similarity fails in the place it
is cheapest to fix.

**Acceptance criteria.**
- The component band names: a card, a question head, a state word, an act row, a note, a
  disclosure, a table, a tick list, a form field, a skeleton. One rule each.
- Every class `index.html` uses is defined in the components or screens band, and none in both.
- The markup changes with it; no class is left defined and unused.

**Source.** `spec.md` Requirement 14.

**Verify.** `make check`

---

## Phase 3 · The spans are approved before a model is asked

The only phase that changes what the service is asked and in what order. One route gains one field;
everything else is the page. Each task states what it rewrites in
`docs/tool-decision-store/spec.md` § *The page*, because these are that document's sentences.

### T25 · A span is a value, and the service is what numbers it

**Goal.** A reviewer keeps or drops a **value**, or types one the scan missed, and every occurrence
of it is found and numbered by the service. No offset is typed anywhere on this page.

**Context.** The containment rule is written twice today — `find_and_number_spans` drops a span
inside a longer one, and `app.js`'s `inside` is that same predicate in JavaScript, character for
character. `docs/tool-decision-pipeline/spec.md` already names the duplication and says why it was
paid: *the cost of a reviewer being able to edit an offset at all*. Take the editable offset away
and the copy goes with it. Everything needed is already written: `order_claims_by_class` takes a
plain `{value: class}` map, `find_and_number_spans` finds **every** occurrence of each value,
numbers `<CLASS_N>` once per distinct value, skips an occurrence with a word character against it,
and drops the nested ones.

**Approach.** One route that renumbers claims — the record, the language, and the `{value: class}`
map as the reviewer left it — answering the same `PersonalDataDetected` the scan does. It runs the
two pure functions and `read_span_values`, opens no model and no database, so it is cheap enough to
run on every tick. The page sends the map; it computes nothing.

**Acceptance criteria.**
- A value typed once is replaced at every occurrence, and the row says how many there are.
- A value the reviewer adds is numbered by the same rule as one the scan claimed — including the
  word-character rule and the nested-span rule.
- Changing a value's class renumbers, because `<CLASS_N>` counts per class.
- `span-table`, *Re-read the rows*, *Add a span* and the **`auto`** tick box are gone, and so is
  `inside` — **`grep -c "other.end - other.start" src/dataforce/ui/` is 0**.
- The read-only disclosure that replaces them shows each occurrence and what it stands in for.
- No model call, and no database, on the renumbering path.
- `docs/tool-decision-pipeline/spec.md` Requirement 41 and its § *Invariants* note that one rule
  lives in three places are rewritten to two, with the page holding neither.

**Source.** `spec.md` § *The spans*, Requirements 27 to 30.

**Verify.** `make check`

**Out of scope.** Where the buttons sit. `T20` does that.

### T19 · `/ai-review` answers the consensus as calls, not as a string

**Goal.** What the panel agreed comes back parsed, so the page can draw it as a table without
deciding what a tool call is.

**Context.** `consensus` is the text a juror wrote. Pipeline Requirement 46 says the page computes
no answer of its own, so parsing a call in JavaScript would be a second definition of one, in
another language — and the first is `parse_text_to_tools` in `profile/tool_decision/utils.py`,
already written and already tested.

**Approach.** One field on `ReviewerVerdicts`, which is declared in the router. The router is an
`adapter` and `H-8` lets an adapter import logic, so it may know what a tool call is. It must
**not** go on `LLMReviewerVerdict`: that lives in `modalities/text2text/ai_review/`, which serves
every text2text task and may not name this one's nouns — a field called `consensus_calls` there is
the modality learning the word *tool*.

**Acceptance criteria.**
- The parsed calls come back beside `consensus`, and `consensus` itself is unchanged.
- Text that will not parse comes back as no calls, with the text still there — the same leniency
  `parse_text_to_tools` already documents, not a refusal.
- No file under `modalities/` gains the word *tool*.
- Nothing in `ui/` parses a call.

**Source.** `spec.md` § *The flow*, Requirement 23 and Decision 9.

**Verify.** `make check`

### T20 · The spans are approved, and only then are the reviewers asked

**Goal.** Two buttons. The panel is handed the **redacted** record.

**Context.** Today one button runs the scan and the vote back to back, so the jurors read the
customer's real address and the placeholder in the stored argument is this service's substitution
rather than the model's reading. `ReviewRequest` extends `Sample`, so the body the page already
holds after `/data-quality/personal-data/redact` is a valid `/ai-review` body — the change is the
order and the button, not the route.

**Acceptance criteria.**
- *Find personal data* sits at the **head of card 1**, because it is what fills it. *Ask the
  reviewers* sits at the **foot of card 1**, directly above the card it fills, so a reviewer who
  has just finished ticking does not scroll back to a band at the top of the pane.
- Each model picker is beside the button that spends it.
- *Ask the reviewers* is **disabled until the scan has run and the values are settled**, and says
  why while it is.
- The body sent to `/ai-review` is the redacted record, and a juror's answer carries the
  placeholder in the argument.
- Neither runs on load. One that fails names itself, as now.
- Card 1's text block says it is *the conversation the reviewers will be handed* once the spans are
  approved.
- `docs/tool-decision-store/spec.md` § *The page*, **one button runs both checks**, is rewritten:
  it becomes two, for the reason that sentence itself gives.

**Source.** `spec.md` Requirements 20 and 21.

**Verify.** `make check`

**Out of scope.** Drawing the answer. `T21` does that.

### T21 · The panel's call is the proposal, and it is a table

**Goal.** Card 2 leads with what the reviewers propose, drawn as a call; what arrived sits beside
it; and the reviewer has three named acts.

**Context.** The panel's answer is behind a button called *Rewrite it as the reviewers did* today,
while the label that arrived — often a bare name with no arguments at all — is what the card leads
with. The thing worth confirming is the prediction, and taking it should be one click.

**Acceptance criteria.**
- The proposal is a table: the tool, then one row per argument, with how much of the panel agreed
  beside the heading.
- What arrived is drawn the same way, so the two compare without either being read as JSON.
- Three acts — take the reviewers' answer, keep what arrived, write it myself — and **none is
  ticked to begin with**.
- Each juror's own answer and its `reason` are one row each behind a disclosure; the raw JSON is
  under that, not instead of it.
- `docs/tool-decision-store/spec.md` § *The page*, **saying *correct* or *modify* is an act**, is
  rewritten to three acts, keeping its reason.

**Source.** `spec.md` Requirement 22.

**Verify.** `make check`

### T22 · A label is written on a form, not in JSON

**Goal.** *Write it myself* opens a form built from the sample's own catalog.

**Context.** The editor is a `<textarea>` of JSON with a button that says *Check it is JSON*. A
reviewer who does not write software cannot use it, and the one who can still has to retype a call
the panel already spelled out. Everything the form needs is on the page already: `tools` carries
each tool's `parameters.properties`, its `description` and its `required`.

**Acceptance criteria.**
- The tool is picked from the tools that sample offers; nothing else can be picked.
- Each argument is a field labelled by the catalog's own description, with the required ones marked.
- *This turn needs no tool at all* is a box, not something achieved by clearing a text area — **no
  call is an answer**, which the guide already says.
- A label with two calls can be written, and a call can be removed.
- The warning from `POST /data-quality/label` is unchanged: it warns, it does not block.
- Nothing in `ui/` parses or composes a call from free text.

**Source.** `spec.md` Requirement 24.

**Verify.** `make check`

### T23 · The record is confirmed as a table

**Goal.** What will be written is read back in words before it is written.

**Context.** It is a `<pre>` of JSON behind a disclosure today. It is already remade whenever
anything changes and already shown before the post — both of those stay; what goes is the JSON.

**Acceptance criteria.**
- One row per key that lands in a row: the name, the call as the catalog writes it, each facet,
  `schema_valid`, and how many of the found spans are replaced.
- The raw JSON stays under it, collapsed.
- It is still remade whenever anything above it changes, and still shown before the post.

**Source.** `spec.md` Requirement 25.

**Verify.** `make check`

### T24 · The dataset sheet says what the database holds

**Goal.** One button opens what is stored: which database, the counts, the empty cells, and the
rows.

**Context.** The sheet exists and answers `GET /records`; the statistics and the store line are
drawn elsewhere on the screen. Gathering them is what makes the button worth pressing — and the
limit is a requirement, not an omission: **there is no route to `tool_decision_record`**, because
that table keeps what arrived un-redacted and serving it would put a customer's address on the
screen of anyone who can open the page.

**Acceptance criteria.**
- The sheet opens on which database is attached, the counts, and the statistics grid with its empty
  cells named, above the page of rows.
- A row opens whole, drawn by the same code the sample pane uses.
- Nothing on this screen asks for `tool_decision_record`, and the sheet says in one line that the
  un-redacted half is not served.

**Source.** `spec.md` Requirement 26; `docs/tool-decision-store/spec.md` § *The page* — *the corpus
can be read back, and only the redacted half of it*.

**Verify.** `make check`

---

## Phase 4 · The screen says what kind of thing each thing is

What is left of the form, over a screen whose shape has stopped moving.

### T14 · Two cards, and nothing else shaped like one

**Goal.** The review pane holds two cards and no third thing wearing a card's form.

**Context.** Three `<article class="panel">` today, and one of them held no decision at all. `T20`
already moved its two acts into card 1 and `T25` took its table away, so what is left of the checks
panel is a verdict word per check — which belongs in the head of the card that check filled. A
reviewer's eye should find two questions on this pane. *(Hick's Law; Law of Similarity read in
reverse — things that are not alike must not look alike.)*

**Acceptance criteria.**
- Two cards in the review pane, and the checks panel is gone rather than restyled.
- What each check said is the state word in the head of the card it filled, said once.
- `docs/tool-decision-store/spec.md` § *The page*, **the checks are three columns**, is rewritten:
  the table goes and its reason is kept — a picker travels with the button that spends it.

**Source.** `spec.md` Requirements 9 and 11.

**Verify.** `make check`, then read <http://localhost:8000/ui/>.

### T15 · Each decision is headed by its question

**Goal.** "Which of these are personal data?" and "Which call should this be?" head the two cards.

**Context.** `1 The data` and `2 The label` are nouns, and a reviewer has to work out what is wanted
from them. The step numbers stay: they are the order the cards are worked in and the guide names
them. The questions themselves are the one thing in this plan a reviewer will argue with, and
changing one later costs a line.

**Acceptance criteria.**
- Both card heads are questions, with their number kept.
- The guide still names the same two steps by the same numbers.
- Each card shows its own unanswered state in its head, in a word and not only a colour.

**Source.** `spec.md` Requirements 10 and 15; `spec.md` § *Open*.

**Verify.** `make check`

### T16 · The bar says what is still unanswered

**Goal.** One line in the action bar, counting both cards, live: what is left before this sample can
be submitted.

**Context.** Today the same fact is a refusal that lands after submit is pressed — the scan was
never run, the label has no verdict, a declared facet has nothing ticked. Said early it changes what
the reviewer does next; said late it reports what went wrong. Both stay: this is not the refusal
moving, and the refusal keeps landing on the panel that owns it, in the service's own words.

**Acceptance criteria.**
- The line updates as the two cards are answered, and is empty when nothing is outstanding.
- It is a line of text, not a third act: the bar still holds exactly Skip and Submit.
- Submitting with something outstanding still refuses on the owning panel, unchanged.
- `docs/tool-decision-store/spec.md` § *The page*, **the action bar holds exactly two acts**, gains
  the line and keeps the two acts.

**Source.** `spec.md` Requirement 12.

**Verify.** `make check`

### T17 · Everything a person waits for says it is working

**Goal.** No region of this page goes quiet while a call is in flight.

**Context.** One string on the strip does this today. The queue's next sample, the samples list, a
page of the dataset, the statistics and the copy that ships are all calls a person waits on with
nothing on screen to say so. `T-3` applies: this is not a spinner for its own sake, it is the
Doherty threshold for five named waits.

**Acceptance criteria.**
- A table about to fill shows skeleton rows; a region about to be replaced does not go blank.
- The run button keeps naming the check it is on, as now.
- A call that refuses replaces the skeleton with the refusal, never leaves it turning.

**Source.** `spec.md` Requirement 16.

**Verify.** `make check`

### T18 · The narrow layout, read again

**Goal.** The screen still works at phone width after everything above.

**Context.** The panes stack with the sample first — already true, and written against a screen
that has since changed shape twice. The three columns of tick boxes that did not fit a phone no
longer exist as a row; each picker now sits beside its own button inside a card. What is left to
check is whether anything else overflows, which is decided by looking rather than here.

**Acceptance criteria.**
- Nothing overflows sideways at 400px.
- The sample is the first thing, the action bar stays fixed.
- Each model picker wraps under its own button and stays with it — there is no longer a row of
  three tick columns to fit, which is what `layout.md` § *Narrow* used to be about.

**Source.** `spec.md` § *Open*; `layout.md` § *Narrow*.

**Verify.** `make check`, then read <http://localhost:8000/ui/> at phone width.

---

## Not scheduled — what is earned later

These are in `spec.md` § *What else to add*, and they are deliberately not tasks. A check is earned
by a rule that has been broken *here*, and none of these has been. Writing them now would put
machinery around a shape nobody has used yet, which costs five times as much to reverse as the shape
does.

- **The `ui/` direction check.** A regex sweep over tags and `import` lines, holding Requirement 2
  without a JavaScript parser. Write it the first time an import goes the wrong way.
- **The id-ownership sweep.** Extending what `test_page.py` already runs, to hold Requirement 4.
  Write it the first time two modules claim one id.
- **The raw-pixel sweep** holding Requirement 13. Write it the first time a `13px` comes back.
- **Splitting `page.js`.** 1015 lines mirroring a file that no longer exists in that shape. Worth
  doing; not worth doing in the same weeks as the thing it checks.
- **`AGENTS_UI.md`.** The WordPress, Gutenberg and Tailwind names come out before it is cited as a
  repository rule. Its own change, and not this one.
