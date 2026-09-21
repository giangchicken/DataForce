# One module a decision, one panel a question

## What

Three things about the labelling UI, in one document because the first pays for the other two.

- **Where its source lives** — which file a thing goes in, what each file may import, and what owns
  which piece of markup. `app.js` is 1763 lines in one scope today.
- **What the screen looks like** — what form a thing on it takes, told by what kind of thing it is:
  work the machine did, a question the reviewer answers, something they may inspect. All three wear
  the same card today.
- **What order the work happens in, and what a person is shown it as** — the spans are approved and
  the record redacted **before** a model is asked, so a juror reads `<EMAIL_1>` and writes
  `<EMAIL_1>`; what it answers is the proposal the reviewer confirms; and nothing a reviewer reads
  or types on this screen is JSON.

**What is still not this document's.** Which routes exist, what each one computes, and what is
stored: `docs/tool-decision-pipeline/spec.md` § *The labelling UI* and
`docs/tool-decision-store/spec.md` § *The page*. The third thing above does reach into the second of
those — the order the checks run in and what the reviewer is asked to confirm are its sentences, and
the ones this changes are listed under § *What this rewrites* rather than left to disagree.

The order matters and is a requirement, not a preference: **the source moves first with the screen
frozen, then the screen changes on the moved source.** A commit that does both proves neither.

## Context

What the repository already is. The source is what Phase 1 left; the measurement that started this
was taken at `7694033` on 2026-09-20 and is what the numbers in brackets are.

### The source

- `ui/` is fourteen files: `index.html`, `style.css`, and twelve ES modules `app.js` loads. `app.js`
  is 389 lines of composition and draws nothing *(it was one file of 1763)*.
- The tag census is eleven `adapter`, one `shape` (`held.js`), one `logic` (`record.js`) and one
  `wiring` (`app.js`), and nothing imports `app.js` *(135 top-level declarations and 17
  module-level mutable bindings sat in one scope; `held` alone is read or written in 116 places)*.

**The premise, checked.** `app.js` has 5 commits out of the repository's 248, so it is not a file
that changes often — the claim that editing it keeps breaking something is not visible as churn.
What the history shows is *how* it changes: the most recent commit is **+1067 / −374**, two thirds
of the file moved at once, and the four before it are +84/−3, +49/−10, +4/−4 and the +638/−0 that
first wrote it. The cost is not frequency. It is that a change has nowhere inside the file to stop:
one scope, one set of names, and 17 mutable bindings any of the 135 declarations can reach, so
every edit is an edit to the whole of it and the only thing that says otherwise is a test suite in
a stubbed DOM. That is the real form of what was asked about, and it is what a boundary fixes.

**The coupling a file split does not touch by itself.** `index.html` declares 89 ids; `app.js`
names 60 of them at **124 call sites**. That is connascence of name at degree 124, between two
files in two languages, and cutting `app.js` into fourteen files redistributes those 124 literals
without removing one (`C-1`: the farther apart, the weaker the form has to be). A layout that does
not say which module owns which ids is one in which fourteen files can each reach into every panel
— the split would read as done and buy nothing.

### The screen

- The right pane carries **11 controls and 3 panels** visible at once, before a sheet is open.
- `style.css` is **six spacing tokens** — 4 / 8 / 12 / 16 / 24 / 32 — and **three type sizes**, in
  four bands *(20 distinct spacing values — 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 20,
  22, 24, 26px — and five font sizes, one of them `12.5px`; no scale, twenty numbers each chosen
  next to the thing it spaces)*. That is what `AGENTS_UI.md`'s Aesthetic-Usability law is about, and
  it is measurable rather than a matter of taste.
- **One name per role**: secondary text is `note`, a state word is `verdict`, a form field's name
  is `fieldname` *(48 distinct classes. The six counted as one role — `note` ×12, `lab` ×4, `lab
  tight` ×3, `lead` ×3, `verdict` ×3, `said` ×2 — measured as two roles spelled twice each and one
  spelled with a modifier: `note` and `lead` both said secondary text, `verdict` and the checks
  table's `said` both said the state word, and `tight` said "this one comes first". Law of
  Similarity, failing)*.
