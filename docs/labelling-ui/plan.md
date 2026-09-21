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
- `app.js` **is 389 lines**, draws nothing, and nothing imports it.
- `corpus.js` holds the dataset sheet, the statistics grid, the strip and the store line; the seam
  between the first two is named and not cut.
- Fourteen files, and the tag census is eleven `adapter`, one `shape`, one `logic`, one `wiring`.

**Why 389 and not under 200.** The number was written before the graph was measured. The four
panels are not a tree: `personal-data` and `label` call each other, and `record` calls both. What
broke the cycle was lifting the page's reaction to a change — `copyLater`, `refreshBoth`,
`refreshCopy`, `assemble`, `submit`, `skip`, `openSample`, `forgetEverything`, `runChecks` and the
keyboard — into the only module allowed to know every panel. That is 389 lines of composition and
no drawing, and it is the price of a `ui/` with no import cycle in it.

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

**What moves, and where to look.** Thirty-one of the twenty values sit on an exact midpoint of the
scale — 6, 10, 14 and 20 are all equidistant between two tokens — so they are resolved by role and
not by arithmetic: a value inside a control rounds down, a value between two things rounds up. The
rest go to the token nearest them, and none goes to a farther one. Two type changes are worth a
look rather than a diff: everything set at 13px reads at 14px now (every table, the tick labels, a
call, and the conversation the reviewers are handed — whose own comment always said it should be
the size the prose is), and the strip reads at 12px, which is what made its narrow override
redundant.

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

**What landed instead, and why.** Three things. The six spellings are not six spellings of one
role: measured, `note` and `lead` are one role spelled twice, `verdict` and the checks table's
`said` are one role spelled twice, and `tight` is a modifier, not a name — it stays, because a
modifier is not a role. `:first-child` was tried in its place and is **not** the same rule: `tight`
marks three elements and `:first-child` marks ten, so seven headings the author left a gap above
lost it — including one whose gap came from a margin collapsing through an empty wrapper this task
had just emptied further. Where a gap goes is the author's call, not the tree's. `lab` is a fourth
thing — the name over a control — renamed `fieldname`, because on this page *label* is the tool
call being reviewed. The skeleton is **not**
defined: nothing shows one until `T17`, and a rule with no user is what this task's own last
criterion forbids. The band names the empty region instead, which is the skeleton's sibling and
does have users.

**And what the sweep found.** Four classes were written and never defined — `shown`, `editor`,
`num`, and the keep table's `value` — so the row that says a span's offsets do not slice read as
ordinary text. Two rules were defined and never used, `h3.way` and `.mono`, neither of which any
commit has ever used. And `dropped` named two different things: a stored row whose label will not
call, and a span the reviewer chose not to replace. They are split, not merged.

**What a reader sees change.** Four things, none of them wrong and none of them visible to
`make check`, which is why this phase is read in a browser. Merging `lead` into `note` takes card
1's instruction paragraph and the two in the import sheet from 14px to 12px. `p.note` now sets the
margin a `<p>` used to get from the browser, so the note under the two verdict radios sits tighter
against them and the statistics' paragraphs lose a top margin they had. The checks table's *What it
said* column is 12px, because the state word is one size everywhere. And nothing else gained a
property in the merge: `overflow-wrap: anywhere` stayed on the cell, where a refusal is a sentence
in a fixed-width column, rather than moving onto every state word — in the card head, which is a
flex row, it would let a long verdict break mid-word instead of widening the head.

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

**What landed instead, and why.** Four things.

**One route was three answers short of enough, so there are two.** The reviewer says *what kind* a
value they typed is, and the kinds have to come from the scans: a list written into the page would
offer a class no scan declares and put the rest in another order, and that order is the one
`<CLASS_N>` counts in. So `GET .../data-quality/personal-data/classes` answers
`PiiRuleDetector(list_scan_functions).classes`, the way `GET /models` answers a directory. It spends
no model and no row, which is why `page.js` counts it among the calls that may be made on load.

**The body carries no language, and the route runs two functions rather than three.** Nothing in
numbering reads a language — `find_and_number_spans` matches `\w` and `order_claims_by_class` sorts
by position — so a `language` field would have been one nothing read. `read_span_values` is not run
either: the answer is the `PersonalDataDetected` the scan gives, and what a span reads is `sliced`
on the page, which is reading a span rather than holding a rule about one.

