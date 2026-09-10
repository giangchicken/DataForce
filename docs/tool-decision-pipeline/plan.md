# Build plan

Tasks for building what `spec.md` specifies. Read that first; this document schedules it and does
not restate it. Where the two disagree, the spec wins and this file is wrong.

**Source:** [`spec.md`](spec.md) @ `0ddb190`, plus the two passages the questions behind this plan
forced — Requirements 7 and 24, Decision 17 and the `edge/cli.py` row of § *Files*. AGENTS.md
@ `8a00fdb` for `H-8`, `E-1`, `T-1` and `T-5`.

**State at the time of writing.** The tree holds the whole shape and almost none of the behaviour:
34 modules under `src/dataforce`, and nine methods whose body is `pass`. `ruff check` and
`ruff format --check` are green. `pytest -m "not integration"` is green over 57 tests, all of them
guards — **no test in the repository drives this feature.** `mypy --strict src/dataforce` reports 38
errors, and 20 of them say the same thing: `Skipping analyzing "dataforce.…": module is installed,
but missing library stubs or py.typed marker`. There is no `src/dataforce/py.typed`, so the type
checker stops at the package's own boundary and every intra-package import resolves to `Any`.

That is the first task, because it is why the other numbers cannot be trusted. With the marker in
place `mypy` follows the imports and the count *falls* to 13 — the 20 vanish, four real findings
appear in `edge/cli.py`, and `Class cannot subclass "PersonalDataChecking" (has type "Any")` turns
out to have been the checker admitting it could not see the base class. `edge/cli.py` imports
`dataforce.services.text2text`, which this restructure deleted, so `import dataforce.edge.cli`
raises and the `dataforce` console script is broken — and nothing in the gate said so.

**Scope.** The two parts with a shape to act on — the personal-data scan and `ai_review` — the four
endpoints, the record the page posts, and the tests § *Testing Strategy* names. Phase 0 is the gate
itself: not discoveries to be made in Phase 2, but the reason a Phase 2 *Verify* means anything.

**Assumption:** no corpus is declared. Every fixture is hand-written, and § *Testing Strategy* asks
for nothing else.

---

## How to read this

**One task is one commit.** Each is sized for one session with no prior context: read the task, read
what its *Source* points at, do it, run its *Verify*, commit.

**Every task has the same parts.**

| Part | Answers |
|---|---|
| **Goal** | What is true once this is done |
| **Context** | Why it is not true today, and what will bite |
| **Approach** | The shape of the change — present only where the task needs one of its own |
| **Acceptance criteria** | The outcome to check. Never the steps |
| **Source** | Where in `spec.md` the requirement it serves lives |
| **Verify** | A command that runs as written |
| **Out of scope** | What belongs to a different task |
| **Blocked by** | What must land first, when that is more than the task before it |

**Every short reference resolves somewhere.**

| Written | Lives in |
|---|---|
| `Requirement 24` | `spec.md` § *Requirements* — 43 of them |
| `Decision 10` | `spec.md` § *Decisions* — 18 of them, the last an `Assumption:` |
| `H-8`, `E-1`, `T-5` | a rule in `AGENTS.md`. The ID is stable and citable |
| `T7` | a task in this file. The number is its name, not its place in the order |
| step 5 | one of the page's eight rectangles, `spec.md` Requirement 37. Steps are numbered by the page, and only there |

---

## Phases

| # | Phase | Goal — the outcome that ends it |
|---|---|---|
| 0 | The gate reads the package | `make check` is green, and `mypy --strict` type-checks `dataforce` instead of skipping it |
| 1 | The scan answers | `POST .../data-quality/personal-data` returns a real `PersonalDataDetected` over a hand-written sample, and `.../personal-data/replace` the copy over the spans handed back |
| 2 | The panel answers | `POST .../ai-review` returns both verdicts against stubbed model calls |
| 3 | Every endpoint is drivable alone | Each of the seven routes is exercised by its own arguments, and one record makes the round trip |

Phase 0 comes first and is not optional: every later *Verify* is `make check`, and until Phase 0
lands that command reports 38 errors whether the task worked or not. Phases 1 and 2 are independent
of each other — the scan and the panel share only the catalog rendering, which T5 pins — so they can
run in either order or at once. Phase 3 needs both.

---

## The tasks

**Needs** is what must land before this task can start; blank means *as soon as the phase opens*.
**Size** is a shape, not an estimate — **S** one module or one file · **M** several modules, or one
algorithm to get right · **L** more than one sitting, so split it if it grows while you work.