- **All three panels are `<article class="panel">`.** One of them — Checks — holds no decision at
  all: it is five machine calls the reviewer cannot influence, which the store spec collapsed into
  one button for exactly that reason. It looks identical to the two panels that ask the reviewer
  something. That is the screen's central defect: the form does not say what kind of thing a thing
  is.
- **What is still unanswered is said only after the attempt.** A missing facet, an unsettled label
  and an unrun scan are refusals that land when submit is pressed (store spec, § *The page*). Before
  that, nothing on the screen counts what is left. Zeigarnik and Goal-Gradient both point at the
  same gap.
- **Four disclosures**, and they are the one thing already done right: what may be inspected is
  collapsed, what must be answered is open. The redesign generalises that rule rather than
  inventing one.

### The flow

Three findings, read off the routes rather than off the screen.

- **The jurors are already a prediction, not an opinion about a label.**
  `profile/tool_decision/ai_review.py` says so in its first paragraph: each juror is handed the
  catalog, the conversation *and nothing else — not the sample's label, because a model shown a
  label answers about the label*. What comes back under `consensus` is what the panel thinks the
  call should be, arrived at independently. The page today draws the label that **arrived** at the
  top of the card and puts the panel's answer behind a button called *Rewrite it as the reviewers
  did*. That is the wrong way round: the thing worth confirming is the prediction.
- **And the arriving labels are the weak half.** A real corpus line reads
  `"label": ["VerifyEmail_15d"]` — a tool **named** and never called, with no `email` argument at
  all, against a conversation whose last turn is a customer reading out their address. That is
  exactly the defect `docs/tool-decision-store/spec.md` names as the reason `schema_valid` exists. A
  screen that puts that at the head of the card and hides the panel's full call behind a button is
  optimised for the wrong one of the two.
- **Redacting before the vote costs no route change.** `ReviewRequest` extends `Sample`, so the body
  the page already holds after `POST /data-quality/personal-data/redact` — the whole record with
  every confirmed value replaced — is a valid `POST /ai-review` body as it stands. A juror then
  reads `<EMAIL_1>` in the turn and writes `<EMAIL_1>` in the argument, because that is the only
  thing the conversation contains. Today the raw address goes to the model and the label is redacted
  after the fact, which means the model is shown the personal data, and the placeholder in the
  argument is this service's substitution rather than the model's own reading.
- **The next act is at the top and the work that unlocks it is at the bottom of a card.** A
  reviewer who has just finished ticking spans at the foot of card 1 would have to scroll back up to
  a band to press the button that uses them. Fitts's Law is the short version; the longer one is
  that a button placed away from the work it follows is a button that reads as unrelated to it.
- **The containment rule lives in one language again.** `find_and_number_spans` drops a span
  inside a longer one with `other.start <= span.start and span.end <= other.end and other.end -
  other.start > span.end - span.start`, and that predicate stood in `app.js` as `inside`, character
  for character. `docs/tool-decision-pipeline/spec.md` named it as a known cost and said why it was
  paid: *"that is the cost of a reviewer being able to edit an offset at all — a row they typed has
  to be resolved against the rows beside it, and only the page knows which rows those are."* The
  editable offset went in `T25` and the reason went with it. `T-6` is the rule: two definitions of
  one rule rot apart, and the copy is the one that will be wrong.
- **And the function that replaces it was already written.** `find_and_number_spans(text,
  [(class, value)])` finds **every** occurrence of a value, numbers `<CLASS_N>` once per distinct
  value so a value said twice stays co-referent, skips an occurrence with a word character against
  it, and drops the nested ones. That is exactly *"I noticed one it missed — here is the value"*,
  answered by the same function the detector itself runs. `order_claims_by_class` in front of it
  takes a plain `{value: class}` map, which is the whole of what a reviewer types.
  Requirement 12 of the pipeline spec already says the replacement runs **by value and not by
  offset** — so values are the vocabulary the rest of this already speaks.