**The rows are the claims, and the confirmation arrives as the ticking.** `claims` is what both
detectors claimed; `spans` is what the confirmation kept. So every claim is a row, and a claim the
model rejected is a row that starts unticked — something a reviewer can put back, rather than
something that silently never appeared.

**Only the ticked values are numbered, and that decides one thing at the cost of another.**
Containment is measured over what is still ticked, which is what Requirement 41 of the pipeline
spec says in words: *untick an email and the phone number inside it is what is left to hand back*.
The other way round — numbering every row, ticked or not — was written first and is wrong: untick a
street address and the name inside it that the reviewer **kept** earns no span, is not replaced, and
nothing downstream refuses the record, because `find_surviving_spans` only looks for values that
carry a confirmed span. What it cost: `<CLASS_N>` counts over the claims that are sent, so a
placeholder moves when a value before it is unticked. That is a number changing under a reviewer's
eye, against a value they keep going out un-redacted, and it is not close.

**What is handed back keeps `claims` and `reason` from the scan.** `claims` is what the *detectors*
claimed and it is what `outcome` is measured against, so a value unticked has to stay in it —
otherwise unticking turns every record from `withheld` to `redacted` and the audit signal goes.
`reason` is the confirmation's own words about a value, and the numbering route has never been told
it, so it is added back where the record is composed rather than by the page editing an answer the
service gave it.

**The scan is followed by one numbering, before anything is drawn.** So the table, the disclosure
and what is handed back are always read off one answer, rather than off the scan's narrowed spans
until the first tick and off a numbering afterwards. It costs no model and no database, which is
Requirement 30.

**What the review caught.** Five, and the worst of them is the one above about numbering the
unticked rows. The rest:

- **The staleness guard counted numberings and not samples.** `forgetEverything` bumps `copyAt` so
  a redaction cannot land on the sample after the one it was made for; the numbering had no such
  bump, so skipping a sample — or changing the language mid-scan — put the previous sample's
  `review_text` and spans into the next sample's record, stamped `redacted`, with nothing
  downstream able to catch it. `forgetPersonalData` bumps the counter now.
- **The claim was committed to the page before it was numbered.** A numbering that refused left a
  row nothing could place and a shipping copy nobody invalidated. The proposed maps are passed in
  and committed only on success, so the page never holds a claim it has not been given spans for.
- **`Object.fromEntries` put the map back into a plain object at the wire**, and a plain object
  sorts integer-like keys first. The order is not decoration: within a class the numbering sorts by
  first appearance and the sort is stable, so two values starting at one offset — a value and a
  prefix of it — are ordered by the order they arrived in, and `<OTP_1>` and `<OTP_2>` swap. The
  body carries an ordered list of `(class, value)`, the shape `claims` already comes back in.
- **One cell said *not in the text* for three different situations.** A value the reviewer left in
  the text now says so; a ticked value every occurrence of which is inside a longer span says that;
  and only a value the text does not hold is called missing.
- **The card was repainted in time `rows × spans × text`.** Every cell re-split the whole review
  text to read one span, on every tick. The text is split once per answer and the occurrences
  counted once per paint.
- **A row the page does not hold now changes nothing.** The table keys a row by its value, and a
  value is escaped into a `data-` attribute and read back out of it; a value carrying a carriage
  return does not survive that, and setting a key nothing matched would have added a second row
  rather than changing one.
- **The classes were asked for once and never again.** A page opened while the service was
  restarting could not add a value for the rest of the shift. `detect` asks again where it has
  none, which is where a reviewer is about to need them.
- **Two checks proved less than they read as.** *Changing a value's class renumbers* was asserted
  at the request and never at what the page drew, so a page that sent the right body and drew the
  stale placeholder passed; and the placeholder round trip it replaced had stopped meaning
  anything once nothing went out through a field and came back. `dom.js` also gave every element
  it minted a `<select>`'s reading of its own markup; it knows the tags `index.html` declares now.

