# Conventions

Rules for anyone — person or agent — writing code here. General enough to copy into
another repo. Every rule has a test you can apply without asking me.

## 1 · Think before coding

State your assumptions. If two readings of the request produce different code, say both
and pick one out loud — do not pick silently. If something is unclear, name what is
confusing and ask. If a simpler approach exists, say so before writing the complex one.
Push back when warranted; a reason I can check beats agreement.

## 2 · Minimum code that solves the problem

Nothing speculative. No features beyond what was asked. No abstraction for a single use.
No flexibility or configurability that was not requested. No error handling for a state
no caller can reach. If you wrote 200 lines and it could be 50, rewrite it.

The check: *would a senior engineer call this overcomplicated?* If yes, simplify.

## 3 · Surgical changes

Touch only what the request requires. Do not improve adjacent code, comments, or
formatting. Do not refactor what is not broken. Match the existing style even where you
would do it differently.

Remove imports, variables and functions that **your** change orphaned. Leave
pre-existing dead code alone — mention it instead.

The test: every changed line traces to the request.

## 4 · When to create a function

**Create one when it has two or more callers, or when it holds a decision a reader needs
named — a check, a branch, a raise, a rule.**

One expression with one caller is not a function. Inline it. A name that only forwards
an argument costs a file to open and returns nothing for it.

These are worth a name at a single caller, and nothing else is:

| Reason | Why the name earns its keep |
|---|---|
| Interface member | a protocol / ABC / base-class method — deleting it deletes the polymorphism |
| Registered by name | a callback or check whose name appears in output, config, or metrics |
| Cached | `lru_cache` and friends — the decorator *is* the function |
| Closure factory | it returns a function; that is not inlinable |
| Not one expression | a loop, a `try/except`, a generator, an early return |
| A test calls it directly | the behaviour is proved through this name |

Splitting one long function into named steps is allowed and often right — but each step
must be nameable as a *result*, not as "part 2 of the thing above".

## 5 · How to name things

**A name states what it returns, not the operation that produced it, and is long enough
to be unambiguous read alone at the call site.**

Three ways a name fails:

- **A bare operation names no object.** `of`, `parse`, `load`, `render`, `adapt`,
  `measure`, `export`, `embed`, `drift` — *parse what, into what?* Name the result:
  `read_manifest`, `catalog_to_tools`, `training_example`.
- **A one-word abbreviation of the concept.** Too short to mean anything on its own:

  | Don't | Do | Because it returns |
  |---|---|---|
  | `_leaves` | `leaf_values` | the leaf `(path, value)` pairs of a nested mapping |
  | `_turn` | `turn_text` | the text of the turn with this role |
  | `_percentile` | `value_at_quantile` | the value at a quantile, nearest-rank |
  | `_tools` | `answer_tools` | the set of tool names an answer means |
  | `_records` | `raw_with_records` | each raw item paired with the record it became |

- **A name shared with a step, stage, command, or table in the system.** It makes every
  sentence about the code ambiguous. If `load` is a pipeline stage, no function is called
  `load`.

Test: read the call site with nothing else on screen. If you cannot say what comes back,
the name is too short. A private `_` prefix is not an excuse — you still have to read it.

## 6 · How to organise files

**One module, one job, and the job is one of four kinds. The first word of the module
docstring says which:**

- `DEFINITION ·` one noun and its shape. Types, schemas, constants.
- `LOGIC ·` the conversions and computations over that noun.
- `STEP ·` serves exactly one step of the flow, and nothing else.
- `TOOL ·` not in the flow at all.

Then:

- **A shape is a shape; turning one thing into another is logic.** They change for
  different reasons, so they are different files: `schema.py` holds the types and
  schemas, `utils.py` holds the conversions over them. One of each per feature folder.
- **Group what changes together.** A reader follows a *path* — how does one input become
  one output. A file per concern charges ten navigations for one step. Everything one
  step does belongs in that step's module.
- **Do not split a module until a second consumer needs half of it.** A module with
  exactly one caller is that caller's code, not a module.
- **Do not make a consumer depend on what it does not use.** If twenty things live in one
  module and each consumer needs one, editing any of them puts every consumer in the
  blast radius. Split by the boundary along which consumers actually import.
- **Name a module for its noun or its job**, never `helpers.py`, `common.py`, `misc.py`.
  `utils.py` is the one allowed exception, and only for conversions over the shapes in
  the `schema.py` beside it.
- **Declare the import direction once and never reverse it.** Write it in the top-level
  package docstring — *these packages may import the engine; the engine may not import
  them* — and enforce it with a test, not with discipline.

## 7 · Verify, then report

Define success as something runnable before you start: *write the failing test, then make
it pass.* "Add validation" is not a goal; "invalid input raises, proved by a test" is.

- Add or change a test whenever behaviour changes. The test must prove the new behaviour,
  not merely execute the new code.
- Run the focused check, then the project's full check. Fix what they catch without
  growing scope.
- If behaviour must not change, say what proved that — a byte-identical output, an
  unchanged golden file, the same test count passing.
- Report what you ran and what it said. If something was skipped or is unverified, say
  so plainly. Never describe unrun code as working.

## 8 · When a rule is wrong

Rules lose to reasons. If a rule makes the code worse here, break it — and record the
break where the next reader will hit it: a sentence in the module docstring, and in the
spec if there is one. Two rules that disagree in one place is a fact about the design and
belongs written down, not resolved silently.

## 9 · Working agreement

- One task at a time. Finish it, verify it, commit it, then tell me to push. I push.
- Commit messages say **why**, not what the diff already shows: the alternative not
  taken, the cost paid, the rule deviated from.
- Never commit anything internal or personally identifying — this repo is public. No
  absolute paths, no credentials, no hostnames. Test fixtures are invented, never
  extracted from real data.
- Never write a live key or token into a file. Environment variables only.
