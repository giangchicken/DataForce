# Axis module shape — Implementation Spec

**Status:** awaiting review · **Reads from:** [`../annotation-pipeline/spec.md`](../annotation-pipeline/spec.md),
AGENTS.md · **Style reference:** the internal
`agent-evaluation` service, which `annotation-pipeline/spec.md` already names on its own line 3

---

## What

Both axis implementations put every conversion they own in one `utils.py`: 562 lines in
`modalities/text2text/`, 916 in `profiles/tool_decision/`. This document specifies three changes,
in order, each independently landable:

1. **Move the `agent-toolkit` pin** to a tag that holds the library's four personal-data scans, so
   layer one can be a call into them instead of a second copy of them.
2. **Rewrite invariant I4** so it constrains the direction of an import rather than the number of
   files in a package.
3. **Split both `utils.py`** into modules named for what they produce, and give the manifest reader
   both axes copy a single home.

Nothing about the flow, the record, the two protocols, the endpoints or the question store changes.
No member is added to or removed from either protocol. The public surface of both axis façades is
the same after this work as before it — which is what makes the whole thing verifiable by a test
that already exists (I23).

---

## Context

`annotation-pipeline/spec.md` Decision 14 already settled this question once, and settled it the
other way: *"`utils.py` stays … Alternative: split each into `parts.py`, `embedding.py`,
`detectors.py`. Why not: three modules with one consumer each — the `__init__.py` that assembles the
axis — which the sentence above the exemption forbids."* This document reopens it because four of
the facts that decision rested on are measurably not true, and one of them was never true.

**1 · The exemption does not cover most of what the modules hold.** AGENTS.md grants `utils.py`
"only for conversions over the shapes in the `schema.py` beside it". Counting top-level functions
that name a shape defined in the `schema.py` beside them:

| module | lines | code lines | top-level functions | functions touching a `schema.py` shape |
|---|---|---|---|---|
| `modalities/text2text/utils.py` | 562 | 214 | 16 | **2** — `a_detector`, `personal_data_detectors` |
| `profiles/tool_decision/utils.py` | 916 | 423 | 23 | **5** — `calls_in`, `catalog_of`, `one_call_schema`, `agreed_arguments`, `vote_consensus` |

The other 32 are a language vocabulary, two manifest readers, two JSON canonicalisers, turn
rendering, answer arithmetic and annotation decoding. The exemption has not been stretched — it
stopped covering these modules some time ago and nothing said so, because no guard reads the convention's
condition and the guard that does read the package (I4) only counts files.

**2 · A second consumer already arrived — three of them, and they are tests.** Decision 14's
"one consumer each" is the reason it gives, and it is false today:

- `tests/stages/test_text2text.py:35` imports `PHONE_PLANS`, `SPOKEN_PII_FORMS`, `phone_plan`,
  `spaced` and `spoken_pii_forms` from `text2text.utils`
- `tests/stages/test_tool_decision.py:32` imports `stated_calls` from `text2text.utils`
- `tests/guards/test_one_canonical_form.py:35` imports `canonical_json` from `tool_decision.utils`

Under the rule that *"no test imports a module's internals. If one must, that is a design finding, not a test
problem"* — those three lines are the finding. They are also the second consumer whose
absence was the stated reason not to split.

**3 · The style reference this repository names does the split, and accepts the consumer count.**
`annotation-pipeline/spec.md` line 3 names `agent-evaluation` as the style reference. Its feature
folders are named modules, and its modules have exactly the consumer count Decision 14 rejected —
counted as import statements across its `src/`:

| feature folder | modules | importers each |
|---|---|---|
| `agents/evaluations/llm/function_calling/` | `parser.py` (54L), `runner.py` (126L), `schemas.py` (81L) | 4, 3, 33 |
| `agents/testcase_generator/user_behavior_simulation/` | `extract_intents.py` (192L), `extract_steps.py` (128L), `generate_scenarios.py` (404L), `graph.py` (319L), `schemas.py` (225L) | 4, 3, **2**, 7, 33 |
| `agents/testcase_generator/flowtest_generator/` | `agent.py` (470L), `generator.py` (177L), `graph.py` (163L), `submit_graph_tool.py` (128L), `schemas.py` (81L) | **2**, 3, 7, **2**, 33 |

Three of those modules have two importers — the façade and one sibling. That is the shape Decision
14 calls forbidden, in the codebase Decision 14's own document calls the reference. One of the two
sentences has to give, and the measurement says which.

**4 · The `utils.py` files cannot get a real name, because a guard forbids it.**
`tests/guards/test_axis_module_shape.py` requires an axis package to hold exactly `__init__.py`,
`schema.py` and `utils.py`, and carries a test named `test_the_scan_rejects_a_fourth_module`. So
AGENTS.md's remedy — *"the moment it holds something else, it needs a real name"* —
is a build failure. **A rule that forbids its own remedy converts every later addition into
`utils.py`**, which is the outcome the convention exists to prevent. AGENTS.md records the
resolution: *a guard may fix a package's shape only where the conventions state that
shape, and should prefer to constrain the direction of an import over the number of files.*

**5 · The whole of layer one is a duplicate of the library.** `agent-toolkit`'s `main` holds
`phone_number_detection_by_rules`, `email_detection_by_rules`, `otp_detection_by_rules` and
`name_detection_by_rules` (`d0abc5d`, `src/agent_toolkit/string_utils.py`), each
`(text, language) -> list[str]`, together with the vocabulary tables behind them — so the six pattern
shapes here, the words that fill them and the tone-stripped twin of each are all a second copy of
something that ships. **T54 is where they go, and it is specified in
[`../annotation-pipeline/spec.md`](../annotation-pipeline/spec.md)** — § *Modality*, § *PII, in two
layers* and Requirement 18 — because a `Detector` becomes a class and a scan rather than a pattern,
which is a change to that document's own contracts and not to this one's module shapes.

I6 cannot see the duplicate yet. The guard reads owned names off the **installed** library; the pin
resolves by tag, `v0.1.0` is at `2b603a6`, and the four scans are past it. The pin move is what makes
the rule effective, which is why T54's first step is to relock and read the installed `__all__`.

**6 · The manifest reader is duplicated, and the reason given for duplicating it is not true.**
`declaration`, `declared_name`/`declared_text` and `canonical_json` are copied between the two
`utils.py` — about 20 lines of code carrying about 15 lines of prose defending the copy. The defence,
in both docstrings and in § *The two axes*, is that the axes share *"`name`, `version`, `Part` and one
separator and nothing else"*, so a shared reader would be a fourth shared thing. They share more than
that already: `Manifest` (a whole type, whose own docstring at `manifest.py:5` argues **against**
splitting it), `ConfigError`, `Record`, `SPOKEN_AND_STATED` — and since Decision 24, `ToolDecision`
**subclasses `Text2Text`**. The two copies of `declaration` differ in one string: `config/modalities/`
versus `config/profiles/`.

The vocabulary objection is real and survives: a shared reader must not learn a key. It is satisfied
by signature rather than by duplication — `declaration(manifest, *path: str)` takes the path from its
caller and names no key, and every key constant stays in the axis that means it.

**What is not wrong with these files.** 38% of `src/` is docstring (2647 of 6905 lines) and that is
Documenting the interface where it lives, working as intended. `tool_decision/utils.py` is 423 lines of code, not 916. The problem is the
number of unrelated jobs in one module, not its length, and this document does not delete one
sentence of prose — every docstring moves with the code it documents.

---

## Decisions