**One seam that looked like a choice, and one limit that is real.** Both new functions took a
`list_scan_functions` defaulting to `SCANS`, and no caller could ever pass one: a scan is a Python
callable and these answer a `GET` with no body and a `POST` carrying a record. The parameters are
gone. What is left is the limit under them, stated in `list_personal_data_classes`: a deployment
that hands its checker a scan set of its own has given the scan a class these do not know about, so
the picker will not offer it while the rows the scan claimed show it, and `order_claims_by_class`
files it after the declared ones — which moves a span's `id` without moving its placeholder.
Changing `SCANS` is what keeps every route agreeing. Making `SCANS` itself the configured thing is
the fix when a deployment needs one, and nothing outside the suite does yet.

**One thing left standing, and it is the redaction route's rather than this task's.** The count in
a row is how many occurrences were *numbered*; `replace_text` replaces every substring occurrence
with no word-boundary rule and no containment rule, so a value that is also a fragment of a longer
number is replaced more often than the row says. That is what `redact` has always done and nothing
here changes it.

**What a reader sees change, and `make check` cannot.** Card 1's table is four columns — keep, what
it is, the value, how many times it occurs — where it was six of offsets. Under it is one field and
a picker, where *Re-read the rows* and *Add a span* were. The disclosure is read-only and says what
each span stands in for. A value the verifier rejected is now on the table, unticked, where it used
to be invisible. And the scan's row on the Checks panel counts **values** rather than spans, which
is the same number more often than not and a different one exactly when it matters.

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

**What landed.** `consensus_calls` on `ReviewerVerdicts`, as a `@computed_field` reading
`llm.consensus` rather than a field the route fills. The plan said *one field*; what it did not say
is whether that field is **stored or derived**, and stored is the version that can go wrong: two
places holding one sentence's meaning drift the moment anything constructs the model by hand, and
nothing would say which of the two was right. Derived, the invalid state has no spelling.

The leniency is `parse_text_to_tools`'s own and is not re-stated here: prose comes back as no calls
with `consensus` untouched beside it, which is the case the second test drives with a juror writing
*Chưa đủ thông tin để gọi tool nào.* Both tests were proved red — once by answering `()`
unconditionally, once by answering the unparsed text as a named call.

**What a reader sees change.** Nothing yet. `T21` is what draws it.

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

**What landed.** Two buttons, `run-detect` at the head of card 1 and `run-review` at its foot,
each with the pickers it spends. `RUNS` and the `for (const { step } of CHECKS)` loop are gone —
there is no longer a run that has an order — and with them `checks-verdict` and `checks-note`, which
were a head word and a commentary about a single run. The checks panel is now two verdict words and
the Model column is off it, which is what `T14` said it would inherit.

**One sentence that turned out to be false already.** `index.html` said *the shipping copy cannot be
shown earlier, because the label is part of this text: a copy made before the label is settled is a
copy of a label about to change.* Measured: `refreshCopy` has run on every tick since `T12` — the
copy was always being **made**, it was only being **withheld from the screen**, and the gate was
`held.settled`, which is a fact about card 2. So the reviewer approved the spans, the page redacted
the record, and then showed them the unredacted text. `paintReviewText` now shows the replaced copy
from the moment there is one, and the label above it says which copy: *the conversation the
reviewers will be handed* before the label is settled, *the text as it ships* after. **The
unreplaced text is never drawn into that block at any point** — the raw sample is the left pane's
job, and it is never redrawn.

**What disables the second act, in the order a reviewer meets it**: no sample · no scan · the copy
refused, in the service's own sentence · the copy still being made. That last one is what makes the
gate correct rather than decorative — `copyLater` nulls `held.shipped` the instant a tick lands, so
there is no window in which *Ask the reviewers* is live over a record that does not match the table
above it. `app.js` decides all four, because `layout.md` § *The import direction* says it is the only
module allowed to know both cards.

**What a reader sees change.** *Find personal data* fills the table under it. The redacted
conversation is on the screen with `<NAME_1>`, `<PHONE_1>`, `<EMAIL_1>` in it **before** anything is
confirmed, and *Ask the reviewers* sits under that text with the jury beside it. Checked in a
browser at 1440×900 and 390×844: no console errors, and the juror's body carries the placeholder.

**Three defects were re-injected and each turned its check red**: sending `held.sample` instead of
`held.shipped.sample`; gating the redacted text on `held.settled` again; and never disabling
`run-review`.

**What the review caught.** The sentence above about there being no window was wrong when it was
written, and two of the three findings are why.