| # | Task | Phase | Needs | Size |
|---|---|---|---|---|
| T1 | The package declares itself typed | 0 | | S |
| T2 | Delete the CLI and its console script | 0 | T1 | S |
| T3 | No stub lies to the type checker | 0 | T1 | S |
| T4 | Five tags, one case, and the guard that reads them | 0 | T1 | M |
| T5 | The catalog rendering is pinned | 0 | | S |
| T6 | What layer two is asked | 1 | | S |
| T7 | `review_text`, and the scan's two layers | 1 | T6 | L |
| T8 | The scan's tests | 1 | T7 | M |
| T9 | The scan endpoint stops answering `None` | 1 | T7 | S |
| T10 | The three shared bodies in the modality | 2 | | M |
| T11 | The prompt, and the two `predict`s | 2 | T5 | M |
| T12 | The panel's tests | 2 | T10, T11 | M |
| T13 | Each endpoint through its own arguments | 3 | T9, T12 | M |
| T14 | The record's round trip | 3 | T13 | S |

---

## Phase 0 · The gate reads the package

**Goal.** `make check` is green, and `mypy --strict` type-checks `dataforce` rather than skipping it.

### T1 · The package declares itself typed

**Goal.** `mypy --strict src/dataforce` follows an intra-package import instead of resolving it to
`Any`, and says so by reporting fewer errors about more code.

**Context.** `dataforce` is installed editable and ships no `py.typed`, so PEP 561 says it is
untyped and `mypy` treats every `from dataforce.… import …` as an untyped third-party import: 20 of
the 38 errors are that one fact, and four real findings in `edge/cli.py` are invisible behind it.
Adding the marker alone is not enough and fails differently — `Source file found twice under
different module names: "modalities.text2text.ai_review.schema" and
"dataforce.modalities.text2text.ai_review.schema"`, because the editable install puts `src/` on the
path and `mypy` then has two names for one file.

Two settings and one empty file fix all of it, and the third setting is a separate judgement:
`agent_toolkit` ships no marker either, and it is annotated — `complete`, `resolve_config` and the
four rule scans all carry full signatures. `follow_untyped_imports` for that package alone reads
those real annotations. The alternative, `ignore_missing_imports`, makes the library's whole surface
`Any`, which is how a signature changing under a pinned branch becomes invisible here.

**Approach.** Create the empty `src/dataforce/py.typed`, add it to the wheel through
`[tool.hatch.build.targets.wheel]`, and in `[tool.mypy]` set `mypy_path = "src"` and
`explicit_package_bases = true`. Add one override block for `agent_toolkit.*` with
`follow_untyped_imports = true`, carrying the reason above as a comment in the style the rest of
`pyproject.toml` is written in.

**Acceptance criteria.** `mypy --strict src/dataforce` reports no `import-untyped` error and no
`Source file found twice`. It reports 13 errors: four `attr-defined` in `edge/cli.py` and nine
`empty-body`. Every one of the 13 is closed by T2 or T3, and no `misc` `Class cannot subclass`
error remains — those were the checker not seeing the base.

**Source.** § *Testing Strategy*; `E-1` — a rule whose check does not read the code is not enforced.

**Verify.** `uv run mypy --strict src/dataforce 2>&1 | tail -1` reads `Found 13 errors in 6 files`;
`uv run mypy --strict src/dataforce 2>&1 | grep -c import-untyped` reads `0`.

**Out of scope.** The 13 findings themselves.

### T2 · Delete the CLI and its console script

**Goal.** Nothing in the tree imports a module the restructure deleted.

**Context.** `edge/cli.py` calls `open_parts()` from `dataforce.services.text2text` and
`personal_data_scan` / `duplicate_groups` from `dataforce.modalities.text2text.data_quality`. None
of the three exists: the first was `parts.py`, deleted as an invented factory, and the other two were
module-level functions before the checks became classes with sockets. `import dataforce.edge.cli`
raises `ImportError`, and `pyproject.toml` declares that module as the `dataforce` console script,
so the installed entry point is broken. No test, no document and no route reaches it.

**Approach.** Delete the file and the `[project.scripts]` table. `T-5`: nothing gets harder without
it — the four endpoints are how every part is driven, and a JSONL runner over `services/` is a
second caller for every part to keep in step, which is a thing to add when a file-shaped job exists
and not before (`T-1`, `T-3`).

**Acceptance criteria.** No `dataforce.edge.cli`, no `[project.scripts]`, and `mypy` reports four
fewer errors. `uv run python -c "import dataforce.edge.main"` succeeds.

**Source.** § *Files* — the `edge/cli.py` row; `T-1`, `T-5`.