**D1 · The pin moves, rather than the copy being kept in step by hand.**
`agent-toolkit` is a repository we own; the branch is written, tested and one commit ahead of `main`.
*Alternative:* keep the local copy and add a guard comparing the two tables. *Why not:* the guard
would have to import a library the lockfile does not resolve, which is a second dependency graph for
a test. *Alternative:* delete the branch and keep this the only home. *Why not:* the vocabulary is a
fact about a language and has no connection to this pipeline — the branch commit says so and
`text2text/utils.py:103` agrees. *Cost:* none beyond the vocabulary — corrected on
2026-08-30, having first been written the other way. This entry said the move would drag
`llm-yaml-config` along, which was read off a **stale local tag**: the checkout beside this repository
has `v0.1.0` at `ec1f338`, the remote moved it to `2b603a6` some time ago, and `git fetch` refuses to
clobber a local tag, so the difference is silent. `uv.lock` records `2b603a6` and the installed
`agent_toolkit.llm.__all__` already carries `YamlConfigResolver`. `v0.1.0..main` is exactly two
commits — `61fdf65` and its merge `d0572c9` — so the move brings the vocabulary and nothing else.
**Read the lockfile, never a local tag, when deciding what a pin contains.**

**D2 · `PHONE_PLANS` stays here, and stays wrong.**
Only the language half leaves. A numbering plan is a fact about a country, and one of its numbers is
already known to be wrong — `written_digits` is `(10, 11)` and `spoken_words` is `(9, 10)`, where nine
dictated digits is not a valid Vietnamese mobile. It is not corrected here: a detector's reach decides
what gets redacted, and correcting it shrinks what layer one finds. What settles it is a measurement
of layer-one recall over a declared corpus, which is the pilot's. **This document changes no
pattern.**

**D3 · An unknown language stays a `ConfigError`, raised where the detectors are built.**
A scan indexes its vocabulary table by language, so a language nobody wrote down reaches a caller as a
`KeyError` on the first record scanned. `errors.py` says `ConfigError` is "the one exception this
codebase defines" and the edge maps it to a 400, so `pii_detector.py` checks the declared language
against the library's tables when it builds the detectors and raises `ConfigError` naming the
languages there are — at composition, before any record is read, which is where Requirement 43 wants
a bad declaration to fail.
*Alternative:* let the `KeyError` escape. *Why not:* it makes the engine raise a second exception type,
falsifies `errors.py`'s docstring — *"the only exception the engine raises"* — hands the edge
something its 400 mapping does not cover, and does it per record instead of once.
*Noticed while writing this:* § *Error Behavior* has no row for an undeclared `language:` at all,
which is why T54 adds one rather than editing one.

**D4 · I4 constrains the import direction and the exemption's condition, not the file list.**
New form: **an axis implementation has a `schema.py` that imports no sibling; and a `utils.py` beside
it, if one exists, holds only conversions over those shapes.** The first half is what I4 checks today,
generalised from "imports no `utils`" to "imports no sibling" — a `schema.py` that imported
`detectors.py` would be the same defect under a new filename. The second half is AGENTS.md's
condition, made mechanical for the first time: every top-level function in a module named `utils.py`
must reference a name defined in the `schema.py` beside it.
*Alternative:* a threshold — *most* functions must. *Why not:* a tuned literal in a guard is the
finding and there is no measurement behind any particular number. The convention says "and nothing else", so the
rule is *every*, and a helper that touches no shape belongs with the thing it helps.
*Alternative:* forbid `utils.py` outright. *Why not:* the convention grants it on purpose, and a new axis whose
conversions really are all over its own shapes should be allowed to have one. After T56 neither
package has a `utils.py`, so the second half binds only the next axis someone writes — which is
exactly when it is worth having.

**D5 · A module is named for what it produces, and the façade re-exports one name from each.**
This is the naming rule applied to filenames, and it is the style reference's shape. `modality.py` and `profile.py`
name the object that answers the protocol; `turns.py`, `detectors.py`, `answers.py`, `annotations.py`
and `records.py` each name a result. **No guard enforces this**, for the reason the naming rule gives about itself:
telling `answers.py` from `helpers.py` is a judgement, not a pattern. It is caught in review or it is
not caught.

