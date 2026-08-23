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
- **A one-word abbreviation of the concept.** Too short to mean anything on its own.
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

---

# Design Principles

`§1`–`§9` above govern how a change is made. `P0`–`P31` below govern the shape the code
ends up in. They are numbered separately so both can be cited in one review.

Every principle traces to a published source, named inline. Where sources disagree, the
disagreement is stated rather than hidden — per `§8`. Each principle ends with **Check:**,
the way you tell whether it holds. A principle with no check is a preference, and
preferences go in a PR comment, not here.

## Part 0 · Vocabulary

Design arguments waste time when two people mean different things by the same word.

| Term | Meaning here | Source | Don't say |
|---|---|---|---|
| **Module** | Anything with an interface and an implementation. Deliberately scale-agnostic: a function, a class, a package, a service. | Parnas 1972; Ousterhout 2018 | unit, component |
| **Interface** | Everything a caller must know to use it correctly — signature, invariants, ordering constraints, error modes, required configuration, performance characteristics. Not just the type signature. | Ousterhout 2018 | API, signature |
| **Depth** | How much functionality sits behind how little interface. Interface complexity is the cost the caller pays; functionality is the benefit they get. | Ousterhout 2018 | — |
| **Seam** | A place where behaviour can be changed without editing in that place. | Feathers 2004 | boundary |
| **Adapter** | A concrete implementation sitting at a seam. A role, not a substance — an in-memory fake and a production client are both adapters. | Cockburn, Ports & Adapters | — |
| **Connascence** | Two things are connascent when changing one forces you to change the other. Measured on three axes: strength, locality, degree. | Page-Jones 1992 | "coupling" (too coarse) |

**P0.** If a design discussion produces the words *component*, *service* or *boundary*
without a referent, restate it using the table above before continuing. Consistent
language is the whole point; a term nobody uses consistently is worse than no term.

## Part 1 · Decomposition: where the lines go

**P1. Do not decompose along the flow of processing.**
Parnas's central finding in *On the Criteria To Be Used in Decomposing Systems into
Modules* (CACM, 1972) is that starting from the flowchart is almost always wrong. Steps in
a pipeline make bad module boundaries because a design decision usually spans several
steps, so a change lands in all of them. Ousterhout names the same failure **temporal
decomposition** — splitting by the order in which things happen rather than by what a
module knows.
**Check:** for each module, name the change that would touch it *alone*. If every
realistic change touches three modules in a row, the lines are drawn on the flowchart.
*See the conflicts section — this one argues with `§6`.*

**P2. Decompose by the decisions most likely to change.**
Parnas's alternative: list the difficult or volatile design decisions first, then give each
one a module whose job is to hide it. Encoding format, storage engine, wire protocol,
retry policy, pricing rule — each is a secret one module keeps.
**Check:** every module can answer "what do you hide?" in one sentence. A module that hides
nothing is not a module, it is a namespace.

**P3. A module's interface should reveal as little as possible about its inside.**
Information hiding. Its opposite is **information leakage**: one design decision duplicated
across several modules. Leakage does not need a shared import — knowing the file format, or
knowing that A must be called before B, is leakage through an implicit interface.
**Check:** if you change the module's internal representation, does anything outside it
need editing?

**P4. Group by domain first, technical kind second.**
Package-by-feature keeps things that change together in one place, giving high cohesion and
low coupling by construction; package-by-layer gives the opposite, because a package
holding every controller in the system has nothing in common except its shape. Martin's
*Screaming Architecture* states the test: the top-level directory listing should tell a
newcomer what the system is about, not which framework built it.
**Check:** show the top two levels of the source tree to someone unfamiliar with the
project. If they can name the domain, it passes. If they can only name the framework, it
fails.

**P5. Split when a second consumer needs half of it, not before.**
A module split in anticipation of a caller that never arrives costs the indirection forever
and returns nothing. Same rule as `§6`, stated at package scale.
**Check:** every extracted module has at least two callers, or a written reason why the
second is imminent.

## Part 2 · Interfaces and depth