**Verify.** `uv run mypy --strict src/dataforce 2>&1 | grep -c cli` reads `0`.

**Blocked by.** T1 — before it, `mypy` cannot see that the imports are dead.

### T3 · No stub lies to the type checker

**Goal.** Every method with no body says which kind of nothing it is, and `make check` is green.

**Context.** Nine `pass` bodies remain, and they are three different situations wearing one face.

- Two are **undecided by declaration**, and `spec.md` § *Out of Scope* says so:
  `DuplicateDataChecking.duplicate_groups` and `ToolDecisionDuplicateChecking.embedding`. No task in
  this plan writes either, so the gate cannot go green by waiting for one.
- Seven are **pending**, each with a task below: `LLMPrediction.verdict`, `SFTPrediction.verdict`,
  `ToolDecisionPersonalChecking.scan` and `.review_text`, `ToolDecisionLLMPrediction.predict` and
  `.rendered_prompt`, `ToolDecisionSFTPrediction.predict`.
- The abstract ones are already right and `mypy` never complained: an `@abstractmethod` with `pass`
  is a socket, not an empty body.

`exact_match_consensus` and `llm_judge_consensus` also have `pass` bodies and produce no error,
because `None` satisfies `str | None`. They are pending all the same, and T10 writes them.

**Approach.** Three answers, one per situation. `duplicate_groups` returns `DuplicateGroups | None`
and returns `None` — the pattern its own sibling already states in
`common_abnormal_checking.py`: *"it returns None rather than an invented shape because a placeholder
shape is the one thing a caller would start depending on."* Delete
`ToolDecisionDuplicateChecking.embedding`, whose override adds nothing to the abstract method it
covers, leaving the class abstract and uninstantiated, which it already is — `duplicate_report`
answers `None` without it. Give each of the seven pending bodies `raise NotImplementedError`.

The cost of the seven, stated: a route that reached a `pass` used to answer `null` and now answers
500 until its body lands. That is the honest report of the same state, and it is why
`personal_data` is typed with a `| None` today — T9 removes that once T7 lands.

**Acceptance criteria.** `make check` is green. No method in `src/` has a `pass` body except an
`@abstractmethod`. `spec.md` § *Files* no longer lists `embedding` as a body to write.

**Source.** § *Out of Scope*; Decision 7 — an undecided shape answers `None` at 200, it does not
invent one.

**Verify.** `make check`.

**Out of scope.** Any real body. Seven of these are removed again, one per task, by T7, T10 and T11.

**Blocked by.** T1.

### T4 · Five tags, one case, and the guard that reads them

**Goal.** Every module's first word is one of `H-8`'s five tags, and a test fails on the sixth.

**Context.** `H-8` names five: `shape`, `logic`, `facade`, `adapter`, `wiring`, and gives the
import direction as a table — the fourth column is what `E-1` is supposed to enforce. The tree
writes seven things instead. Four modules open with `DEFINITION ·` — `errors.py` and the three
`schema.py` — which is not one of the five and is the tag the deleted spec used. `edge/cli.py` and
`tests/guards/tree.py` open with `TOOL ·`, also not one of the five; T2 deletes the first and the
second is under `tests/`, which no guard scans. `modalities/text2text/__init__.py` and
`edge/__init__.py` write `façade`, with the cedilla `H-8` explicitly forbids because the tag is read
by a machine. And the case is split down the middle: `ADAPTER`, `LOGIC` and `WIRING` shout while
every `facade` whispers.

Nothing checks any of this, which is the actual finding. `E-1` exists because the IDE encourages the
import that breaks the direction, and this restructure proved the point twice: `services/` imported
`edge/store` — logic reaching for an adapter — and was fixed by hand, and `edge/cli.py` has been
importing a deleted module for four commits. `tests/guards/tree.py` already has every part such a
guard needs: `modules_in`, `imports`, `not_exempt`, and the exemption grammar.

While the file is open: `errors.py` cites `Requirement 43`, which in *this* spec is the page's step 8
and has nothing to do with it. The citation is left over from the deleted spec, and `8a00fdb` is the
commit that made the rule *cite a section, not a number*.

**Approach.** Rewrite the seven wrong tags as the five, in one case — `DEFINITION` becomes `shape`
for all four, `façade` loses the cedilla — and fix `errors.py`'s citation to name a section. Then one
guard in `tests/guards/`, an AST scan over `modules_in()`: every module's docstring opens with one
of the five, and no module imports across the direction `H-8`'s table forbids. Prove it red against
a synthetic violation the way `test_toolkit_not_reimplemented.py` does — a `logic` module importing
an `adapter`, and a module tagged `helper`.