- **A value typed in went to the jurors in the clear.** `valuesChanged` called `copyLater()` only
  *after* the renumber came back, while the tick path called it *before*. So for the whole round
  trip of `POST …/spans` the copy on screen was the one made before the reviewer said the value was
  personal data, and **Ask the reviewers** stayed live over it. Reclassing had the same window, at
  lower cost — the value is already replaced there, under the class the old count numbered. Fixed
  with a counter of renumbers in flight, not by nulling `held.shipped`: nulling would leave the
  button dead with a false note when a renumber *fails*, and `numbered` commits nothing on failure,
  so the copy that is already there is still the right one.
- **`outcome: "withheld"` was never read, and reading it would have been wrong.** The reviewer
  proposed gating on it; measured, that stops the ordinary path — `handedBack()` sends
  `held.scanned.claims`, all of them, while only ticked values earn spans, so **any untick answers
  `withheld`**, which is a value left in the text on purpose. Their narrower form is the one that
  holds and is what landed: every value still ticked must be absent from the copy.
- **The reviewer's own trigger for it did not reproduce.** Their stub answered `withheld` with the
  raw number intact; the real service does not do that for their input. Two kept values overlapping
  *in part* — `"Tran Van"` and `"Van Minh"` — answer `withheld` with neither value whole:
  `user: anh <NAME_1> Minh goi nhe`, a fragment. What does reproduce is a kept value that is not a
  contiguous substring of any *field*: `build_review_text` joins turns with `\n`, so a value
  crossing that join stands in the text and in no field, and replacement by value can never place
  it. Measured — claimed `"0912345678\nassistant"`, outcome `withheld`, copy
  `user: so 0912345678\nassistant: vang a`, the number in the clear. `POST /records` already
  refuses to *store* such a record; what was unguarded was the model call in front of it.
- **The handler is guarded by the same sentence as the button**, because a disabled button is a
  browser's courtesy and not the page's rule.
- **One check caught an unfaithful fixture on its first run**, which is the best evidence it works:
  the stub replaced the phone and not the value the test had just added, so the copy still held it
  and the gate refused — correctly. The fixture was the thing that was wrong.

**And the round after that, which was about the checks rather than the code.** The reviewer copied
`ui/` aside, deleted `paintActs()` from `copyLater` and ran the suite against the copy: **all
green**. Every `run-review` assertion written up to that point sat on a path where the button had
**never been enabled** — before a scan, after a refused scan, after a refused copy — so the
`disabled` in the markup satisfied all of them, and a page that never took the button back would
have passed. The transition is now driven on the one path where `copyLater` is the sole
invalidator: settling the label. Two things were fixed with it.

- **A dead button said it was ready.** The state came from `off || why` and the note from `why`
  alone, so for the whole of an in-flight `/ai-review` — the longest wait on the page — the button
  was dead under *they read the text above*. One reason string now, empty meaning askable, with
  `busy` and no-sample inside it, so the two cannot drift. And `paintActs` is among the first
  paints, so the note is not blank until `/queue/next` answers.
- **The two acts followed opposite rules.** `run-review`'s disabled was written by its owner and
  `run-detect`'s directly from `app.js`. One `acts()` in `checks.js` writes both. The `skip` and
  `submit` mismatch is older than this task and belongs to `T14`.

`docs/tool-decision-store/spec.md` Requirement 36 is rewritten in the same commit: two columns, and
the reason the middle one existed is kept and strengthened — the row a picker sat on was standing
in for a button that was somewhere else entirely.

**And a third round, which was prose the move left behind.** One check's sentence was the negation
of its own assertion — *the panel cannot be asked until there is a redacted record* over
`disabled === false` — so a green line told a reader the reverse of what it proved. A test's name,
its docstring and its body disagreed three ways about how many columns the checks table has. The
review-text block called itself two versions of a text it draws one of. Three `.checks` rules styled
pickers that had left the table.

**One thing was measured and kept rather than fixed.** Deleting `.checks .tickbox` and the two
`.checks .fieldname` rules took away spacing the pickers had; at the foot of the card they fall
through to the generic `.tickbox`. Measured in a browser with the old spacing re-added as
`.askline`-scoped rules: 177px against 161px at 1440, 237px against 213px at 390 — a tenth of the
block. Kept loose, and for a reason: those rules were tight because the pickers were in a table cell
34% wide, and re-adding them here would put one-off spacing back into the file `T13` exists to take
it out of.

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