**P6. Prefer deep modules: much functionality, small interface.**
Ousterhout's canonical example is the Unix file API — a handful of calls hiding disk
layout, permissions, caching and concurrency, with the implementation rewritten repeatedly
over decades while the signatures stayed put.
**Check:** ask what a caller must learn versus what they get. If the interface is nearly as
complex as the implementation, the module is shallow and probably not earning its place.

**P7. Depth is a property of the interface, not the implementation.**
A deep module can be built internally from small swappable parts; they just do not surface
to callers. A module may have internal seams its own tests use, and one external seam at
its interface.
**Caution:** Ousterhout defines depth as roughly the ratio of implementation complexity to
interface complexity, which taken literally rewards a bloated implementation. Read it as
*leverage per unit of interface learned*, not as a line-count ratio.

**P8. The deletion test.**
Before adding a module, imagine deleting it. If complexity disappears with it, it was a
pass-through and should not exist. If the same complexity reappears in every caller, it
earns its keep. Ousterhout flags pass-through methods and pass-through variables as red
flags for exactly this reason. This is `§4` applied one level up.
**Check:** the PR description answers the deletion test in one sentence.

**P9. The interface is the test surface.**
Callers and tests cross the same seam. If a test must reach past the interface to set
something up or observe a result, the module is the wrong shape — change the shape rather
than reaching through it.
**Check:** no test imports a module's internals. If one must, that is a design finding, not
a test problem.

**P10. Expose narrow, caller-specific interfaces.**
Interface Segregation, from SOLID. No caller should depend on members it never calls,
because every member it does not call is a reason it can be forced to change. `§6`'s
blast-radius rule is the file-level version of this.
**Check:** for each interface, list which callers use which members. Two callers with
disjoint member sets is a signal to split.

**P11. Design it twice.**
Ousterhout's most transferable practice: for any interface that matters, produce two or
three genuinely different designs before choosing — not variations, different shapes. He
reports that his second design for the Tk toolkit API beat his first.
**Check:** for any interface expected to outlive a quarter, the rejected alternative is
named in the PR or the spec.

**P12. Document the interface where the interface lives.**
Ousterhout is unusually firm here, against the "code should be self-documenting" fashion:
comments stating invariants, units, ordering constraints and error modes are part of the
interface, because that information exists nowhere in the signature. Comments restating
what the code plainly does are a different thing and are still noise.
**Check:** every public element states what a caller must know that the type does not say.
In particular, a precondition that lives only in a design document is an undocumented
interface.

## Part 3 · Coupling, measured

Coupling is not binary. Page-Jones's connascence model (*Comparing Techniques by Means of
Encapsulation and Connascence*, CACM 1992) gives three axes: **strength** (how hard the
dependency is to change), **locality** (how far apart the two ends sit), **degree** (how
many things are affected). Jim Weirich's rules of thumb follow from them.

**P13. Rule of strength — prefer weaker forms.**
Connascence of name is weaker than of type, which is weaker than of meaning, position or
timing. Refactor toward the weaker form: a magic literal becomes a named constant,
positional arguments become keyword arguments or a struct, an implicit ordering requirement
becomes an explicit one.
**Check:** any dependency on an undocumented shared assumption — a magic number, an
argument order, an execution order — is a finding.

**P14. Rule of locality — the further apart, the weaker the coupling must be.**
Strong connascence inside one small module is fine. The same strength across a package
boundary is a problem; across a network boundary it is a defect. If you cannot weaken the
coupling, move the two ends closer together instead.
**Check:** for each cross-package dependency, name its connascence type. Anything stronger
than name or type needs a stated reason.

**P15. Maximise connascence inside a boundary; minimise it across.**
Page-Jones's own rule, and simply cohesion and coupling stated as one sentence instead of
two.

**P16. One key, one writer.**
For any piece of derived or shared state, exactly one module writes it. Multiple writers is
connascence of value and timing at maximum degree — the worst cell in the table.
**Check:** for each field of shared state, name its single writer.

## Part 4 · Dependency direction

**P17. Dependencies point toward the domain.**
The Dependency Rule from Clean Architecture, and the same rule in Hexagonal / Ports &
Adapters and in Onion. Business logic depends on nothing framework-shaped; frameworks,
databases and transports sit at the edges and depend inward. This is `§6`'s import-direction
rule, named.
**Check:** an import-graph rule in CI, not a diagram in a wiki (see P28).