**Acceptance criteria.** Every module under `src/dataforce` opens with one of the five tags in one
case. The guard rejects a synthetic module tagged with a sixth word, and a synthetic `logic` module
importing an `adapter`. `make check` green.

**Source.** `AGENTS.md` `H-8` and its import table, `E-1`; § *Files* — the
`modalities/text2text/__init__.py` row. **Sourced from `AGENTS.md`, not from `spec.md`:** the
cedilla is the spec's, the other six tags and the guard are the rule's.

**Verify.** `uv run pytest tests/guards -q`; then add `from dataforce.edge.store import stored_row`
to `services/tool_decision/data_quality.py`, confirm the guard fails, and revert.

**Out of scope.** `tests/guards/tree.py`'s own `TOOL ·` tag. `H-8` is a rule about the package;
widening a guard to scan the guards is a second decision.

### T5 · The catalog rendering is pinned

**Goal.** The text a reviewer and a juror both read cannot change without a test saying so.

**Context.** `profile/tool_decision/utils.py` is the one module in this feature that is finished, and
it is the only code both halves of the flow depend on: Decision 8 puts one renderer behind both
parts so a reviewer and a juror cannot disagree about the catalog they read. Its docstring states
two rules the schema does not — a required param carrying a `default` is optional and out of
`require:`, and an object param's subfields move to their own lines the moment one carries a type, a
description, an enum or a default — and § *Invariants* adds a third: property order is preserved, so
text re-rendered from the same tools is byte-identical. Nothing tests any of them.

**Approach.** One test module, a hand-written `tools` array covering the two docstring rules and the
ordering, pinned against its expected rendering as a literal string.

**Acceptance criteria.** The rendering is asserted character for character. A required param with a
`default` appears unmarked and absent from `require:`. An object whose subfields are plain strings
renders inline as `Gồm các trường:`; one subfield gaining an enum moves them all to their own lines.
Two tools render in the order given, not sorted.

**Source.** § *Testing Strategy* — *"`openai_tool_format_to_text` pinned against its known
rendering"*; § *Invariants*, the property-order line; Decision 8.

**Verify.** `uv run pytest tests/ -q -k catalog`.

**Out of scope.** Changing the renderer. If a rule in the docstring turns out to be wrong, that is a
finding to report, not a rendering to adjust so the test passes.

---

## Phase 1 · The scan answers

**Goal.** `POST .../data-quality/personal-data` returns a real `PersonalDataDetected` over a
hand-written sample, and `.../personal-data/replace` the copy over the spans a reviewer handed
back.

### T6 · What layer two is asked

**Goal.** The prompt layer two runs on exists, and it belongs to the task.

**Context.** `config/prompts/profiles/tool_decision/personal_data.txt` is the one file § *Files*
lists as new. Layer two is the precision gate: Requirement 8 says only a value the model confirms is
replaced, and Requirement 26's error path says a value it returns that is not character-for-character
one of the candidates is discarded. So what the model is asked is *confirm these*, never *find
some* — the finding is layer one's, and a model asked to find would return candidates nothing can
check against an offset.

`tool_prediction.txt` is the model to follow: it states the output shape before the inputs, forbids
prose around the JSON, and says what each key is for.

**Approach.** One prompt, handed the review text and layer one's candidates, returning one JSON
object whose only content is which candidates are real. No markdown fence, no prose. Its placeholders
follow `tool_prediction.txt`'s `{{name}}` spelling and include the language the request declared
(Decision 17).

**Acceptance criteria.** The file exists, asks for confirmation of a given list, and states its output
shape as strict JSON. A value not in the candidate list is out of contract by the prompt's own words,
not only by the code that discards it.

**Source.** Requirements 7, 8 and 26; § *Files*; Decision 17.

**Out of scope.** The code that renders or sends it — that is T7.

### T7 · `review_text`, and the scan's two layers

**Goal.** `ToolDecisionPersonalChecking.scan` answers, and every offset it returns slices back to the
value it was made from.

**Context.** This is the task the spec spends most of its Requirements on — 5 to 14 — and Decision 4
is why it is one method: the composition begins by deciding what text to scan, and that is the
task's answer, not the modality's. Two bodies to write, and the order of operations is the whole
difficulty.

`review_text` builds the one string every offset indexes: the turns, the tool catalog and the label
together (Requirement 6), because an argument value in a tool call is where a phone number actually
sits. It is built once and nothing afterwards may reorder or reflow it — § *Invariants* pins
that, and Decision 6 is why `redacted_text` is a second string rather than a rewrite: replacing in
place would invalidate every span on the same object.

