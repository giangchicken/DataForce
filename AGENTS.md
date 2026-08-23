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
  `read_manifest`, `catalog_to_tools`, `create_training_example`.
- **A one-word abbreviation of the concept.** Too short to mean anything on its own

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

# Design Principles
 
Rules for the shape of code. Numbered `P1`–`P28` so they can be cited in review; they do not
renumber the existing `§` sections.
 
Each is a statement someone can point at and say whether a given change holds it. A principle that
cannot be pointed at is a preference, and preferences go in a PR comment, not here.
 
---
 
## Vocabulary
 
These seven words have one meaning each. Use them; do not use the substitutes.
 
| Term | Meaning | Do not say |
|---|---|---|
| **Module** | Anything with an interface and an implementation. Scale-agnostic on purpose: a function, a class, a package, a slice spanning tiers. | unit, component, service |
| **Interface** | Everything a caller must know to use it correctly — the type signature, plus invariants, ordering constraints, error modes, required configuration, performance characteristics. | API, signature |
| **Depth** | Leverage at the interface: how much behaviour a caller or a test can exercise per unit of interface it must learn. Deep = a lot of behaviour behind a small interface. Shallow = the interface is nearly as complex as the implementation. | — |
| **Seam** | A place where behaviour can be altered without editing in that place. It is the *location* of an interface; where to put it is a separate decision from what goes behind it. | boundary |
| **Adapter** | A concrete thing satisfying an interface at a seam. A role, not a substance — an in-memory fake and a Postgres repository are both adapters. | — |
| **Leverage** | What callers get from depth: more capability per unit of interface learned. | — |
| **Locality** | What maintainers get from depth: change, bugs and verification concentrate in one place. Fix once, fixed everywhere. | — |
 
**P1.** Depth is not the ratio of implementation lines to interface lines. That metric rewards padding
the implementation. Depth is leverage at the interface.
 
**P2.** Depth is a property of the interface, not of the implementation. A deep module may be built
internally from small swappable parts; they do not surface to callers. A module may have internal seams
its own tests use and one external seam at its interface.
 
**P3.** A design discussion that produces the words *component*, *service* or *boundary* has not
reached a design yet. Restate it in the table above before proceeding.
 
---
 
## Dependency direction
 
**P4.** Dependencies point inward, toward the domain. The domain kernel depends on nothing in this
repository. Adapters depend on the domain. The domain never depends on an adapter.
 
**P5.** **An abstraction belongs to the layer that consumes it, not to the layer that implements it.**
If the domain takes `X` as a parameter, `X` is defined in the domain — even when the only thing that
can build an `X` is an adapter. Ports live inside; implementations live outside.
 
**P6.** There is exactly one composition root. It is the only module permitted to name a concrete
adapter, read configuration, and wire the two together. Nothing else constructs its own dependencies.
 
**P7.** Adapter packages are named for the kind of I/O they perform (`http`, `persistence`, `config`),
never for one of the transports that happens to use them. A package named for the HTTP layer must not
hold the code the CLI also needs.
 
**P8.** The direction in P4 is enforced by a test, not by review. An import that crosses inward-out
fails CI.
 
---
 
## Module shape
 
**P9. The deletion test.** Before adding a module, imagine deleting it. If complexity vanishes, it was
a pass-through — do not add it. If the same complexity reappears across N callers, it earns its keep.
Record the answer in the PR description.
 
**P10. One adapter means a hypothetical seam; two adapters mean a real one.** Do not cut a seam until
something actually varies across it. A single-adapter seam is indirection with a nicer name. A test
fake counts as a second adapter only when the seam is genuinely exercised through it.
 
**P11.** A port with zero adapters is deleted, not kept for later. The protocol that would sit behind
it is enough of a seam for a future implementer.
 
**P12. The interface is the test surface.** Callers and tests cross the same seam. Wanting to test past
the interface means the module is the wrong shape — change the shape, do not reach through it.
 
**P13.** Expose narrow, caller-specific interfaces. A module must not depend on members it does not
call. Where one protocol serves many callers with disjoint needs, the members each caller actually
uses are written down; a protocol nobody can split is a protocol nobody has measured.
 
**P14.** Every module's precondition is part of its interface (see the table above), so it is stated in
the same place as the signature — in the code, next to the thing it constrains. A precondition that
lives only in a design document is an undocumented interface.
 
**P15.** Modules are grouped by what they are about, not by what they are made of. Feature and domain
first; technical kind second. This applies to the adapter layer too — the split there is by kind of
I/O (P7), which *is* what those modules are about.
 
---
 
## Naming
 
**P16.** A name states the object it holds or the value it returns, never the operation that produced
it. A bare verb that names no object (`load`, `process`, `handle`) is not a name.
 
**P17.** A property so broad that everything in the system is an instance of it (`validity`, `check`,
`manager`) is not a name either. Name the specific thing being checked or held.
 
**P18.** `utils`, `helpers`, `common`, `core`, `misc`, `shared` and `base` are forbidden as module or
package names. They mean "not elsewhere", which is not a meaning. Name the module for its contents.
 
**P19.** A package containing one useful module *is* that module. Flatten it.
 
**P20.** Names are not reused across levels: no function shares a name with a phase, a stage or a
module it lives in.
 
---
 
## Errors, state and flow
 
**P21.** Failure that concerns one item is data on that item, not an exception. Processing continues;
the failure travels with the item and is visible at the end.
 
**P22.** Failure that concerns the configuration is an exception, raised at startup before the first
item is read. These are the only exceptions this codebase defines.
 
**P23.** Nothing is silently removed. Exclusion is a value on the item, and an excluded item travels
the whole flow carrying why. Where this holds, conservation is structurally true and needs no
assertion.
 
**P24.** Each piece of derived state has exactly one writer. Two writers for one key is a merge
conflict waiting for production.
 
**P25.** Processes hold no state between requests. Clocks, identifiers, file paths and connections are
supplied by the composition root, never reached for from inside.
 
---
 
## Simplicity, configuration, and operations
 
**P26.** Build what is asked for. No speculative seams, no configuration switch with one setting, no
second reader for a format that has no caller. Flexibility nobody asked for is a cost with no payer.
 
**P27.** Behavioural constants live in configuration, not in code. Logic contains no numeric literal
other than the ones intrinsic to the algorithm. Changing behaviour is then a committed, attributable
edit whose digest a run records.
 
**P28.** Identity comes from a declaration, never from a class body. What a thing is called is data;
code reads it.
 
**P29.** Development, test and production run the same implementations of every dependency. Where a
lighter substitute is used for local convenience, at least one test suite runs against the production
implementation, and the difference is written down as a known risk rather than assumed away.
 
**P30.** Structured logging is part of the architecture, not added after the first incident. Every unit
of work emits a line carrying the run identifier, the item identifier and the stage, so a long run can
be observed while it is running and not only audited after it stops. Logging is I/O, so it happens at
the edge (P4): the domain returns what happened, the edge writes it.
 
---
 
## Enforcement
 
**P31.** Every principle above that can be checked mechanically is checked mechanically — as an AST
scan, an import-graph rule or a model-introspection test. A principle enforced only by review is a
principle that survives until the first deadline.
 
**P32.** These checks are written before the code they constrain, and each is proved against a
synthetic violation so it is known to fail. A guard written afterwards is how a codebase acquires the
thing the guard forbids.
 
**P33.** Where a design document states a fact the code also states — a stage list, a phase order, a
set of names — a test compares the two and fails on drift. A document nothing checks becomes fiction
without anyone noticing.