**D6 · The manifest reader becomes `dataforce/declarations.py`, and names no key.**
Top level, beside `manifest.py`, holding `declaration`, `declared_name`, `declared_count` and
`declared_roles`. It is the same relationship `pipeline/params.py` already has to `params.yaml`, and
its docstring line is written to rhyme with that one. The directory in the error message comes from
the manifest rather than from a literal: `config/profiles/` when `manifest.modality` is set,
`config/modalities/` when it is not — which is what that field already means.
*Alternative:* leave both copies and add a guard holding them equal, the way I24 holds the three
`json.dumps`. *Why not:* I24 exists because the canonical form is genuinely constrained from three
directions; a config reader is constrained from none, and a guard pairing two copies is a
pass-through with a test attached.
*The check that keeps the vocabulary out:* `declarations.py` contains no string literal that is a
manifest key. Its four functions take `*path: str`.

**D7 · `canonical_json` moves to `record.py`, and there is then one of it.**
There are three copies of `json.dumps(value, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)` in the package — `record.py:159` inline, and one `canonical_json` per axis. A
`record_id` *is* the hash of that string, so `record.py` is where the form is defined and the two axes
import it. Both already import `record.py`, so this adds no dependency edge. I24's first half then has
one call site to check instead of three, and its second half — running the two `canonical_json`s over
values chosen to tell the options apart — collapses to running one.
*This is separable.* If it is rejected, D6 and the splits still stand and I24 is unchanged.

**D8 · What this does not do.**
No behaviour changes. No pattern, threshold, protocol member, record key, endpoint or config key
moves. Every docstring travels with the code it describes, so the prose that explains a decision stays
at the line where the next reader hits it. The proof is I23: an axis implementation's public
surface is exactly its protocol's members, and it is asserted before and after.

---

## The target layout

Rows are written the way I19 requires — the text **is** the module's own docstring first line, and the
guard compares them word for word. These rows are what § *Package layout* gains.

```
  declarations.py           LOGIC · the manifest declarations an axis reads, checked where they are read.

  modalities/
    text2text/
      __init__.py           façade · the text2text modality; the object a composition root registers, and the encoder it is built with.
      schema.py             DEFINITION · the text2text shapes: what a detector is, and what its display config holds.
      turns.py              LOGIC · one turn as one part: what it said, what it called, and the string that holds both.
      detectors.py          LOGIC · the six shapes layer one scans for, filled with the words a declared language dictates.
      modality.py           LOGIC · Text2Text — the object that answers the Modality protocol.

  profiles/
    tool_decision/
      __init__.py           façade · the tool_decision profile; the object a composition root registers.
      schema.py             DEFINITION · the tool_decision shapes: a call, an answer, and what constrains one.
      answers.py            LOGIC · the answer space, and the three operations over an answer: distance, permitted, consensus.
      annotations.py        LOGIC · what one annotation said, decoded from the controls the capture half emitted.
      records.py            LOGIC · the answer a record carries: the one that ships, the one its turns restate, the redacted one.
      profile.py            LOGIC · ToolDecision — the object that answers the Profile protocol.
```

**Where each existing name goes.** Nothing is deleted except what layer one duplicates of the
library (T54); nothing is renamed.