**What landed.** `proposed-call` and `arrived-call`, drawn by one `drawLabel` in
`conversation.js` so the two cannot disagree about what a call looks like, and three radios where
two plus a button were. The proposal comes from **`consensus_calls`** and never from `consensus`:
that is the field `T19` exists for, and `test_page.py` asserts the page never reaches for
`consensus` itself.

**What `Take the reviewers' answer` stores, and why it is the parsed form.** `consensus_calls` is
what the service read out of the juror's sentence — `{"type": "function", "function": {"name": …,
"arguments": "<json text>"}}` — while a label that arrives usually reads `{"name": …, "arguments":
{…}}`. Storing the parsed one puts two spellings in the label column, so it was worth checking
whether the repository minds: it does not, in writing. `read_call_arguments` says *whether it wrote
its arguments as an object or as JSON text*, and `parse_text_to_tools` says *a corpus writing the
object and a provider writing the text wrote one call*. Measured as well as read —
`check_label_calls` answers `schema_valid=True` for both shapes over the same catalog. The
alternative was the page re-parsing the juror's text into an array, which is a second reading of
one sentence and the thing `T19` was written to stop.

**One number that had to move.** `label_agreement` is *the share of votes that say what the label
says*, and the label it is measured against is the one that **arrived** — `reach_verdict` sets
`wanted = normalize_prediction(label)` from the sample. `layout.md` said to put it beside the
proposal's heading; there it would read as a third of the panel agreeing with the proposal, which
is not a thing the service answered. It sits beside **what arrived**, where it is true, and the
proposal's heading says how it was reached instead — *what more than half of N reviewers gave*,
which is `find_exact_match_consensus`'s own definition. It was also in the card head and beside
what arrived at once, 400px apart in identical words; the head is a state word now.

**One seam, named.** `drawLabel` reads a call's `arguments` when they arrive as JSON text, so it
can list one row per argument. That is not a second definition of what a call is — it decides no
validity, no containment and no numbering — but it is the page knowing that both spellings exist,
which the store says in `read_call_arguments`. It is drawing, and it is the only way to put an
argument on its own row.

**What a reader sees change.** Card 2 leads with `OpenTicket · kenh: app · ma_khach: <PHONE_1>` as
a table, with what arrived — `ma_khach: 0912345678`, one argument and the raw number — in the same
form underneath, so the comparison is immediate and neither is JSON. Then three named acts, none
ticked. Checked in a browser at 1440×900 and 390×844: no console errors, no page overflow.

**Five defects were re-injected and each turned its check red**: drawing the call as a name over
its arguments as JSON; never disabling the act that takes a proposal that does not exist; storing
what arrived when the reviewer took the panel's answer; seeding the editor from what arrived; and
putting the percentage back into the card head.

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

**What landed.** `call-form`, and `conversation.js` reading the catalog once for both the pane that
draws it and the form built out of it — `offeredTools()` answers each tool's name, its description,
and one entry per parameter with that parameter's own description and whether the tool requires it.
`label.js` holds the form; `held.written` holds the calls being written, as a list of
`{name, arguments}` whose every argument value is **text**, because a field on a form holds text
and a second type in there would be a shape the page has to guess at.

**Four things the form decides, and why each way.**

- **An empty field is not an argument.** What ships is the fields that were filled in, so a call
  missing one the tool requires is a call missing it — and `POST /data-quality/label` says so, in
  the sentence it already had. The alternative is shipping `""`, which validates and means nothing.
- **Changing the tool clears the arguments**, because a different tool has different parameters and
  carrying a value across would put one tool's argument under another's name.
- **A seeded call naming a tool the sample never offered is dropped**, because *the tool is picked
  from the tools that sample offers* is the requirement, and a `<select>` cannot hold a name that is
  not in it without quietly answering something else.
- **Typing in a field does not redraw the form.** Every other change does. Markup written over a
  field with the caret in it takes the caret with it, and this is the one control on the page a
  person types into character by character.

**One parse that had to go with the editor.** `T21` drew each juror's vote through a `JSON.parse`
of the sentence that juror wrote — so a juror answering in prose was drawn as **No call**, which is
a different answer from the one it gave. Requirement 24's last line is *nothing in `ui/` parses or
composes a call from free text*, and that was the last one. The votes are drawn as the sentences
they are, behind the disclosure already called *what each reviewer said*; the reading of one into
calls stays where `T19` put it, on the service. `test_page.py` now names the three modules allowed
to hold a `JSON.parse` and what each of them reads: a response body, a pasted `.jsonl` line, and a
call's own `arguments` field — which the store says is *an object or JSON text*.

**What a reader sees change.** *Write it myself* opens a block with the tool in a picker, its
description under it, and `ma_khach` and `kenh` as two fields, each with the catalog's own sentence
beneath and `required` beside the one the tool demands — seeded from the panel's answer, so the
field reads `<PHONE_1>` because the juror read `<PHONE_1>`. *Another call* adds a second block,
*Remove this call* takes one off, and *This turn needs no tool at all* is a box that ships `[]`.
Checked in a browser at 1440×900 and 390×844: no console errors, and the only page overflow at 390
is the header defect `T18` already holds.

**Nine defects were re-injected and each turned its check red**: filling the picker from something
other than the catalog; not marking the required argument; seeding the form blank instead of from
the panel; ignoring the no-tool box; keeping an empty field as an argument; not adding a second
call; not removing one; putting the juror's `JSON.parse` back; and leaving `label-text` on the page.

**One thing found and left.** `screen.js` still exports `sliced`, which nothing imports — `T25`
took the page's last reader of an offset away. It is one line in a file this task does not touch.

**Two defects the review of the finished diff measured, both this task's own.**

- **A wipe the form did not show.** `forgetEverything` dropped `held.written` without touching the
  three acts, so changing the language while *Write it myself* was open left the form on screen
  with a call in it while `[]` was what shipped. Measured by driving it: the block still read
  `Lookup(ma=0912345678)` and the redact route was posted `label: []`. `forgetVerdict` is part of
  `forgetEverything` now, and `openSample` drops its own call to it. The draft still goes on a
  language change — everything else computed under the old language does — but it goes **visibly**:
  the acts untick and the form closes, and what ships is what arrived, which is what three unticked
  acts say. It also fixes an older one the same way: an emptying queue used to leave the last
  sample's verdict ticked over a pane saying nothing was waiting.
- **An act taken with no sample threw.** *Write it myself* is live whatever is on screen, and
  `seedForm` reads `held.sample.tools` — `TypeError: Cannot read properties of null` on an empty
  queue. `tookVerdict` puts the tick back instead.

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

**What landed.** `record-table`, drawn by `record.js` beside the `show("record", …)` it already
did, and the `<pre>` moved under it into a disclosure called *the raw record*. Ten rows: the key,
the label as `OpenTicket(ma_khach=<PHONE_1>)`, every declared facet, `language`, `schema_valid`
and how much of what the scan found came out.

**Three readings the table had to get right.**

- **A facet nobody ticked still has a row.** `readDeclaredFacets` leaves a *tick one* facet out of
  the object entirely until one is ticked, so drawing the object's own keys would have left
  `domain` — a column a record is refused without — simply absent, which reads as nothing to say.
  The rows are the **declared** facets in declared order, then whatever else `class` carries.
- **The count is of values, not of spans.** `<CLASS_N>` is numbered per distinct value, so the
  distinct placeholders are the values that came out; the spans are the places they came out of.
  *3 of 3 values replaced, in 4 places* says both, and neither number stands for the other.
- **`schema_valid` is read off the check, not off the record.** The store computes that column at
  write time and the record posted carries no such key, so the row reads what
  `POST /data-quality/label` answered — the same rule, asked early. A check nobody could make
  reads *nothing could check it*, which is not the same as a label with nothing wrong.

**One import edge this adds, named.** `record.js` is the only `logic` and it now imports
`conversation.js` for `saidCall`. The alternative was a second spelling of a call — one in the file
that draws one, one in the file that composes the record — and `layout.md` § *The import direction*
says so rather than leaving it to be discovered.

**What a reader sees change.** Under the two cards, a box that is not a card: *What will be
written*, then key over label over the facets over `schema_valid` over *values replaced*, and *the
raw record* collapsed at the foot of it. Before any scan it reads *Nothing yet — the record is made
as soon as the values you kept are replaced*. Checked in a browser at 1440×900 and 390×844: no
console errors, and the only page overflow at 390 is the header defect `T18` already holds.

**Seven defects were re-injected and each turned its check red**: never drawing the table;
stringifying the label back into the row; counting spans where values were meant; never reading
what the catalog said; leaving the facets out; drawing no call as an empty cell; and leaving the
last sample's record on the table when the next one opens.

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

**One thing already broken, found while `T13` was being reviewed.** `index.html` gives that table
`class="rows"`, and `.rows` is the **sample list** — `display: flex; flex-direction: column`, which
blockifies a `<table>`. It predates this plan (`86b3d9e`) and it is one name doing two jobs, which
is what `T13` is about; it is written here rather than fixed there because the fix is read by
looking at the sheet, and this is the task that opens it. Nothing else on that table depends on the
class: every rule that styles it is `#dataset-rows`-scoped.

