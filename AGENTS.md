# Conventions

Rules for anyone — person or agent — writing code here. General enough to copy into another
repo.

## Think before you code

- Say your assumptions out loud.
- If the request reads two ways, say both and pick one. Never pick silently.
- If something is unclear, name the confusing part and ask.
- If a simpler way exists, say so before writing the complicated one.
- A reason I can check beats agreement.

## Write the least code that solves it

- Nothing built for a future that has not arrived.
- No features beyond what was asked.
- No abstraction for a single use.
- No settings nobody asked for.
- No error handling for a state no caller can reach.
- If you wrote two hundred lines and fifty would do, write the fifty.

## Change only what was asked

- Touch what the request needs and nothing else.
- Do not tidy nearby code, comments or formatting.
- Do not refactor working code.
- Match the style already there, even where you would write it differently.
- Delete what your own change left unused.
- Leave dead code that was already there. Mention it instead.

## When something deserves to be a function

- Make one when two or more places call it.
- Make one when it holds a decision a reader needs to see named: a check, a branch, a raise,
  a rule.
- One expression with one caller is not a function. Inline it. A name that only forwards an
  argument costs a file to open and gives back nothing.
- These earn a name even with a single caller:
  - a method that implements an interface, because deleting it deletes the polymorphism
  - a callback whose name shows up in output, configuration or metrics
  - a cached function, where the decorator is the point
  - a function that returns a function
  - anything longer than one expression: a loop, a try/except, a generator, an early return
  - anything a test calls directly
- Splitting a long function into named steps is often right. Each step must be nameable as a
  result, not as "part two of the thing above".

## How to name things

- A name says what comes back, not what was done to get it.
- A name is long enough to be clear read alone at the call site.
- A bare verb names no object. Parse what, into what? Name the result.
- A relation suffix hides the object. The noun in front is then free to be wrong without
  looking wrong.
- A one-word shortening of a concept is too short to mean anything.
- A word already used for a step, a stage, a command or a table makes every sentence about
  the code ambiguous.
- Read the call site with nothing else on screen. If you cannot say what comes back, the name
  is too short.
- A leading underscore is not an excuse. You still have to read it.

## How to organise files

- One module, one job. The first word of the module docstring says which kind of job:
  - a definition: one noun and its shape, its types and its constants
  - logic: the conversions and computations over that noun
  - a step: serves exactly one step of the flow, and nothing else
  - a tool: not in the flow at all
  - a façade: re-exports, and holds nothing of its own
- A shape is a shape; turning one thing into another is logic. They change for different
  reasons, so they are different files.
- Group what changes together. A reader follows one input to one output, and a file per
  concern charges ten jumps for one step.
- Do not split a module until a second consumer needs half of it. A module with one caller is
  that caller's code.
- Do not make a consumer depend on what it does not use. Twenty things in one module puts
  every consumer in the blast radius of every edit.
- Name a module for its noun or its job, never for how useful it is. There is no such thing as
  a helpers module.
- A module named for utilities holds conversions over the shapes beside it and nothing else.
  The moment it holds something else, it needs a real name.
- Read the import with nothing else on screen and say what comes back.
- Declare the import direction once and never reverse it. Enforce it with a test, not with
  discipline.

## Verify, then report

- Decide what success is, as something you can run, before you start.
- Write the failing test, then make it pass.
- "Add validation" is not a goal. "Invalid input raises, proved by a test" is.
- Add or change a test whenever behaviour changes. It must prove the new behaviour, not merely
  run the new code.
- Run the focused check, then the project's full check. Fix what they catch without growing
  the job.
- If behaviour must not change, say what proved it.
- Report what you ran and what it said.
- If you skipped something, say so. Never call unrun code working.

## When a rule is wrong

- Rules lose to reasons.
- If a rule makes the code worse here, break it.
- Write the break where the next reader will hit it.
- Two rules disagreeing in one place is a fact about the design. Write it down rather than
  settling it silently.

## Working agreement

- One task at a time. Finish it, verify it, commit it, then tell me to push. I push.
- Commit messages say why, not what the diff already shows: the option not taken, the cost
  paid, the rule bent.
- Never commit anything internal or personally identifying. This repo is public.
- No absolute paths, no credentials, no hostnames.
- Test fixtures are invented, never taken from real data.
- Never write a live key or token into a file. Environment variables only.

---

# Design principles

## Words we agree on

- A module is anything with an interface and an implementation: a function, a class, a
  package, a service.
- An interface is everything a caller must know to use it correctly: the signature, the
  invariants, the ordering, the error modes, the required configuration, the speed. Not just
  the types.
- Depth is how much a module does, divided by how much you must learn to call it.
- A seam is a place where behaviour can change without editing in that place.
- An adapter is a concrete thing plugged into a seam. A fake and a production client are both
  adapters.
- Two things are connascent when changing one forces you to change the other.
- Use these words, or define the one you want. A word nobody uses the same way is worse than
  no word.

## Where the lines go

- Do not split along the flow of processing. One decision usually spans several steps, so
  splitting by step makes every change land in three files.
- Split by the decisions most likely to change. Give each one a module whose job is to hide
  it: the encoding format, the storage engine, the wire protocol, the retry policy.
- A module that hides nothing is a namespace, not a module.
- An interface shows as little of the inside as possible.
- Leakage needs no shared import. Knowing the file format, or knowing that one call must come
  before another, leaks through an implicit interface.
- Group by domain first, technical kind second. A package holding every controller in the
  system has nothing in common but its shape.
- Someone new should be able to read the top of the source tree and name the domain, not the
  framework.