**P18. An abstraction belongs to the layer that consumes it, not the layer that implements
it.**
Dependency Inversion, stated where it actually gets violated. If the domain takes `X` as a
parameter, `X` is *defined* in the domain — even when the only thing that can construct an
`X` is an adapter. Ports live inside; implementations live outside. Defining a port next to
its database implementation is the most common way a clean-looking layer diagram turns out
to be false.
**Check:** no domain module imports from an adapter package, including for type
annotations.

**P19. One composition root.**
Exactly one place constructs concrete dependencies and wires them together. Nothing else
reaches for a connection, a client, a clock or a file path.
**Check:** search for construction of adapters. More than one call site outside the
composition root is a finding.

**P20. One adapter is a hypothetical seam; two adapters make it real.**
Do not cut a seam until something actually varies across it. A single-adapter seam is
indirection with a better name. A test double counts only if the seam is genuinely
exercised through it. This is `§2` applied to architecture.
**Check:** for each port, name its adapters. Zero adapters means delete the port — the
interface type is already enough of a seam for a future implementer.

**P21. Name adapter packages for the kind of I/O, not for one transport.**
A package named for the HTTP layer must not hold code the CLI and the batch job also need.
When it does, everything ends up importing "the API package" and the layer diagram stops
meaning anything.
**Check:** no non-HTTP entry point imports from the HTTP package.

## Part 5 · Errors, state, configuration

**P22. Define errors out of existence where you can.**
Ousterhout's argument, and the least-followed idea in his book: the cheapest error is the
one the design makes unrepresentable. Prefer a signature that cannot express the bad case,
a default that makes the empty case ordinary, an operation that is idempotent. This is not
licence to skip a check you actually need, and it is the constructive form of `§2`'s ban on
error handling for unreachable states.
**Check:** for each error branch, ask whether a different interface would delete it.

**P23. Failure about one item is data on that item; failure about the configuration is an
exception.**
A bad record should not stop a batch of twenty thousand. A missing credential should stop
the process before the first record is read. Separating the two by *scope* rather than by
severity gives one rule instead of a judgement call at every site.
**Check:** exceptions escaping the domain are startup-time only. Everything else surfaces
as a value.

**P24. Processes are stateless.**
Twelve-Factor VI. Any state that must survive a request lives in a backing service, never
in process memory or on the local disk. This is what makes restarts, scaling and crash
recovery unremarkable.
**Check:** killing a process mid-run and restarting it loses no committed work.

**P25. Configuration lives in the environment, not in code.**
Twelve-Factor III. Anything that varies between deployments is read at the edge and passed
in. Behavioural constants belong in configuration too: logic containing tuned numeric
literals means changing behaviour requires changing code, and the change is invisible in a
config diff.
**Check:** grep for tuned literals in business logic. Also, per `§9`: could this repository
be open-sourced right now without leaking a credential?

**P26. Keep development and production as similar as possible.**
Twelve-Factor X. The classic violation is a lightweight local substitute for a backing
service — SQLite standing in for Postgres, an in-memory queue for the real broker. The
substitute is fine; the assumption that they behave identically is not.
**Check:** at least one test suite runs against the production implementation of every
backing service, even if only in CI.

**P27. Treat logs as an event stream, and build observability in from the start.**
Twelve-Factor XI: the application writes structured events to stdout and never manages log
files or rotation. "Predictable" in Dan North's CUPID makes the same point from the design
side — code you cannot observe is code you cannot trust. Logging is I/O, so under P17 it
happens at the edge: the domain returns what happened, the edge writes it.
**Check:** a long-running job can be observed while it runs, not only audited after it
stops. Every event carries the identifiers needed to correlate it with a unit of work.

## Part 6 · Enforcement

**P28. Every rule above that can be checked mechanically, is.**
An architecture fitness function (Ford, Parsons & Kua, *Building Evolutionary
Architectures*) is any objective, automated, repeatable check that an architectural
property still holds. Import rules, layering rules, cycle detection, naming rules and
public-API snapshots all qualify. Tooling exists in every ecosystem — ArchUnit for Java,
import-linter for Python, dependency-cruiser or ESLint boundaries for JavaScript,
NetArchTest for .NET. Without them, rules degrade quietly: the diagram keeps saying the
controller never touches the repository long after it started to.
**Check:** the layering rule fails the build, not the review.

