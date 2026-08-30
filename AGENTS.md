# Conventions

Rules for anyone — person or agent — writing code here. General enough to copy into another
repo. Every rule has a test you can apply without asking me. `§1`–`§9` are how you work;
`§10`–`§42` are the shape the code ends up in. One series, so a rule is cited by number alone.

## 1 · Think before you code

Say your assumptions out loud. If the request reads two ways, say both and pick one — never
pick silently. If something is unclear, name the confusing part and ask. If a simpler way
exists, say so before writing the complicated one. A reason I can check beats agreement.

## 2 · Write the least code that solves it

Nothing built for a future that has not arrived. No extra features. No abstraction for one use.
No settings nobody asked for. No error handling for a state no caller can reach. If you wrote
200 lines and 50 would do, write the 50.

**Check:** would a senior engineer call this overcomplicated? If yes, cut it.

## 3 · Change only what was asked

Touch what the request needs and nothing else. Do not tidy nearby code or refactor working code.
Match the style already there, even where you would write it differently. Delete what **your**
change left unused; leave pre-existing dead code alone and mention it instead.

**Check:** every changed line traces back to the request.

## 4 · When something deserves to be a function

**Make one when two or more places call it, or when it holds a decision a reader needs to see
named — a check, a branch, a raise, a rule.**

One expression with one caller is not a function. Inline it — a name that only forwards an
argument costs a file to open and gives back nothing. These earn a name at a single caller:

| Reason | Why the name pays for itself |
|---|---|
| Interface member | a protocol / ABC / base-class method — delete it and the polymorphism goes |
| Called by name | a callback or check whose name shows up in output, config or metrics |
| Cached | `lru_cache` and friends — the decorator *is* the function |
| Returns a function | a closure factory; you cannot inline that |
| More than one expression | a loop, a `try/except`, a generator, an early return |
| A test calls it | the behaviour is proved through this name |

Splitting a long function into named steps is often right — but each step must be nameable as a
**result**, not as "part 2 of the thing above".

## 5 · How to name things

**A name says what comes back, not what was done to get it, and is long enough to be clear read
alone at the call site.**

Four ways a name fails:

- **A bare verb names no object.** `of`, `parse`, `load`, `render`, `measure`, `export`, `embed`
  — *parse what, into what?* Name the result: `read_manifest`, `create_training_example`.
- **`_of` or `_for` standing in for the object.** They name the relation to an argument the
  signature already shows, leaving the noun in front free to be wrong without looking wrong.
  `cell_of(scores, floors)` returned a *bucket*; `share_of(record_id)` returned a position in
  `[0, 1)`. Fix the noun: `bucket_for`, `sampling_position`. Where the noun already is what comes
  back the suffix is harmless (`answer_id_for`) — so it is either redundant or hiding something.
- **A one-word shortening of the concept.** Too short to mean anything alone.
- **A word already used for a step, stage, command or table.** Every sentence about the code
  turns ambiguous. If `load` is a pipeline stage, no function is called `load`.

**Check:** read the call site with nothing else on screen. If you cannot say what comes back, the
name is too short — a leading `_` is no excuse. For the fourth failure, say the name and the
return type as one sentence: *`cell_of` returns a `str`* is not a sentence; *`placed_bucket`
returns a bucket* is.

**No guard enforces this section** — a check would have to allow `answer_id_for` and refuse
`share_of`, and that difference is a judgement, not a pattern. So `§5` is caught in review or it
is not caught. Read it twice.

## 6 · How to organise files

**One module, one job, and the job is one of five kinds. The first word of the module docstring
says which:**

- `DEFINITION ·` one noun and its shape. Types, schemas, constants.
- `LOGIC ·` the conversions and computations over that noun.
- `STEP ·` serves exactly one step of the flow, and nothing else.
- `TOOL ·` not in the flow at all.
- `façade ·` an `__init__.py` that re-exports and holds nothing of its own.

Then:

- **A shape is a shape; turning one thing into another is logic.** `schema.py` holds the types,
  `utils.py` the conversions over them. One of each per feature folder.