- **One thing the page may not do, so one field is added.** `consensus` is a **string** — the text a
  juror wrote. Drawing it as a table means parsing a tool call out of it, and pipeline Requirement
  46 says the page computes no answer of its own: a client that parsed a call would be a second
  definition of what a call is, in another language. `profile/tool_decision/utils.py` already holds
  `parse_text_to_tools`. So the parsed calls are added to what `/ai-review` answers, on
  `ReviewerVerdicts`, which is declared in the router — an `adapter`, and the layer allowed to know
  what a tool call is. It may **not** go on `LLMReviewerVerdict`: that lives in
  `modalities/text2text/ai_review/`, which serves every text2text task and may not name this one's
  nouns.

### The reference, measured

`label-studio-develop/web` is 1822 `.ts/.tsx/.js/.jsx` files: an Nx monorepo,
`apps/{labelstudio,labelstudio-e2e,playground}` over
`libs/{ui,core,editor,datamanager,app-common,storybook,frontend-test}`, React with Vite, bun,
Tailwind and shadcn. Three things in it are worth taking and one is not.

- The *rule*: `apps/labelstudio/src/` splits into `pages/`, `components/`, `services/`,
  `providers/`, `hooks/`, `utils/` — by what a thing is to the app, with **one place declaring the
  API surface** and **one place holding shared state**, and helpers that can reach neither.
- The *co-location*: a component owns its markup, its behaviour and its styles together, so a panel
  changes in one place (`C-2`). This page already has most of it — `index.html` is a frame of
  panels and ids, and everything inside a panel is painted by the script.
- The *token layer*: `design-tokens.json` and one Tailwind config, so spacing and type are chosen
  once and used everywhere. That is the answer to the twenty spacing values, and it needed neither
  Tailwind nor a build — CSS custom properties do it, and the token block that held only the colours
  now carries the scale beside them.
- The *machinery*: 1822 files of infrastructure, a framework, a lockfile and a build. That is what
  `T-3` is about, and it does not transfer to a 2678-line page by scale alone.

**Decision 15, re-read.** `docs/tool-decision-pipeline/spec.md` rejected a Vite app under `ui/`:
"a build step and a lockfile are a mouth to feed (`T-3`) for a skeleton meant to be deleted
(`T-5`)". Half of that reason has expired — the page is not a skeleton and nothing plans to delete
it. The other half has not, and native ES modules give the file boundaries without either. The
decision stands on one reason instead of two.

**What the split had to pay for, and it is paid.** `tests/ui/dom.js` now compiles each file on its
own and resolves the specifiers between them (`vm.SourceTextModule`), `tests/ui/test_page.py`
passes node the flag that turns that on and sweeps `$("id")` over every `.js` under `ui/` rather
than over one name, and loading a page is awaited where running a script was not. It was the whole
price of the split and it was paid before a line moved, which is the only order in which a linker
that is wrong is legible as a linker rather than as a bad cut.

**`AGENTS_UI.md`.** Its laws are what § *The screen* below is written against, and each requirement
names the one it comes from. Two cautions. It names WordPress admin conventions, Gutenberg's
`PanelBody` and Tailwind utilities (`gap-2`, `px-4`, `text-lg font-semibold`), none of which this
repository uses — those names come out before it is cited as a rule, the way `AGENTS.md` carries
house style as a rule and never as another repository's path. And its Jakob's Law entry asks for
*familiar WP Admin patterns*, which this page cannot follow and should not: the pattern a labeller
already knows is a labelling tool, not a CMS.

## Requirements

### The source

1. **A module is named for the decision it hides, not for the step it runs in.** `app.js` is
   ordered by the flow today — queue, sample, checks, personal data, label, facets, record — which
   is the decomposition `H-7` names as the wrong one: a decision spans several steps, so a split by
   step lands every change in three files. The screen's order stays what the store spec says; the
   source's order is by what each file hides.
2. **Every file under `ui/` opens with one of the five tags** (`H-8`), and the import direction is
   that table's: `shape` imports nothing, `adapter` imports `shape` and `logic`, `wiring` imports
   everything, and nothing imports `app.js`.
3. **`logic` is almost empty here, by design.** Pipeline Requirement 46 says the page computes no
   answer of its own, so a `ui/` module tagged `logic` that computes a span, a vote, an agreement
   or an outcome is the page disagreeing with the service. The one composition the page owns is the
   record. The tag census is the check on Requirement 46 that one file could not give.