**Source.** `spec.md` Requirement 26; `docs/tool-decision-store/spec.md` § *The page* — *the corpus
can be read back, and only the redacted half of it*.

**Verify.** `make check`

**What landed.** The sheet opens on *Where these rows are* — one line naming the database, from the
same reading the header's pill is drawn from and **never the DSN** in either place — then one
sentence saying only the redacted half is served, then the statistics grid with its empty cells
named, then the page of rows. `#stats` moved out of the guide to get there, which also ends the one
place two modules painted into one sheet: the guide is `facets.js` alone now.

**A row opens whole, by the code the sample pane draws with.** `conversation.js` gained
`readTools` and `drawCatalog` beside `offeredTools` — the pane, the form `T22` built and a stored
row now read and draw one catalog three ways from one definition. The stored row's label moved from
`drawCalls` to `drawLabel`, so it is the same call table card 2 draws; `VerifyEmail_15d` over *no
arguments* is what a label that names a tool and never calls it looks like, and the refusal under
it says why nothing could validate it. The catalog is there because **a label is only right or
wrong against the tools it was offered**, and the row had been shown without it.

**`class="rows"` off `#dataset-rows`, and what it was hiding.** `.rows` is the sample list —
`display: flex; flex-direction: column`, which blockifies a `<table>` — so the stored rows had
never been drawn as a table at all. Taking it off turned them into one, and that uncovered a second
defect the blockification had been covering: `.sheet` is a grid whose column track was implicit,
so a track sized by an eight-column table let `.sheetbox`'s `min(760px, 100%)` resolve against the
wider track and **the whole sheet scrolled sideways on a phone**. The track is
`minmax(0, 1fr)` now and the `.tablewrap` scrolls instead, which is what it is for.