- **Group what changes together.** A reader follows one input to one output; a file per concern
  charges ten jumps for one step.
- **Do not split until a second consumer needs half of it.** A module with one caller is that
  caller's code, not a module.
- **Do not make a consumer depend on what it does not use.** Twenty things in one module puts
  every consumer in the blast radius of every edit. Split where consumers actually import.
- **Name a module for its noun or its job**, never `helpers.py`, `common.py`, `misc.py`.
  `utils.py` is the one exception, and only for conversions over the shapes in the `schema.py`
  beside it.
- **`§5` applies to filenames.** Read the import with nothing else on screen and say what comes
  back. When every module names a result, the folder listing is that feature's table of contents.
- **`utils.py` is where a feature starts, not where it ends.** The exception is countable: how
  many top-level functions mention a shape from that `schema.py`? When most do not, it holds
  something else — a vocabulary table, a config reader and a serialiser are three unnamed modules.
- **Declare the import direction once and never reverse it.** Write it in the top-level package
  docstring — *these packages may import the engine; the engine may not import them* — and
  enforce it with a test, not with discipline.

## 7 · Verify, then report

Decide what success is, as something you can run, before you start: *write the failing test, then
make it pass.* "Add validation" is not a goal; "invalid input raises, proved by a test" is.

- Add or change a test whenever behaviour changes. It must prove the new behaviour, not merely
  run the new code.
- Run the focused check, then the project's full check. Fix what they catch without growing the
  job.
- If behaviour must not change, say what proved it — identical bytes, an unchanged golden file,
  the same test count passing.
- Report what you ran and what it said. If you skipped something, say so. Never call unrun code
  working.

## 8 · When a rule is wrong

Rules lose to reasons. If a rule makes the code worse here, break it — and write the break where
the next reader will hit it: the module docstring, and the spec if there is one. Two rules
disagreeing in one place is a fact about the design; write it down rather than settling it
silently.

## 9 · Working agreement

- One task at a time. Finish it, verify it, commit it, then tell me to push. I push.
- Commit messages say **why**, not what the diff already shows: the option not taken, the cost
  paid, the rule bent.
- Never commit anything internal or personally identifying — this repo is public. No absolute
  paths, no credentials, no hostnames. Test fixtures are invented, never taken from real data.
- Never write a live key or token into a file. Environment variables only.

---

# Design Principles

`§1`–`§9` govern how a change is made. `§10`–`§42` govern the shape the code ends up in.

Every principle traces to a published source, listed at the end. Where sources disagree, the
disagreement is written down rather than hidden (`§8`). Each ends with **Check:** — how you tell
whether it holds. A principle with no check is a preference, and preferences go in a PR comment.

## Part 0 · Words we agree on

Design arguments waste time when two people mean different things by one word.

| Term | What it means here | Don't say |
|---|---|---|
| **Module** | Anything with an interface and an implementation — a function, a class, a package, a service. Size deliberately unspecified. | unit, component |
| **Interface** | Everything a caller must know to use it correctly: signature, invariants, ordering, error modes, required configuration, speed. Not just the types. | API, signature |
| **Depth** | How much it does, divided by how much you must learn to call it. | — |
| **Seam** | A place where behaviour can change without editing in that place. | boundary |
| **Adapter** | A concrete thing plugged into a seam. A role, not a substance — a fake and a production client are both adapters. | — |
| **Connascence** | Two things are connascent when changing one forces you to change the other. Three axes: strength, locality, degree. | "coupling" (too vague) |

**§10. Use these words, or define the one you want.**
A word nobody uses the same way is worse than no word.
**Check:** every term in the argument is in the table, or defined on the spot.

## Part 1 · Decomposition: where the lines go

**§11. Do not split along the flow of processing.**
One decision usually spans several steps, so splitting by step makes every change land in three
files. Ousterhout calls it *temporal decomposition*.
**Check:** name the change that touches each module *alone*. If every realistic change touches
three modules in a row, the lines are on the flowchart. *Argues with `§6` — see Conflicts.*