4. **A module names the ids it owns, once, at its top, and names no other module's.** This is what
   makes the split more than a redistribution of 124 string literals: the list at the top of a file
   is that module's interface to the markup, a reader sees what a change to it can reach, and two
   modules claiming one id is a finding rather than a surprise.
5. **`app.js` keeps its name and becomes the wiring** — the composition root `index.html` loads:
   every handler attached, the keyboard, the first paints, and the two transitions that repaint the
   whole screen (`openSample`, `forgetEverything`). It holds no drawing of its own.
6. **No build step, no npm, no lockfile, nothing from a CDN.** Pipeline Requirement 45 carried
   forward unchanged: what is deployed is what is written, and a labeller needs nothing installed
   but the service. The file count is what changes, not that.
7. **The modules are ES modules**, loaded by `<script type="module" src="app.js">`.
8. **The test harness loads modules rather than one script.** `dom.js` installs its stub as globals
   on a `vm` context and links relative specifiers itself (`vm.SourceTextModule`, behind
   `--experimental-vm-modules`); `test_page.py` passes the flag and sweeps `$("id")` over every
   `.js` under `ui/` rather than over `app.js` alone.

### The screen

9. **Three kinds of thing, three forms.** What the machine did, what the reviewer must answer, and
   what they may inspect are three different kinds, and the screen says which is which before a
   word is read. Today all three are a card. *(Law of Similarity, read in reverse: things that are
   not alike must not look alike.)*
10. **A decision is a card headed by its question.** "Which of these are personal data?" and "Which
    call should this be?", not "The data" and "The label". A panel that asks something says what it
    asks; a noun makes the reviewer work out what is wanted. The step number stays, because it is
    the order they are worked in and the guide names it. *(Goal-Gradient; `R-1` read onto a
    screen.)*
11. **The act that moves the work on sits at the end of the work it needs, and machine work has no
    panel of its own.** *Find personal data* opens card 1, because it is what fills it. *Ask the
    reviewers* sits at the **foot of card 1**, directly above the card it fills, because that is
    where a reviewer is standing the moment the spans are approved — not in a band at the top they
    would have to scroll back to. Each check's model picker travels with its own button, which is
    the reason the store spec gave for the three columns in the first place: *a picker somewhere
    further down the page is a picker nobody finds*. What each check said is the state word in the
    head of the card it fills, so nothing is reported twice. *(Fitts's Law; Goal-Gradient. Hick's
    Law is why the third panel goes rather than being restyled: the reviewer's eye should find two
    questions, not three panels and a table.)*
12. **The action bar says what is still unanswered, and says it before submit is pressed.** One
    line, counting both cards: nothing run, no verdict said, a facet with nothing ticked. It is not
    a refusal — a refusal still lands on the panel that owns it, after the attempt, in the service's
    own words. This is the same fact told early, where it changes what the reviewer does next rather
    than reporting what went wrong. *(Zeigarnik; Goal-Gradient.)*
13. **One spacing scale and one type scale, declared as tokens.** Spacing is 4 / 8 / 12 / 16 / 24 /
    32 and nothing else; type is three sizes and `12.5px` is not one of them. Every rule in
    `style.css` uses a token, and a raw pixel value in a margin, a padding or a gap is a finding.
    *(Aesthetic-Usability.)*
14. **One name per role.** Secondary text is spelled one way, a state word one way, a form field's
    name one way. The component set is named once — a card, a question head, a state word, an act
    row, a note, an empty region, a form field, a refusal, a table, a tick list, a disclosure — and
    a panel that needs a second spelling of something is a panel to look at again. Every class the
    markup writes has a rule, and every rule has a user. *(Law of Similarity.)*
15. **A state is a word first and a colour second.** Already the CSS's own stated rule, carried
    forward: nothing on this screen may be legible only to someone who can tell two colours apart.
16. **Everything a person waits for says it is working.** The queue's next sample, the samples list,
    a page of the dataset, the statistics and the copy that ships: a table about to fill shows
    skeleton rows, and the run button keeps naming the check it is on. *(Doherty Threshold.)*
17. **What may be inspected is collapsed; what must be answered is open.** The disclosures are the
    only collapsed things on the screen, and no question ever hides inside one.