**Two things found by looking, both older than this task.** `.sheethead` was `display: flex` with
no `gap`, so the head read *Dataset3 of 3 rows*; it has one now, and `align-items: baseline` like
every other head on the page. And the store line needed air under it before the sentence about the
un-redacted half, or the two facts read as one paragraph.

**What is **not** fixed, and belongs to whoever gets there.** `GET /store` answers
`attached: true` for a database it cannot reach — `db.open_engine()` is `create_engine`, which is
lazy and connects to nothing. So both the pill and this sheet's line can name a database that is
down. Fixing it means an actual connection attempt per request, which is a behaviour change on a
route and is in none of this task's criteria.

**Five defects were re-injected and each turned its check red**: the sheet never saying which
database; a stored row's label drawn some other way; the catalog left out of an opened row; `.rows`
put back on the table; and the statistics put back under the guide.

---

### What the review of `T22`–`T24` measured, and what it cost

Five findings, every one reproduced here before it was agreed with, and every one of them this
phase's own.

- **A label that is not a list of calls took the page down.** `Sample.label` is `Any` and
  `/samples/named` answers each line as it arrived, so a corpus that stored a tool's name arrives
  carrying `"Lookup"`. `saidLabel` read it as a list — a string has a length and no `map` — so
  *Find the personal data* threw out of `composeRecord`, the record table was left reading
  *Nothing yet* while the JSON under it was filled in, and **Submit** stayed live to throw the same
  way with `posting…` on the bar and nothing said. Driven, all three. `saidLabel` asks
  `Array.isArray` now and says *not a list of calls, so nothing here can read it as one*.