**§12. Split by the decisions most likely to change.**
Encoding format, storage engine, wire protocol, retry policy, pricing rule — each is a
secret one module keeps.
**Check:** every module answers "what do you hide?" in one sentence. A module that hides
nothing is a namespace.

**§13. An interface shows as little of the inside as possible.**
The opposite is leakage, and it needs no shared import: knowing the file format, or that A
must run before B, leaks through an implicit interface.
**Check:** change the internals. Does anything outside need editing?

**§14. Group by domain first, technical kind second.**
A package holding every controller in the system has nothing in common but its shape.
**Check:** show the top two levels of the tree to someone new. Naming the domain passes;
naming only the framework fails.

**§15. Split when a second consumer needs half of it, not before.**
A split for a caller that never arrives costs the extra jump forever and returns nothing.
**Check:** every extracted module has two callers, or a written reason the second is
imminent.

## Part 2 · Interfaces and depth

**§16. Prefer deep modules: a lot behind a small interface.**
The Unix file API hides disk layout, permissions, caching and concurrency behind a handful of
calls, rewritten inside for decades while the signatures stayed put.
**Check:** weigh what a caller must learn against what they get. An interface nearly as
complicated as its implementation is shallow.

**§17. Depth is about the interface, not the implementation.**
A deep module may be built inside from small swappable parts; they just do not reach the
caller.
**Caution:** read depth as *leverage per unit of interface learned*. As a literal ratio it
would reward a bloated implementation.

**§18. Delete it in your head first.**
Imagine the module gone. If nothing gets harder, it was a pass-through — do not add it. If
every caller has to do the work itself, keep it. This is `§4` one level up.
**Check:** the PR says which one, in one sentence.

**§19. The interface is the test surface.**
Callers and tests cross the same seam; a test that must reach past it is telling you the
shape is wrong.
**Check:** no test imports a module's internals. If one must, that is a design finding, not
a test problem.

**§20. Give each caller a narrow interface.**
Every member a caller does not call is still a reason it can be forced to change.
**Check:** list which callers use which members. Two callers with no overlap is a signal to
split.

**§21. Design it twice.**
Two or three genuinely different shapes before you choose — variations do not count.
**Check:** for any interface expected to outlive a quarter, the rejected alternative is
named in the PR or the spec.

**§22. Document the interface where the interface lives.**
Invariants, units, ordering and error modes are part of the interface because none of them are in
the signature. Comments restating what the code plainly does are still noise.
**Check:** every public element states what a caller must know that the type does not. A
precondition living only in a design document is an undocumented interface.

## Part 3 · Coupling, measured

Coupling is not on or off. Connascence has three axes: **strength** (how hard the dependency
is to change), **locality** (how far apart the ends sit), **degree** (how many things are
affected).

**§23. Strength — prefer the weaker form.**
Name is weaker than type, which is weaker than meaning, position or timing. A magic literal
becomes a named constant; positional arguments become keyword arguments; an implied ordering
becomes an explicit one.
**Check:** any dependency on an unwritten shared assumption — a magic number, an argument
order, an execution order — is a finding.

**§24. Locality — the further apart, the weaker the coupling must be.**
Strong connascence inside one small module is fine, across a package boundary is a problem,
across a network boundary is a defect. If you cannot weaken it, move the ends together.
**Check:** for each cross-package dependency, name its connascence type. Anything stronger
than name or type needs a stated reason.

**§25. Maximise connascence inside a boundary; minimise it across.**
Cohesion and coupling in one sentence instead of two.
**Check:** redraw a boundary and count both. If the numbers do not move in opposite
directions, the boundary is in the wrong place.

**§26. One key, one writer.**
Several writers is connascence of value and timing at the highest degree — the worst cell in
the table.
**Check:** for each field of shared state, name its single writer.

## Part 4 · Dependency direction