### The flow

20. **The spans are approved before anything is asked of a model.** Detect, then the reviewer ticks
    which spans are real, then the record is redacted, and only then is the panel asked. A juror
    reads the redacted conversation and nothing else, so the argument it writes carries the
    placeholder the turn carries — one value, one placeholder, arrived at by reading rather than by
    substitution afterwards.
21. **So there are two buttons where there is one today.** A human decision now sits between the two
    checks, and a button that ran both would run the second one against spans nobody had approved.
    The first says *Find personal data*; the second, which is disabled until the spans have been
    approved, says *Ask the reviewers*. Neither runs on load. This is the sentence that rewrites
    `docs/tool-decision-store/spec.md` § *The page*, **one button runs both checks** — it was one
    button because nothing was decided in between, and now something is.
22. **What the card proposes is the panel's answer, and what arrived is shown beside it.** The
    reviewer has three acts, which is what the screen already asks of them spelled as two radios and
    a button: **take the reviewers' answer**, **keep what arrived**, or **write it yourself**.
    Taking the reviewers' answer is one click and it lands in the record — a panel whose full call
    has to be retyped by hand is how a corpus ends up storing a bare name.
23. **Nothing a reviewer reads or types on this screen is JSON.** A predicted call, a label, a
    juror's vote and the record about to be written are tables or forms, in the words the catalog
    uses. The raw JSON stays reachable behind the disclosures that already exist, because a verdict
    nobody can check is worse than a payload nobody reads — but it is never the first thing, and it
    is never the only way to do something.
24. **A label is edited as a form built from the sample's own catalog.** The tool is picked from the
    tools that sample offers; each argument is a field, labelled and described by that tool's own
    parameter schema, with the required ones marked. The page builds the form and composes the
    call — which is the record it already composes — and still decides nothing about whether the
    call is right: that is what the warning from `POST /data-quality/label` is for, unchanged.
25. **The record is confirmed as a table before it is written.** Every key that will land in a row,
    in words, with the redacted values showing as their placeholders. It is already on the screen
    while it is being made; what changes is that it stops being a `<pre>` nobody outside this
    repository can read.
26. **The corpus is one button away, and only the half that may be read.** `GET /records` answers
    `tool_decision_dataset` — the facets, the counts, and one row opened whole. **There is no route
    to `tool_decision_record` and this screen does not ask for one**: that table keeps what arrived
    un-redacted, and serving it would put a customer's address on the screen of anyone who can open
    the page, which is the thing this whole part exists to prevent.

### The spans

27. **A span is a value and a class. Offsets are answered, never typed.** A reviewer unticks a value
    the scan claimed, or types one it missed and says what kind it is. Where that value stands in
    the text, how many times, which occurrences count and which nested span is dropped are the
    service's answers — `order_claims_by_class` and `find_and_number_spans`, the same two the
    detector runs, so a value the reviewer added is numbered by the rule that numbered the rest.
28. **So three controls go.** The offset table behind *The spans, by offset*; *Re-read the rows*,
    which existed to re-slice what somebody typed; and the **`auto` tick box**, because dropping a
    span inside a longer one is what `find_and_number_spans` does unconditionally. With them goes
    `app.js`'s `inside` — the JavaScript copy of the containment rule — and the pipeline spec's
    admission that one rule lives in three places becomes two. **The rule is still measured over
    the values still ticked**, which is what the toggle's own sentence gave as its reason: untick a
    street and the name inside it is what is left to hand back. It falls out of what is asked
    rather than out of a box — only the ticked values are sent to be numbered — and the price is
    that a placeholder moves when a value before it is unticked, which is a number changing under a
    reviewer's eye against a value they kept going out un-redacted.
29. **A value typed once is replaced everywhere it occurs.** That is not a new rule; it is
    Requirement 12 of the pipeline spec, which already replaces by value and not by offset. What is
    new is that the reviewer can see it: the row says how many occurrences that value has, and the
    redacted text below shows every one of them carrying the same placeholder.
30. **Renumbering costs no model call.** The route that answers it runs the two pure functions and
    nothing else, so a reviewer adding a value gets the spans back immediately and the panel is
    never re-asked for it.

### The order