| from | to |
|---|---|
| everything layer one is built from — the pattern shapes, the vocabulary and the tone-stripped twin | `agent_toolkit.string_utils`; what stays here is one detector per class (T54, `../annotation-pipeline/spec.md`) |
| `spoken_text`, `a_turn` | `text2text/modality.py`, where the turn a profile in the family overrides is one method |
| `stated_calls`, `call_arguments` | `tool_decision/records.py` — a call is that module's vocabulary (T54) |
| `Encoder`, `embedding_model`, `TURN_SEPARATOR` and the embedding keys | `text2text/text_embeddor.py` (T54) |
| `Text2Text`, `text_parts`, `DISPLAY_TAGS`, `CONVERSATION` and the item keys | `text2text/modality.py` |
| `calls_in`, `entries_in`, `catalog_of`, `one_call_schema`, `answer_schema`, `answer_is_permitted`, `argument_agreement`, `answer_distance`, `agreed_arguments`, `vote_consensus` | `tool_decision/answers.py` |
| `control_values`, `typed_arguments`, `corrected_answer`, `one_written_line` | `tool_decision/annotations.py` |
| `final_label`, `restated_answer`, `redacted_arguments`, `redact_label` | `tool_decision/records.py` |
| `ToolDecision`, `CAPTURE_TAGS`, `VERDICTS`, `SCENARIO_LENGTH` and the manifest key constants | `tool_decision/profile.py` |
| `declaration`, `declared_name`, `declared_text`, `declared_count`, `declared_roles` | `dataforce/declarations.py` — one copy, `declared_text` folded into `declared_name`, plus `declaring_file` |
| `canonical_json` ×2 | `dataforce/record.py` — one copy, and `record_id_for` calls it (D7) |
| `one_role` | `tool_decision/profile.py` — its one caller is `ToolDecision.__init__` (`utils.py:680`), and the role it names is the profile's vocabulary, not a reader |

**Three rows were corrected while this was being built (T56).** `turns.py` describes one turn and
not one item, because `content_parts` — the member that turns an item's turns into parts — stays on
the object in `modality.py`; `text_parts` went with it for the same reason, since refusing a media
part is the modality's rule about its own input and both of its callers are there, and the deletion
test below never named it. `records.py` describes the label a record carries and not the building of
one, because `build_record` is a member too. And `declarations.py` has a fifth function,
`declaring_file`: naming the file a message points at has four callers inside that module, which is
what the file rule asks a function for.

**Each new module answers the deletion test in one sentence:**

- `turns.py` — delete it and every caller has to know that a turn's `content` may be a string, a null
  or a content-block array, and that a call's `arguments` may be a JSON string or an object.
- `detectors.py` — delete it and layer one's six shapes are written at whatever site scans.
- `modality.py` / `profile.py` — delete it and there is no object to register.
- `answers.py` — delete it and δ, the answer space and consensus are re-derived per caller; four
  stages depend on δ alone.
- `annotations.py` — delete it and the annotation tool's `result` shape is read in more than one place,
  which Requirement 49 forbids by name.
- `records.py` — delete it and the only place a source shape is validated stops being one place.
- `declarations.py` — delete it and the reader is copied per axis, which is where this started.

---

## Invariants

**I4 is rewritten.** Its row in § *Invariants* becomes:

> | I4 | An axis implementation's `schema.py` imports no sibling, and a `utils.py` beside it holds only conversions over those shapes | two halves. AST scan over both axis packages: `schema.py` must exist and import nothing from its own package — generalised from "imports no `utils`", because a `schema.py` importing `detectors.py` is the same defect under a new name. Then, for any module named `utils.py`, every top-level function must reference a name `schema.py` defines: AGENTS.md grants that filename "only for conversions over the shapes in the `schema.py` beside it", and this is that condition, checked. The file-set half is gone — it required exactly three files and so made the convention's own remedy, *give it a real name*, a build failure |

The red-first rule applies: the new guard is proved red against a synthetic `schema.py` that imports a sibling, and
against a synthetic `utils.py` holding a function that touches no shape, **before** the packages are
split. The existing `test_the_scan_rejects_a_fourth_module` is deleted with the rule it proves.

**I6 is unchanged and newly effective.** Moving the pin adds the four scans to the owned set, so the
guard covers them with no code change of its own, and its document half — every backticked name in
§ *Context*'s ownership sentence must be a name the installed library exports — is what keeps that
sentence from naming a scan the pin cannot reach.