**§27. Dependencies point toward the domain.**
Business logic depends on nothing framework-shaped; frameworks, databases and transports sit
at the edges and point inward. This is `§6`'s import-direction rule, named.
**Check:** an import-graph rule in CI, not a diagram in a wiki (see `§38`).

**§28. An abstraction belongs to the layer that uses it, not the one that implements it.**
If the domain takes an `X`, `X` is *defined* in the domain — even when only an adapter can build
one. Ports inside, implementations outside. Defining a port beside its database implementation is
the usual way a clean layer diagram turns out to be false.
**Check:** no domain module imports from an adapter package, type annotations included.

**§29. One composition root.**
Exactly one place builds concrete dependencies and wires them together. Nothing else reaches
for a connection, a client, a clock or a file path.
**Check:** search for construction of adapters. More than one call site outside the
composition root is a finding.

**§30. One adapter is a guess; two make the seam real.**
A one-adapter seam is indirection with a nicer name. A test double counts only if the seam is
genuinely exercised through it. This is `§2` applied to architecture.
**Check:** for each port, name its adapters. Zero adapters means delete the port — the
interface type is already seam enough for a future implementer.

**§31. Name adapter packages for the kind of I/O, not for one transport.**
Otherwise the CLI and the batch job import "the API package" and the layer diagram stops
meaning anything.
**Check:** no non-HTTP entry point imports from the HTTP package.

## Part 5 · Errors, state, configuration

**§32. Make errors impossible where you can.**
The cheapest error is the one the design cannot express: a signature that cannot say the bad
thing, a default that makes the empty case ordinary, an operation safe to repeat. Not licence to
skip a check you need — it is the constructive form of `§2`.
**Check:** for each error branch, ask whether a different interface would delete it.

**§33. A bad item is data; a bad configuration is an exception.**
One bad record should not stop a batch of twenty thousand; a missing credential should stop the
process before the first record is read. Splitting by *scope* rather than severity gives one rule
instead of a judgement call every time.
**Check:** exceptions escaping the domain are startup-time only; everything else comes back as a
value.

**§34. Processes keep no state.**
Anything that must survive a request lives in a backing service, never in process memory or
on local disk. That is what makes restarts and crash recovery boring.
**Check:** kill a process mid-run and restart it. No committed work is lost.

**§35. Configuration lives in the environment, not in code.**
Tuned numbers count: a literal in the logic means changing behaviour takes a code change,
invisible in a config diff.
**Check:** grep for tuned literals in business logic. Also, per `§9`: could this repository be
open-sourced right now without leaking a credential?

**§36. Keep development and production alike.**
SQLite for Postgres, an in-memory queue for the real broker — the stand-in is fine, assuming
it behaves identically is not.
**Check:** at least one test suite runs against the production implementation of every backing
service, even if only in CI.

**§37. Logs are an event stream, and observability is built in from the start.**
Structured events to stdout; the application never manages log files or rotation. Logging is
I/O, so under `§27` it happens at the edge: the domain returns what happened, the edge writes
it.
**Check:** a long-running job can be watched while it runs, not only audited after it stops.
Every event carries the identifiers needed to tie it to a unit of work.

## Part 6 · Enforcement

**§38. Every rule above that a machine can check, is checked by one.**
Import rules, layering, cycle detection, naming, public-API snapshots. Without them rules rot
quietly: the diagram keeps saying the controller never touches the repository long after it did.
**Check:** the layering rule fails the build, not the review.

**§39. Write the guard before the code it constrains, and prove it fails.**
`§7` for architecture rules — a guard written afterwards is how a codebase picks up the thing
it forbids. On an existing codebase, baseline: freeze current violations so the rule blocks new
ones without a big-bang cleanup.
**Check:** every rule has a test showing it goes red.

**§40. Allow tracked exemptions.**
A rule with no escape hatch gets bypassed entirely — the import moves to a helper, or someone
deletes the check. Permit an annotated exemption naming a reason and an owner. `§8`, made
mechanical.
**Check:** the exemption list is short, dated, and shrinking.