31. **The move lands first, with the screen frozen.** `tests/ui/page.js` and `tests/ui/reading.js`
    pass unedited except for how the page is loaded. That is the whole evidence that a 1763-line
    file was cut up and nothing moved on the screen, and there is no other way to get it.
32. **Then the scale, then the flow, then the form.** The spacing and type tokens go in before
    anything new is drawn, because new markup should be drawn against them. The flow goes next,
    because it rewrites the whole of card 2 and polishing a card about to be rewritten is work
    thrown away. The remaining form work — the two cards, the question heads, the bar, the waiting
    states — comes last, over a screen whose shape has stopped moving. Every check broken after the
    move is edited deliberately, one requirement at a time; a check rewritten in the same commit as
    a move proves nothing about either.

## Design

### The modules

Fourteen files, `1763 → ~125` lines each, the largest ~300. Names are kebab-case, the convention of
the language they are in and of the URLs they are served at. `layout.md` carries the table with what
each one holds; the rule that put them there is Requirement 1, and the shape it produces is worth
stating: **eleven of the fourteen are `adapter`**, because almost everything here translates a
response into markup. One is `shape`, one is `wiring`, and exactly one is `logic` — the record. A
fifteenth file tagged `logic` is the signal to stop and ask what rule the page has started keeping
a second copy of.

**Two seams named but not cut** (`T-2`: decide the boundary early, cut the file late).
`personal-data.js` holds two decisions — which spans are real, and what the copy is — and they stay
one file while the copy has no consumer but that panel and the record (`C-7`). `corpus.js` holds
the dataset sheet and the statistics; they stay one while both are read off `/records`.

### The screen

| kind | what it is | form |
|---|---|---|
| **machine work** | the two checks, the models that answer them, what they said | **no region of its own**: each act is a row at the point in a card where it is needed, and what it said is the state word in that card's head |
| **a decision** | which spans are real · which call this should be, and what kind of sample is this | a card, headed by the question, carrying its own unanswered state. Card 2 holds the panel's proposal as a table, what arrived beside it, and the form that edits either |
| **something to inspect** | the raw sample, the spans a value earned, each juror's own text, the record's raw JSON | a disclosure, closed, one treatment for all four. Never the first way to read something, and never the only way to do something |
| **where things stand** | the corpus counts, which database, what is left on this sample | the strip at the top, and one line in the action bar |

The skeleton does not move: the header, two panes, the action bar, the four sheets. What changes is
which of those wears which form, the question at the head of each card, the live line in the bar, a
spacing and type scale under all of it — and, in card 2, what is being confirmed.

**The order, as the reviewer walks it.**

```
open a sample
  → [Find personal data]   at the head of card 1, because it is what fills it
  → tick the values that really are personal data · type any the scan missed
      (each edit renumbers, and redacts, by itself)
  → [Ask the reviewers]    at the FOOT of card 1, where the reviewer is already standing
  → take the panel's call · keep what arrived · write it myself
  → tick the facets  → read the record as a table  → [Submit & next]
```

Every arrow but the last two is a route. The two buttons are where they are because a person decides
between them; the redaction sits inside that gap rather than after it; and the second button is at
the bottom of the first card rather than the top of the pane because that is where the hand already
is.

## Decisions

1. **ES modules over several classic scripts.** The alternative is a few `<script src>` tags in
   order, which needs no harness change at all. It also gives no import edges: every file would
   share one global namespace, nothing would declare a direction, and nothing could check one — a
   layout that looks split and is not. The cost of modules is paid once, in `dom.js`. A second cost,
   stated: `index.html` opened over `file://` stops working, because modules are fetched under
   CORS. The page is only ever served from `/ui`, so that costs this repository nothing.
2. **Not a Vite app, and not the reference's toolchain.** Decision 15 of the pipeline spec, kept, on
   its surviving reason. What is taken from `label-studio` is its rule — one place for the API
   surface, one for shared state, panels that own their own markup, and a token layer — not React,
   Nx, bun, Tailwind or shadcn. Stated plainly because the ask named that repository: a 1822-file
   layout is the right answer to 1822 files of frontend and the wrong one to fourteen.