**I19 covers the new modules for free** — every row above is a module docstring, compared word for
word. **I23 is the proof the split changed nothing**: an axis implementation's public surface is
exactly its protocol's members, before and after.

**I24 loses two of its three call sites** if D7 is taken, and is otherwise unchanged.

**I2, I5, I16, I22 are unaffected.** I2 reads what `pipeline/` imports and `pipeline/` imports no axis
either way; I16 reads each axis's `base.py` and `__init__.py`, and the façades still re-export only
implementations; I22 reads the first word of each docstring, and every row above opens with one of the
five kinds.

**One new invariant, for D6:**

> | I25 | `declarations.py` names no manifest key | AST scan: no string literal in the module, so the reader cannot learn one axis's vocabulary. The four functions take `*path: str` and every key constant stays in the axis that means it — which is the objection § *The two axes* raised against a shared reader, answered by signature instead of by a second copy |

---

## Edits to `annotation-pipeline/spec.md`

These land **with the code, in the same commit**, because three guards parse that file and compare it
to the tree: I19 (§ *Package layout*), I6 (§ *Context*'s ownership sentence) and I21/I20 (unaffected
here). Editing it before the code turns the build red; editing it after leaves the build green while
the document is wrong, which is what the doc-and-code comparison exists to prevent.

| § | line | change | task |
|---|---|---|---|
| *Package layout* | 757–761 | *"Every implementation of either axis is `__init__.py`, `schema.py` and `utils.py`"* → the shape D4 states: a `schema.py` that imports no sibling, a façade that holds nothing of its own, and modules named for what they produce | T55 |
| *Package layout* | 672–674, 681–683 | the tree gains the rows above and loses the two `utils.py` rows; `declarations.py` is added at top level beside `manifest.py` | T56 |
| *The two axes* | — | the *"share `name`, `version`, `Part` and one separator and nothing else"* sentence is corrected: it omits `Manifest`, `ConfigError`, `Record` and the base class Decision 24 introduced, and it is the stated reason for the duplication D6 removes | T56 |
| *Invariants* | 1837 | I4's row → the row in § *Invariants* above | T55 |
| *Invariants* | 1856 | I24's row loses "and as `canonical_json` in each axis", if D7 is taken | T56 |
| *Invariants* | after 1857 | I25 is added | T56 |
| *Decisions* | 1588–1597 | **Decision 14 is not deleted.** Per AGENTS.md, a decision reversed is recorded where the next reader hits it: the entry keeps its argument and gains what changed — the four measurements in § *Context* above, and the fact that its "one consumer each" reason was already false when it was written | T56 |

**T54's edits to that file are stated in it**, not scheduled from here: § *Modality*, § *The two
axes*, § *PII, in two layers*, Requirements 18 and 47, § *Package layout*, § *Testing Strategy* item
6, and one new row in § *Error Behavior* for an undeclared `language:`. The `@v0.1.0` line in
§ *Versions* moves with it, because the four scans are what the pin has to reach.

`plan.md` carries T54, T55 and T56 as tasks. Nothing parses `plan.md`, so those edits can land first.

---

## Tasks

### T54 · Layer one is the library's four scans

Specified in [`../annotation-pipeline/spec.md`](../annotation-pipeline/spec.md) and scheduled in
`plan.md`. It is here only as § *Context* item 5, D2 and D3, which are the three things this
document has to say about it: what the duplicate is, that no reach may move in a refactor, and that
an unknown language stays a `ConfigError`.

---

### T55 · I4 stops counting files

**Goal.** The guard enforces D4's rule, and a fourth module in an axis package is legal.

**Context.** § *Context* item 4. This is the task that unblocks T56, and it lands alone so the two are
reviewable apart: after it, nothing has moved and the build is green.