**§41. Where a document states a fact the code also states, a test compares the two.**
Module lists, phase orders, supported formats, public API surfaces. Documentation nothing
checks becomes fiction, and unlike code nobody gets a compile error about it.
**Check:** the doc and the code are compared by CI, or the doc does not state that fact.

**§42. A guard that reads the installed version cannot see a copy that has not shipped.**
Reading a rule off the third party rather than off a list (`§38`) buys completeness only up to the
pin. Where the library is one we also own and still moving, the copy that matters is on a branch —
same table, same names, written twice, with the pin holding the guard's eyes shut. Distance makes
it worse (`§24`): two copies in one module drift in a review, two in two repositories drift in
silence.
**Check:** any sentence in the code saying *this also lives in the library, on a branch* is the
finding, not the excuse. Move the pin and delete the copy, or land the branch. A comment promising
a future deletion is connascence of value across a repository boundary, and the date is what
expires.

---

## Conflicts, written down

Per `§8`, rules that disagree are recorded rather than silently resolved.

**`§6` (`STEP ·` modules) vs `§11` (do not split along the flow).** `§6` optimises for the reader
following one input to one output; `§11` optimises for the writer changing a decision that spans
three steps. **Resolution: step modules are allowed, but a decision that spans steps is extracted
to its own module under `§12`, and the steps call it.** If a change keeps landing in several steps
at once, `§11` is telling you a module is missing, and it wins.

**`§6` (`utils.py` beside `schema.py`) vs `§10` (names must mean something).** `§6` grants one
exception on purpose. It stands, with a limit: `utils.py` holds conversions over the shapes in the
`schema.py` beside it and nothing else. The moment it holds something else, `§5` applies and it
gets a real name.

**`§6`'s escape hatch vs a guard that closes it.** A guard that fixes a package's **file list** —
these three files exactly, a fourth is a violation — turns every later addition into `utils.py`,
which is what `§6` exists to prevent. **Resolution: a guard may fix a package's shape only where
the conventions state that shape, and should prefer constraining import direction over file
count.** Where it fixes more, the guard is the finding.

**`§5` owns naming; `§10`–`§42` do not.** A naming argument that reaches the principles has gone
to the wrong section.

**Ousterhout vs SRP.** He argues that splitting by responsibility, taken far enough, yields many
shallow modules and adds more interface than it removes. SRP is used here as a heuristic — `§12`
is the sharper version — never as an instruction to make everything smaller.

**Ousterhout vs "self-documenting code".** He holds that comments are required interface
documentation. `§22` follows him; that is a real position with real opponents, not a neutral one.

**Package-by-feature vs package-by-layer.** `§14` takes a side. The counter-argument — layers give
newcomers an obvious place to put things, and shared code has no natural home under feature
packaging — is why `§14` says "domain first, technical kind second" rather than "never layer".

## Sources

| Source | Principles |
|---|---|
| Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules*, CACM 1972 | §11, §12, §13 |
| Ousterhout, *A Philosophy of Software Design*, 2018 | §11, §13, §16, §17, §18, §21, §22, §32 |
| Page-Jones, *Comparing Techniques by Means of Encapsulation and Connascence*, CACM 1992; Weirich's rules of thumb | §23–§26 |
| Feathers, *Working Effectively with Legacy Code*, 2004 | seam |
| Cockburn (Ports & Adapters); Martin, *Clean Architecture*; Palermo (Onion) | §27–§31 |
| Martin, *Screaming Architecture*, 2011; Fowler, *PresentationDomainDataLayering* | §14 |
| SOLID — SRP, ISP, DIP | §20, §28 |
| Wiggins et al., *The Twelve-Factor App* | §34–§37 |
| North, *CUPID — for joyful coding*, 2022 | §10, §37 |
| Ford, Parsons & Kua, *Building Evolutionary Architectures* | §38 |

## Renumbering

The principles were `P0`–`P32` until 2026-08-30. They are now `§10`–`§42` — one series, so a rule
is cited by number alone. The map is `Pn` → `§(n + 10)`. Every citation in this repository was
rewritten in the same commit.