3. **`app.js` keeps its name.** It is what `index.html` loads and what every document in `docs/`
   names. A restructure that also renamed the entry point would make every one of those references
   wrong for no gain.
4. **`index.html` stays one file.** The alternative is each panel's markup moving into its module as
   a template string, which is what the reference does with JSX. Here it would cost the three
   things that file is good for: a person can read the whole screen's structure in one place; the id
   declaration stays one declaration (Requirement 4 is written against it); and `test_page.py` reads
   the markup as text rather than by running the page. The co-location it would buy is mostly
   already there, because a panel's content is painted by its module today.
5. **`style.css` stays one file, reordered into four bands** — tokens, primitives, components,
   screens — in that order. The alternative is `@import` per area, which needs no build step and
   would have read as consistent with the split. It buys shorter files and nothing else: CSS has one
   cascade whatever it is cut into, so the boundary would not be one, where a JS module boundary is
   an import edge something can hold. The four bands are what Requirement 14 is read against: a
   component defined twice is visible as two rules in the same band.
6. **Kebab-case for a multiword file name.** The repository is snake_case, but that is Python's;
   these are `.js` files served at URLs. One line of inconsistency, named here so it is a choice
   rather than a drift.
7. **The state stays one object, and stays mutable.** `held` is 116 references, and the honest
   alternative — each module owning its own slice — would spread one sample's worth of state across
   nine files and make *what is on the screen right now* unanswerable from any one of them. It moves
   to `held.js` as `shape`, the smallest change that gives those 116 references one home.
9. **The parsed consensus is answered by the edge, not by the modality and not by the page.**
   `parse_text_to_tools` already exists in `profile/tool_decision/utils.py`; what is added is a field
   on `ReviewerVerdicts`, declared in the router. The two alternatives are both worse in a way the
   repository has already been bitten by: parsing in JavaScript makes a second definition of what a
   tool call is, and putting the field on `LLMReviewerVerdict` teaches
   `modalities/text2text/ai_review/` the word *tool*, which is the one thing a layer serving every
   text2text task may not learn.
10. **The redesign keeps every panel the store spec put on the screen.** Nothing is merged, split,
   moved between panes or taken away. What changes is the form each one wears, its heading,
    what the bar says while it is unanswered, and — in card 2 alone — which of two labels is the one
    being confirmed.

## What this rewrites

A document that disagrees with the tree is a stale document, so these are rewritten in the change
that makes them untrue, not added to.

- ~~`docs/tool-decision-pipeline/spec.md` Requirement 45~~ — done in `T11`: fourteen files, and no
  build step, no npm, nothing from a CDN unchanged.
- ~~Its Decision 15~~ — done: it keeps its conclusion and stands on one reason instead of two.
- ~~Its Design § *The labelling UI*~~ — done: it no longer reasons from three files.
- Its file table rows `ui/index.html`, `ui/app.js`, `ui/style.css` — still to do; the table is what
  `layout.md` § *The tree* lists.
- `docs/tool-decision-store/spec.md` § *The page*, **the checks are three columns** — the three
  columns stand; the sentence gains that they are a band rather than a panel.
- The same section, **the action bar holds exactly two acts** — still two acts, and it gains the line
  that says what is unanswered. A line of text is not an act, and the refusal on the owning panel
  stays where it is.
- The same section, **one button runs both checks** — it becomes two, and the reason the sentence
  gave for one is the reason there are now two: nothing was decided between them, and now the spans
  are. *Never on load* stands, and so does *one that fails names itself and stops the one after it*.
- The same section, **saying *correct* or *modify* is an act** — three acts, not two, and what
  *correct* is said about is the panel's proposal rather than what arrived. The sentence's own
  reason is untouched: neither is ticked for them, because it is a thing a person says.
- The same section, **the label is redacted with the turns, in the same placeholder** — still true
  of the label that *arrived*, and no longer the mechanism for the label that *ships*: that one is
  written against a redacted conversation, so it carries the placeholder because the juror read one.
- The same section, **the record the page will post is on the screen while it is being made** — it
  stays on the screen and stops being JSON.
- `docs/tool-decision-pipeline/spec.md` Requirement 46 — unchanged and worth citing in the change:
  the parsed consensus is added to what the route answers *because* of it.