**Approach.** Rewrite `tests/guards/test_axis_module_shape.py` to D4's two halves. Delete
`test_the_scan_rejects_a_fourth_module` — it proves a rule that no longer exists — and add the two
The red-first proofs D4 names. `docs/annotation-pipeline/spec.md` § *Invariants* row I4 and § *Package layout*
lines 757–761 change in the same commit.

**Acceptance criteria.** The new guard is red against both synthetic violations and green over the
tree as it stands today, with both packages still holding exactly three files. The second half is
therefore exercised against the two real `utils.py` **before** they move — and it will be red, since
2 of 16 and 5 of 23 functions touch a shape. **So this task lands the rule with both modules carrying
one annotated exemption each, naming T56 as the fix and dated.** An exemption that is a scheduled
deletion is what the hatch is for; `test_exemptions.py`'s ceiling of 5 has room for two.

**Source.** AGENTS.md: a guard may fix a package's shape only where the conventions
state that shape.

**Verify.** `make check`, and `test_exemptions.py` shows four standing exemptions rather than two.

---

### T56 · Both axes get modules named for what they produce

**Goal.** The layout above, and no `utils.py` in either package.

**Context.** § *Context* items 1, 2, 3 and 6. Decision 14 is reversed, in writing, in its own entry.

**Approach.** Pure moves, in this order so each step is green: `declarations.py` first with both axes
importing it (D6); then `canonical_json` into `record.py` (D7); then `text2text/` into three modules;
then `tool_decision/` into four. Every docstring travels with its code. The two exemptions from
T55 are deleted by this task, which is what *shrinking* means.

**Acceptance criteria.** I23 passes unchanged — the public surface of both façades is the same set of
names before and after. `tests/stages/test_text2text.py` and `test_tool_decision.py` import from the
module that owns each name rather than from `utils`, and `test_one_canonical_form.py` imports
`canonical_json` from `record.py`. No test's assertions change: if one has to, the move was not a
move and the task is wrong.

**Source.** AGENTS.md; I19, I23.

**Verify.** `make check`. Then the byte check: run the smoke corpus before and after and compare
`records.jsonl` and `metrics.json` byte for byte. The verify rule asks what proved that behaviour did not change,
and for a task that is entirely moves, an identical artifact is the only answer that means anything.

---

## Risks

**The pin is a tag, and this tag moves.** `v0.1.0` has been moved once already: it is `2b603a6` on
the remote and `ec1f338` in the checkout beside this repository, and nothing reports the difference.
T54 changes the pin to a **new** tag rather than moving this one again, for the reason
`pyproject.toml` already gives at the dependency — a moved tag is a release built from a tree nobody
chose, and it reaches this repository as a `uv.lock` diff under an unchanged version string.

**T55 lands a guard that is red on the tree it guards**, and pays for it with two exemptions that T56
deletes. The alternative — land T55 and T56 as one commit — makes the reviewable unit a rewrite of a
guard plus a move of 1478 lines. The exemptions are the cheaper cost, and they are dated.

**Decision 14 was right about one thing.** Each new module has one runtime consumer: the
`modality.py` or `profile.py` that assembles the axis. § *Context* item 3 is the argument that this is
the house shape and not a defect, and it is a measurement of the style reference rather than a
principle. If the reviewer reads those numbers and still wants one module, the fix is to say so here
and keep `utils.py` — but then the exemption sentence should be rewritten to describe what these
files actually hold, because today it describes something else and 32 of 39 functions are outside it.

---

## Out of scope

- **Correcting `PHONE_PLANS`.** D2. It waits for a recall measurement over a declared corpus.
- **Any second axis.** No `speech2text/`, no second profile. D4's second half exists for them and
  nothing else here anticipates one.
- **Splitting `record.py`** (672 lines, 445 of them code). It is one noun and its shape, which is one
  job; it gains `canonical_json` here and loses nothing.
- **The `agent-toolkit` release itself.** T54 depends on a tag in another repository. That work is one
  merge and one tag, and it is not scheduled here.