`detect` runs layer one, then layer two, then numbers the placeholders. Layer one is
`agent_toolkit.string_utils`' four scans in the declared order email, phone, OTP, name, each handed
the declared language (Requirement 7) — they take `language: str = "vi"`, and Decision 17 says the
request declares it, not the record. Each returns `list[str]`: **values, not offsets**, so the offsets are this code's
to find, and a value occurring twice is two spans with one placeholder (Requirement 10). Layer two
is the model pass and it may not raise — a failed call confirms none (Requirement 8), and the
failure is a structured event on stdout, never a log file (`H-6`).

The overlap this order exists to resolve is real and already drawn on the page: a phone-shaped digit
run inside an email address. Email is scanned first, so it keeps the value, and the phone span
falling inside it is dropped by Requirement 11's outermost rule.

**Approach.** `review_text` first, and separately: it is the frame of reference for everything else
and is a rule worth naming (Decision 4's second half). Then `detect`, in the order the requirements
are numbered — candidates, confirmation, placeholder map keyed by value, spans. `redacted_text`
longest value first (Requirement 12) and `outcome` (Requirement 13) are the second call's, over the
spans a reviewer handed back (Decision 19). `resolve_config` reads the
model's config by name and whatever `VerifierModelConfig` carries replaces what the file said —
Decision 10, and the merge is the library's, so none is written here.

**Acceptance criteria.** `detect` returns a `PersonalDataDetected` where: every span slices back to
its value; one value has one placeholder wherever it appears; no span survives inside a longer one.
`replace` over those spans returns a `PersonalDataReplaced` where `redacted_text` is `None` where
nothing was rewritten and otherwise holds no claimed value verbatim, and `outcome` is `reported`,
`redacted` or `withheld` by Requirement 13's three cases. A layer-two call that raises yields an
answer, not an exception.

**Source.** Requirements 5–14, 26; Decisions 4, 6, 10, 17; § *Invariants*, the first four lines.

**Verify.** `make check`. The proof is T8; this task's own check is that the endpoint answers a scan
instead of 500.

**Out of scope.** The tests (T8) and the response type (T9). Layer two's prompt text (T6).

**Blocked by.** T6 — layer two has nothing to send without it.

### T8 · The scan's tests

**Goal.** Every rule in Requirements 5–14 fails a test when it is broken.

**Context.** § *Testing Strategy* names five, and they are the five that took a wrong answer at
some point while the page was being built: overlap resolution picks the declared first scan; a value
said twice gets one placeholder; a span inside a longer span is dropped; every returned offset slices
back to its value; `redacted_text` replaces the longest value first.

The last one is the one that bites. A phone number inside an email, with the shorter value replaced
first, produces `minh<PHONE_1>@vd.vn` — a row that is neither redacted nor intact. The page draws
this case today as a conflict it cannot resolve; a test is what keeps the *scan's* half of it from
regressing.

**Approach.** One hand-written sample with the overlap in it, layer two stubbed — `conftest.py`
already refuses a real endpoint to every test. No corpus, no fixture file.

**Acceptance criteria.** Five tests, one per bullet. Each observed to fail when the rule it names is
inverted.

**Source.** § *Testing Strategy*, the first bullet.

**Verify.** `uv run pytest tests/ -q -k personal_data`.

**Blocked by.** T7.

### T9 · The scan endpoint stops answering `None`

**Goal.** The route's return type says what the route returns.

**Context.** `personal_data` is typed with a `| None`, and its docstring says why: *"`None` for as
long as the body is `pass`. The type tightens when the body lands."* The body lands in T7.
§ *Invariants* asks that no endpoint's response mention a part it does not own, and a `| None` that
exists because of a missing body is the response model documenting the schedule.

**Acceptance criteria.** `personal_data` returns `PersonalDataDetected`, and the second route
`.../personal-data/replace` returns `PersonalDataReplaced` — the part is two calls with a human
between them (Decision 19). Neither route's OpenAPI schema holds a `null` branch. `mypy --strict`
green.

**Source.** Requirement 32; § *Invariants*.

**Verify.** `make check`; `uv run python -c "from dataforce.edge.main import app; import json;
print(json.dumps(app.openapi()['paths']['/text2text/tool-decision/data-quality/personal-data'],
indent=1))"`.

**Blocked by.** T7.

---

## Phase 2 · The panel answers

**Goal.** `POST .../ai-review` returns both verdicts against stubbed model calls.

### T10 · The three shared bodies in the modality

**Goal.** A panel of N reaches one answer, or defensibly none.

**Context.** § *Design* says exactly which bodies belong in `modalities/` and why: `verdict`,
`exact_match_consensus` and `llm_judge_consensus`, *"because a strict majority is arithmetic and
does not change with the question being asked."* `SFTPrediction.verdict` is the fourth, on the same
grounds — comparing two labels is not a task's answer.

Three rules that are easy to write slightly wrong. `exact_match_consensus` is a **strict majority,
never a mode** (Requirement 21): two of three is an answer, two of four is `None`. It compares
answers as canonical text — one whitespace and one key ordering — so two answers that mean the same
count as one, and `agent_toolkit.string_utils.normalize_text` is the library's, not this code's
(`I6`). `llm_judge_consensus` runs *only* where the exact match returned `None`, reads the answers
and not the conversation (Decision 9 — otherwise it is an N+1th juror whose single vote breaks every
tie), and can only return a string some juror wrote (Requirement 22). `verdict` counts agreement
over the votes that came back, never over the panel that was asked: a juror that failed is absent,
and every juror failing is a verdict with no votes, `label_agreement` 0.0 and `consensus` `None` —
a valid answer, not an exception.

Absent is not silent. Phase 1 set the pattern and left the writer behind it: `edge/events.py`
turns a log record into one JSON object per line on stdout, and each asking class writes
`logger.warning("<step>_failed", extra={"model": ..., "error": f"{type(e).__name__}: {e}"})`
outside the answer it returns (`H-6`). A juror that fails or answers the wrong shape is one such
event naming the juror, on the same two keys, so a panel that quietly shrank is readable from the
output rather than only from `label_agreement`.

**Acceptance criteria.** `verdict` calls `predict` once. `label_agreement` is over returned votes.
`exact_match_consensus` returns only a strict majority. `llm_judge_consensus` is not called when the
exact match found one, and returns only an answer some juror gave. `SFTPrediction.verdict` compares
two labels and asks no model.

**Source.** Requirements 19–23; Decisions 9, 11, 12; § *Design* — *Where a body lands*, *AI review*;
§ *Error Behavior*, the first two bullets.

**Verify.** `make check`. The proof is T12.

**Out of scope.** Anything that renders a prompt or makes a call. Those are the profile's, and
`jurors` already has its body.

### T11 · The prompt, and the two `predict`s

**Goal.** Each juror is asked the sample's own question, once, and its answer is read as written.

**Context.** Requirement 24 puts the prompt inside `predict`, in the profile, so the prompt and the
shape it must return are read in one file. Four slots:
`{{tool_descriptions}}` from `openai_tool_format_to_text(sample["tools"])` — T5 pins that rendering
— `{{conversation_history}}` with the turns before the last, `{{user_message}}` with the last one,
and `{{language}}` from the language the request declared. **The sample's label is not among them**
(Decision 12): a model shown the label answers about the label.

`{{language}}` has no source yet, and this task is where that is settled. Decision 17 makes the
language a declaration about the request rather than a key of the record: `ScanRequest` carries it,
`ReviewRequest` does not, and `Sample` never did. So either `ReviewRequest` grows
`language: Language = "vi"` — symmetric with the scan, and one more thing every caller may declare
— or the slot goes and the prompt asks in one language. Whichever way, the signatures change:
`predict(turns, label)` and `rendered_prompt(turns, tools)` carry no language today, and
`tool_decision_llm_predict` passes the turns and the label and nothing else. `rendered_prompt` also
needs `tools`, which `verdict(turns, label)` never receives — the same threading settles both.

The answer comes back as one JSON object, `{reason, label}`. `label` stays a **string** — the
tool-call array as text (Requirement 25, Decision 11) — and nothing turns it into a structure;
`model_name` is set by the caller, the only party that knows which juror it asked. An answer that
does not parse, or is missing either key, is a juror that did not answer: no vote, and never an
empty-label vote. `agent_toolkit.llm.complete` is the call and `read_txt` reads the prompt file;
neither has a twin here (`I6`).

**Approach.** `rendered_prompt` fills the four slots and nothing else. `predict` renders once per
juror, calls each independently, and drops the ones that failed or did not parse. `resolve_config`
by model name, with whatever `LLMModelConfig` carries replacing the file (Decision 10). Where the
prompt path is read, it is the profile's own: `config/prompts/profiles/tool_decision/`.

**Acceptance criteria.** `rendered_prompt` leaves no `{{…}}` unfilled and contains the sample's label
nowhere. `predict` returns one vote per juror that answered, each carrying the `model_name` of the
juror asked. A juror whose call raises, or whose answer is unparseable, is absent from the result.
`ToolDecisionSFTPrediction.predict` returns one `SFTReviewerVerdict`.

**Source.** Requirements 18, 19, 24, 25, 26; Decisions 10, 11, 12, 17.

**Verify.** `make check`.

**Out of scope.** `verdict` and the two consensus rules — T10.

**Blocked by.** T5, so the catalog rendering both halves depend on is already pinned.

**What it settled, and what it left.** `ReviewRequest` grew `language: Language = "vi"`, symmetric
with the scan; the parts take it as text, because only the scans key a table by it. The label came
off both `predict`s rather than being passed and unread — Decision 12 is structural now, and
Requirements 19, 23 and 24 were rewritten to match.

The judge was built here as a fourth request key and then taken back out, which is worth recording
because the second answer is the better one. An answer to *this* task is a tool-call array, so
sameness is a rule: `ToolDecisionLLMPrediction.normalize_prediction` matches the calls in one
answer against the calls in another. It answers a third socket beside `predict` and
`judge_prediction` -- declared in the modality and left undefined there, because
`modalities/text2text/` serves any text2text task and cannot know a tool call exists. Reading a
juror's text back into those calls turned out to be the reverse of a rendering this profile already
owns, so it landed beside it as `utils.text_to_openai_tool_format`: one definition of what a call
is, in the file that already holds the one definition of what a tool looks like (Decision 8). Most of what a judge was going to be paid to resolve was never a
disagreement — two jurors spelling one answer differently — and what is left is two genuinely
different calls, where Decision 9 already says a model would only be casting the deciding vote
blind. So `judge_prediction` stays a socket for a task whose answers can only be compared as
meaning, this profile answers `None`, and no request key names a judge (Decision 20).

`ToolDecisionSFTPrediction.predict` is the one half that did not land: nothing says where its
`confidence` comes from, so § *Open* now carries that question and the body still raises.

### T12 · The panel's tests

**Goal.** The three arithmetic rules and the failure paths are proved without a model call.

**Context.** § *Testing Strategy* names three: the consensus cases, `verdict` with a stubbed
`predict`, and a failing juror not counted as agreement. The last is the one worth writing first — a
juror that fails must be *absent*, and the cheapest wrong implementation counts it as a vote with an
empty label, which then agrees with nothing and quietly drags `label_agreement` down.

**Acceptance criteria.** Two of three matching gives that answer; two-two gives `None`; a mode that
is not a strict majority gives `None`. `verdict` over a stubbed `predict` counts agreement over
returned votes only. Every juror failing gives a verdict with no votes, `0.0` and `None`, and one
event per failed juror on stdout, read back through `capsys` as the scan's two failure tests
already do. The judge fallback is not called when the exact match answered, and a judge returning a
string no juror wrote is refused.

**Source.** § *Testing Strategy*, bullets two and three; § *Error Behavior*.

**Verify.** `uv run pytest tests/ -q -k ai_review`.

**Blocked by.** T10, T11.

---

## Phase 3 · Every endpoint is drivable alone

**Goal.** Each of the seven routes is exercised by its own arguments, and one record makes the
round trip.

### T13 · Each endpoint through its own arguments

**Goal.** Seven routes, seven tests, and no fixture that threads one payload through more than one
of them.

**Context.** Requirement 1 and Decision 2 are the whole point of the shape, and a test suite is the
one place they can be broken silently: a fixture that posts a scan, keeps the response and feeds it
to `/ai-review` would pass while making the parts undrivable apart, which is what
*"each callable without the others"* forbids. § *Testing Strategy* says it in the negative — *"called
with nothing but its own arguments — no fixture threads one payload through several of them."*

Requirement 41 is the same rule on the page: step 6 reads the sample, not step 5.

There are also three `no-any-return` findings in the router that T1 will have surfaced —
`models()`, `duplicate()` and `abnormal()` return what a service handed back without the checker
being able to see its type. They are the router's own, and this is the task that owns that file.

**Approach.** `TestClient`, model calls stubbed, one test per route: the page, `/models`, the four
data-quality routes, `/ai-review`, `/records`. An unserved model name is refused with 422 naming it
and the served list (Requirement 29), and `GET /models` is the `config/model/` listing with
`DATAFORCE_MODEL_DIR` pointed at a temporary directory the test wrote — Decision 13, the directory
*is* the list.

`.../data-quality/personal-data/replace` is the fourth, and it is the one route that asks no model:
nothing on it can be refused for a name this deployment does not serve, and its body is the
`PersonalDataDetected` the detect route answered — the same shape out and back in (Decision 19).
Posting it is not threading a payload between two parts: it is one part's second call, which is
what Requirement 1 distinguishes. The scan route's own test posts `language` and `verifier_model`
as keys of the request rather than of the sample.

**Acceptance criteria.** Every route has a test whose body it is the only route in. `duplicate` and
`abnormal` answer `null` at 200. An unserved name is 422 before any model is called, and the
replace route answers without a model name at all. `mypy --strict` reports no `no-any-return`.

**Source.** Requirements 27–36, 41; Decisions 2, 13; § *Testing Strategy*, bullet five.

**Verify.** `uv run pytest tests/ -q -k endpoint`; `make check`.

**Out of scope.** The record round trip — T14. The page: § *Testing Strategy* is explicit that no
test drives it and a browser is the check.

**Blocked by.** T9, T12.

### T14 · The record's round trip

**Goal.** A record posted comes back equal, and one that has not been redacted does not get stored.

**Context.** `services/tool_decision/human_review.py` is written and `edge/store/records.py` is
written, and nothing has run the two against each other in this repository — the round trip was
checked once by hand against SQLite while the page was being built, and left no test behind.

Requirement 35 gives the store two refusals: a record with no redacted form, and a row that still
holds a value its own scan says it replaced. The first is unimplemented — nothing in
`human_review.py` reads the field at all — and the field it reads is `personal_data.outcome`, so
`reported` is the value that refuses. The second is written: `unreplaced_values` reads only the
three `new_` keys,
and § *Design* says why the check cannot be wider: *"the originals hold raw content on purpose and
checking the whole record would fail by design."* The consequence is the one the spec states once
and this test should not re-litigate — the row holds the personal data verbatim, so the redaction
protects a reader of the `new_` keys and not the database.

**Acceptance criteria.** `POST .../records` then `latest_row` returns an equal document. A second
post under one id replaces the row rather than adding one. A record whose `personal_data.outcome`
is `reported` is 422 and is not written. A record whose `new_messages` still holds a replaced value
is 422 and is not written. A record with no id is 422.

`span_values` needs nothing changed for the split: it reads `review_text` and `spans`, and both are
on `PersonalDataDetected`. What the record's `personal_data` key holds is the two answers together —
the page posts the detect answer merged with the replace answer — and no shape declares that
container. Undecided, and this task does not decide it: the key is typed `Mapping[str, Any] | None`
and the two refusals read the three fields they name.

**Source.** Requirement 35; § *Design* — *What the row holds*; § *Testing Strategy*, bullet six;
§ *Error Behavior*, the `POST .../records` line.

**Verify.** `uv run pytest tests/ -q -k record`.

**Out of scope.** The store's schema management. § *Out of Scope* defers Alembic and migrations by
decision; `create_all` against a temporary SQLite file is what this test uses.

**Blocked by.** T13.

---

## Not in this plan, and why

- **`DuplicateDataChecking.duplicate_groups` and `CommonAbnormalChecking.check_verdict`.** Neither
  declares a shape and § *Out of Scope* invents none. T3 makes both answer `None` by declaration
  rather than by an empty body.
- **`ToolDecisionDuplicateChecking.embedding`.** § *Files* lists it, and it is a body for nothing
  while `duplicate_groups` is undecided — its only caller. T3 deletes the override and retires that
  half of the row (`T-1`).
- **The two redaction conflicts the page draws.** Unticking a span leaves its value in the row;
  unticking a value that another kept value sits inside cuts it in half. § *Design* records both and
  says *"which of the two wins is not decided"*, so no task here decides it. The page shows them
  beside the reviewer who caused them, which is the behaviour that exists.
- **The finetuned reviewer's own answer.** `SFTReviewerVerdict` carries a `confidence`,
  `tool_prediction.txt` asks for none, and `complete` answers with text and no logprobs — so T11
  left `ToolDecisionSFTPrediction.predict` raising rather than inventing a number, and § *Open*
  states the two ways out. `SFTPrediction.verdict` was written and then withdrawn with it: T10
  asked for it on the grounds that *"comparing two labels is not a task's answer"*, and that turned
  out to be wrong -- comparing two answers means knowing what an answer is made of, which is
  exactly what the modality may not know. It lands in the profile when the rest of this reviewer's
  half does.
- **The page's own tests.** § *Testing Strategy*: *"No test drives the page. A browser is the check."*
- **Auth, batching, a corpus, and which models a deployment picks.** § *Out of Scope*.