- `docs/tool-decision-store/spec.md` § *The page*, **the checks are three columns** — the table goes
  and its reason is kept: each model picker travels with the button that spends it, which is a
  stronger reading of *a picker somewhere further down the page is a picker nobody finds* than a
  panel of its own was.
- ~~`docs/tool-decision-pipeline/spec.md` Requirement 41 and its § *Invariants* note that **one rule
  lives in three places**~~ — done in `T25`: it lives in two, and the labelling page holds neither.
  That passage said the duplication was the price of an editable offset; the price is refunded and
  the note is rewritten rather than deleted, because the scan and the drawing still hold it twice.
- ~~The same spec's § *The labelling UI* sentence about the reviewer resolving a typed row against
  the rows beside it~~ — done in `T25`: nothing is resolved on the page any more.

## Out of scope

- **Which routes exist, and what each one computes.** Three additions, all for the reason
  Requirement 46 gives: one field on what `/ai-review` answers, one route that renumbers claims with
  the two functions the detector already runs, and — landed with it in `T25` — one that answers the
  classes those scans declare, because a picker of kinds filled from a list written into the page
  would offer a class no scan declares and put the rest in another order, and the order is the one
  `<CLASS_N>` counts in. None decides anything new; the second **removes** a rule the page was
  keeping a second copy of. No rule about a span, a vote or an outcome is re-decided here.
- **Any second opinion about whether a label is right.** The warning from `POST /data-quality/label`
  is what it was, and it still warns rather than blocks.
- **Splitting `tests/ui/page.js`.** It is 1251 lines and mirrors `app.js`, so the same argument
  reaches it — but the split *forced* by this change is the loader, and a test file cut up in the
  same commit would make a green suite prove less, not more.
- **An import-direction check for `ui/`.** `tests/guards/test_import_direction.py` walks Python with
  `ast`, and this repository has no JavaScript parser and will not grow one for it.
- **Rewriting `AGENTS_UI.md`.** Named in Context as something that needs the WordPress, Gutenberg
  and Tailwind references taken out; that is its own change.
- **A dark theme, and any second visual language.** One scale, one accent, one theme.

## What else to add

In this order, once the layout is in the tree and only then:

1. The `ui/` direction check — the tags are regular enough at the top of a file, and so are ES
   module `import` lines, that a regex sweep in `tests/guards/` holds Requirement 2 without a
   parser. Written after the shape is accepted, because a check is earned by a rule that has been
   broken here.
2. The id-ownership sweep of Requirement 4, extending the one `test_page.py` already runs.
3. A raw-pixel sweep of `style.css` holding Requirement 13.
4. `page.js` split to follow the modules it drives.

## Open

- **The question at the head of each card is the one thing here a reviewer will argue with.** "Which
  of these are personal data?" and "Which call should this be?" are proposals; whoever labels for a
  day gets the casting vote, and changing them later costs one line each. The second is phrased as
  the panel's question rather than the corpus's on purpose — *is this label right?* asks about what
  arrived, and what arrived is the half this flow stopped leading with.
- **What a value's class list should offer.** The scan claims a class per value and the reviewer can
  correct it, so the picker needs the classes this corpus actually uses. Read off what the scans
  declare rather than typed here, and settled the first time somebody corrects one.
- Whether *Ask the reviewers* should also be reachable from the action bar for a very long sample.
  It sits at the foot of card 1, which is right for a conversation a person has just scrolled
  through; a fifty-turn one may want both. Decided by using it, not here.

## Sources

- `docs/tool-decision-pipeline/spec.md` § *The labelling UI*, Requirements 45–47, Decision 15
- `docs/tool-decision-store/spec.md` § *The page*, § *Raw data in*
- `AGENTS.md` — `H-7`, `H-8`, `C-1`, `C-2`, `C-7`, `R-1`, `R-8`, `T-2`, `T-3`, `T-5`, `E-1`
- `AGENTS_UI.md` — Aesthetic-Usability, Hick, Fitts, Proximity, Zeigarnik, Goal-Gradient,
  Similarity, Miller, Doherty
- `label-studio-develop/web` — `apps/labelstudio/src/`, `libs/`, `design-tokens.json`