**P29. Write the guard before the code it constrains, and prove it fails.**
`§7` for architecture rules. A guard written afterwards is how a codebase acquires the
thing the guard forbids. Each new rule is demonstrated against a synthetic violation before
it is trusted. On an existing codebase, baseline instead: freeze current violations so the
rule blocks new ones without demanding a big-bang cleanup.
**Check:** every rule has a test showing it goes red.

**P30. Allow tracked exemptions.**
A rule with no escape hatch gets bypassed entirely — the import moves to a helper, or
someone deletes the check. Permit an annotated exemption naming a reason and an owner, and
review the list periodically. This is `§8` made mechanical.
**Check:** the exemption list is short, dated, and shrinking.

**P31. Where a document states a fact the code also states, a test compares the two.**
Module lists, phase orders, supported formats, public API surfaces. Documentation nothing
checks becomes fiction without anyone noticing, and unlike code, nobody gets a compile
error about it.
**Check:** the doc and the code are compared by CI, or the doc does not state that fact.

---

## Conflicts, written down

Per `§8`, rules that disagree are recorded rather than silently resolved.

**`§6` (`STEP ·` modules, "everything one step does belongs in that step's module") vs P1
(do not decompose along the flow of processing).**
These pull opposite ways and both are right about something. `§6` optimises for the reader
following one input to one output: a file per concern charges ten navigations for one step.
P1 optimises for the writer making a change: a volatile decision that spans three steps
gets edited in three places. Resolution used here: **step modules are allowed, but a
decision that spans steps is extracted to its own module under P2, and the steps call it.**
If a change keeps landing in several steps at once, that is P1 telling you a module is
missing, and it wins.

**`§6` (`utils.py` permitted beside `schema.py`) vs P0 (names must mean something).**
`§6` grants one exception on purpose. It stands, with a limit: `utils.py` holds conversions
over the shapes in the `schema.py` beside it, and nothing else. The moment it holds
something else, `§5` applies and it gets a real name.

**`§5` owns naming; the P-series does not.**
There is no naming principle below because `§5` is already sharper than anything the
sources offer. If a naming argument reaches the P-series, it has gone to the wrong section.

**Ousterhout vs SRP.** He argues that splitting by responsibility, taken far enough, yields
many shallow modules and adds more interface than it removes. This document uses SRP as a
decomposition heuristic — P2 is the sharper version — never as an instruction to make
everything smaller. `§4` says the same thing about functions.

**Ousterhout vs "self-documenting code".** He holds that comments are required interface
documentation. P12 follows him; it is a real position with real opponents, not a neutral
one.

**Package-by-feature vs package-by-layer.** P4 takes a side. The counter-argument — that
layers give newcomers an obvious place to put things, and that shared code has no natural
home under feature packaging — is real, and is why P4 says "domain first, technical kind
second" rather than "never layer".

## Sources

| Source | Principles |
|---|---|
| Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules*, CACM 1972 | P1, P2, P3 |
| Ousterhout, *A Philosophy of Software Design*, 2018 | P1, P3, P6, P7, P8, P11, P12, P22 |
| Page-Jones, *Comparing Techniques by Means of Encapsulation and Connascence*, CACM 1992; Weirich's rules of thumb | P13–P16 |
| Feathers, *Working Effectively with Legacy Code*, 2004 | seam |
| Cockburn (Ports & Adapters); Martin, *Clean Architecture*; Palermo (Onion) | P17–P21 |
| Martin, *Screaming Architecture*, 2011; Fowler, *PresentationDomainDataLayering* | P4 |
| SOLID — SRP, ISP, DIP | P10, P18 |
| Wiggins et al., *The Twelve-Factor App* | P24–P27 |
| North, *CUPID — for joyful coding*, 2022 | P0, P27 |
| Ford, Parsons & Kua, *Building Evolutionary Architectures*, 2nd ed. 2023 | P28–P30 |