- **And the message about that label named a control this phase deleted.** `drawLabel`'s non-array
  branch said *the box below says what is wrong*; the box was `label-note`, which `T22` removed and
  `test_page.py` now asserts is gone. It points at `label-fault` above it instead — which does
  fire, measured: `check_label_calls("Lookup", tools)` answers `schema_valid=False` with the
  service's own sentence.
- **The `values replaced` row divided by a number nothing keeps current.** It counted
  `personal_data.claims`, which `handedBack` fills from `held.scanned` — the raw scan's list, which
  `addValue` never touches. A value typed in by hand gave *2 of 1 value replaced* one box below a
  card saying *2 values found*. The denominator is `held.claimed.size` now, which is the same
  source card 1 counts from, so the two cannot disagree.
- **The form shipped arguments it never drew.** `writtenCalls` shipped everything in
  `one.arguments`; `drawCallForm` drew only the catalog's `parameters.properties`. So an argument
  the catalog does not declare — reachable from the arrived label and from `consensus_calls` — went
  out with nothing on the screen saying it was there, and the reviewer could neither see it nor
  take it off. Worse than it first looked: `check_label_calls` answers `schema_valid=True` over
  one, measured, so nothing else on the page was going to say it either. The form draws a field for
  every argument the call carries, and the ones the catalog does not declare are marked **not in
  the catalog**. Clearing one takes it off, the way clearing any other field does.
- **`schema_valid` was read once and never redrawn.** `refreshBoth` starts the check and the copy
  together and the copy usually wins, so the row went on saying *yes* in green while the warning
  directly above it said the label names a tool without calling it. Reproduced by making
  `/data-quality/label` slower than the redact route and flipping its answer mid-run. `record.js`
  exports `paintRecord`, and `app.js` — the module allowed to know both — wires the check's landing
  to it through one `askCatalog`.

**Five more defects were re-injected and each turned its new check red**: reading a string label as
a list; the message naming the deleted box again; counting against the scan's own claims; drawing
only the catalog's fields; and dropping the repaint after the check.

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
- ~~`docs/tool-decision-store/spec.md` § *The page*, **the checks are three columns**~~ — done in
  `T20`, which is what took the pickers off the table: it is two columns now, and the reason the
  middle one existed is kept as the reason it outgrew the table.

**Two things `T20`'s review found and left here, because both predate it.**

- **`app.js` writes `.disabled` on controls `record.js` owns.** `layout.md` § *What each module is
  for* gives `submit`, `skip` and `submit-note` to `record.js`; `app.js`'s header claims two of
  them and `actsChanged` writes all three. `T20` fixed the same shape for the two run buttons —
  `paintActs` in `checks.js` writes both — so this is the last place the rule is broken, and the
  task that deletes the checks panel is the one holding the pen.
- **Skip is live on a sample that cannot be skipped.** `skip()` returns at once when `held.key` is
  null, and a pasted sample has no key, so the button is enabled and does nothing. The old
  `frozen()` behaved identically, so this is not a regression — but *the bar says what is
  unanswered* is `T16`'s sentence and a button that answers nothing is the same defect one control
  over. Whichever of `T14` or `T16` gets there first should take it.

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

**One thing already broken, measured while `T25` was being read in a browser.** The header is
the defect, and it starts at **900px** rather than at phone width — a laptop in a split window.
`.top` is `--top` tall, which is 56px, and its content is not: the strip is a flex item that
squeezes to nothing and wraps one word per line, so it grows down through the panes under it.
Measured at 1440 / 900 / 640 / 390 with the sample on screen:

| viewport | `.top` box | what the strip needs | `#store` width |
|---|---|---|---|
| 1440 | 56px | 19px | 222px |
| 900 | 56px | **80px** | 117px |
| 640 | 56px | **270px** | 45px |
| 390 | 56px | **368px** | **18px** |

So at phone width 312px of counts is drawn over the sample pane, and `#store` — *which database a
record lands in*, the one line `spec.md` says a reviewer needs before writing four hundred rows —
is squeezed from the 220px it wants to an 18px dot with no text in it. `.topacts` also ends 2px
past the viewport, which is the page's only sideways overflow. Nothing on the page scrolls
sideways otherwise: `document.scrollWidth` is 390 at 390.

Three things to decide, and this is the task that decides them: whether the header wraps to a
second row or the strip goes behind something at narrow widths; whether `--top` stops being one
number; and where *which database* goes when the bar cannot hold it.

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