- Split when a second consumer needs half of it, not before. A split made for a caller that
  never arrives costs the extra jump forever and returns nothing.

## Interfaces and depth

- Prefer deep modules: a lot behind a small interface.
- Weigh what a caller must learn against what they get. An interface nearly as complicated as
  its implementation is shallow.
- Depth is about the interface, not the implementation. A deep module may be built inside from
  small swappable parts; they just do not reach the caller.
- Before adding a module, imagine it gone. If nothing gets harder, it was a pass-through. If
  every caller has to do the work itself, it earns its place.
- The interface is the test surface. A test that must reach past it to set something up or see
  a result is telling you the shape is wrong.
- Give each caller a narrow interface. Every member a caller does not call is still a reason
  it can be forced to change.
- Design it twice. Two or three genuinely different shapes before you choose; variations do
  not count.
- Document the interface where the interface lives. Invariants, units, ordering and error
  modes are part of it, because none of them are in the signature.
- A precondition that lives only in a design document is an undocumented interface.
- Comments restating what the code plainly does are still noise.

## Coupling

- Coupling is not on or off. It has three axes: how hard the dependency is to change, how far
  apart the two ends sit, and how many things are affected.
- Prefer the weaker form. A magic literal becomes a named constant. Positional arguments
  become keyword arguments. An implied ordering becomes an explicit one.
- Any dependency on an unwritten shared assumption is a finding: a magic number, an argument
  order, an execution order.
- The further apart, the weaker the coupling must be. Strong coupling inside one small module
  is fine, across a package boundary is a problem, across a network boundary is a defect.
- If you cannot weaken it, move the two ends together.
- Maximise coupling inside a boundary; minimise it across.
- One key, one writer. For any derived or shared state, exactly one module writes it.

## Dependency direction

- Dependencies point toward the domain. Business logic depends on nothing framework-shaped.
- Frameworks, databases and transports sit at the edges and point inward.
- An abstraction belongs to the layer that uses it, not the one that implements it. If the
  domain takes something as a parameter, that thing is defined in the domain, even when only
  an adapter can build one.
- Ports live inside, implementations outside. Defining a port beside its database
  implementation is the usual way a clean layer diagram turns out to be false.
- One composition root. Exactly one place builds concrete dependencies and wires them
  together, and nothing else reaches for a connection, a client, a clock or a file path.
- One adapter is a guess; two make the seam real. Do not cut a seam until something actually
  varies across it.
- A port with no adapters should be deleted. The interface type is already seam enough for a
  future implementer.
- Name adapter packages for the kind of input and output, not for one transport. Otherwise
  every entry point imports the package named for the web layer, and the diagram stops meaning
  anything.

## Errors, state, configuration

- Make errors impossible where you can. The cheapest error is the one the design cannot
  express.
- Prefer a signature that cannot say the bad thing, a default that makes the empty case
  ordinary, an operation safe to repeat.
- This is not licence to skip a check you actually need.
- A bad item is data; a bad configuration is an exception.
- One bad record should not stop a batch of twenty thousand.
- A missing credential should stop the process before the first record is read.
- Processes keep no state. Anything that must survive a request lives in a backing service,
  never in process memory or on local disk.
- Configuration lives in the environment, not in code.
- Tuned numbers are configuration too. A literal in the logic means changing behaviour takes a
  code change, and the change is invisible in a configuration diff.
- Keep development and production alike. A lightweight local stand-in for a backing service is
  fine; assuming it behaves identically is not.
- Logs are an event stream. Write structured events to standard output, and never manage log
  files or rotation.
- Logging is input and output, so it happens at the edge: the domain returns what happened,
  the edge writes it.
- Code you cannot watch while it runs is code you cannot trust.

## Enforcement

- Every rule a machine can check should be checked by one: import rules, layering, cycle
  detection, naming, public interface snapshots.
- Without that, rules rot quietly. The diagram keeps saying the controller never touches the
  repository long after it did.
- A rule that fails the build is enforced. A rule that fails the review is a suggestion.
- Write the guard before the code it constrains, and prove it goes red first. A guard written
  afterwards is how a codebase picks up the thing it forbids.
- On an existing codebase, freeze the current violations so the rule blocks new ones without
  demanding a big cleanup.
- A guard may fix the shape of a package only where the conventions state that shape. Prefer
  constraining the direction of an import over the number of files.
- A rule that forbids its own remedy is worse than no rule.
- Allow tracked exemptions. A rule with no escape hatch gets bypassed entirely: the import
  moves to a helper, or someone deletes the check.
- An exemption names a reason and an owner. The list should be short, dated, and shrinking.
- Where a document states a fact the code also states, a test compares the two. Documentation
  nothing checks becomes fiction, and unlike code, nobody gets a compile error about it.
- A guard that reads the installed version of a library cannot see a copy that has not
  shipped. Two copies in one module drift in a review; two copies in two repositories drift in
  silence, and nobody runs the tests for the second one.
- Step modules are allowed, but a decision that spans several steps gets its own module and
  the steps call it. If a change keeps landing in three steps at once, a module is missing.

## Sources

- Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules*, 1972
- Page-Jones, *Comparing Techniques by Means of Encapsulation and Connascence*, 1992
- Feathers, *Working Effectively with Legacy Code*, 2004
- Martin, *Screaming Architecture*, 2011, and *Clean Architecture*
- Cockburn, *Ports & Adapters*; Palermo, *Onion Architecture*
- Ousterhout, *A Philosophy of Software Design*, 2018
- Wiggins and others, *The Twelve-Factor App*
- North, *CUPID — for joyful coding*, 2022
- Ford, Parsons and Kua, *Building Evolutionary Architectures*
