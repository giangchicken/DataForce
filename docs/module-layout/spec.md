# Module layout — the tree mirrors the flow

**Status:** built, in six commits, Phase 2L of the plan. Supersedes
`docs/engine-api-split/spec.md`, whose one rule (§ *the engine never opens a file*) is
restated here as requirement 3.

**What the build changed about this document.** Three renames in § *Naming — private*
were guesses this document made about code it had not read, and the code won:
`_records` is `_raw_with_records` rather than `_read_records`, because it reads no file
-- it pairs raw items with the records they became; `cli._profile` is `_profile_command`
rather than `_named_profile`, because it returns an exit code for a subcommand; and
`modalities/text._model` is `_embedder`. Everything else was applied as written. Two
things were found on the way and fixed in the commit that moved them rather than
carried forward: a comment in the old `build_record.py` claimed
`label_names_one_tool_twice` reads 0, where `params.yaml` has said 10 since Phase 2C;
and `test_naming.py`'s scan had never looked at a private name, which is where two
dozen of them had been sitting.

## What

The annotation flow has four phases — `data_quality`, `ai_review`, `human_review`,
`release` — and they already name the stage table, the planned `pipeline/` directories
and the artifact schemas. They do not name the profile, which is instead split into
modules called `build_record.py`, `answer.py` and `ask_annotator.py` — three operations.
This spec makes the flow the layout rule everywhere: `shared/` becomes `core/`, the base
the flow is written against; every profile is the same seven files, four of them named
for a phase; and the function names that state an operation instead of a result are
renamed, with the guard that permits them extended so they cannot come back. No
behaviour changes, and the proof of that is stated in § *Invariants*.

## Context

### The premise, measured

`shared/` is **not** used only by profiles. Every package imports it:

| importer | files importing `dataforce.shared` |
|---|---|
| `profiles/` | 8 |
| `shared/` itself | 8 |
| `declared/` | 3 |
| `api/` | 2 |
| `modalities/` | 2 |
| `cli.py` | 1 |

So "it is only for profiles, make it a base" does not hold as stated. What does hold is
sharper, and it is per member rather than per package:

| member | lines | production importers |
|---|---|---|
| `shared/errors.py` | 26 | 14 — every package |
| `shared/record.py` | 171 | 11 |
| `shared/manifest.py` | 41 | 4 |
| `shared/gates/runner.py` | 113 | **1** (`api/artifacts.py`) |
| `shared/registry.py` | 100 | **1** (`api/engine.py`) |
| `shared/schemas/` | 387 | **0** — one test, nothing in `src/` |

Three members are a genuine base. Two have a single caller each, which AGENTS.md §6
calls that caller's code. One has no caller at all. `shared/` accumulated them because
its docstring names *consumers* — "what every stage uses" — and `pipeline/` is still
empty, so nothing was ever excluded. A name that describes who imports a thing cannot
reject a candidate; a name that describes what a thing *is* can. That is the real
argument for the change, and it is why `shared/` is renamed rather than just tidied.

### The flow already names everything except the profile

The four phases are canonical in three places today:

- the core spec's stage table — `docs/annotation-pipeline/spec.md`, stages 0-14, with a
  phase column: `data_quality` 0-4, `ai_review` 5-6, `human_review` 7-11, `release` 12-14;
- the planned stage modules — `pipeline/data_quality/load.py`, `pipeline/ai_review/jury.py`,
  `pipeline/human_review/publish.py`, `pipeline/release/split.py`, per the plan's Phases 3-6;
- the artifact schemas — `shared/schemas/{data_quality,ai_review,human_review,release}.py`,
  one per phase, each docstring stating which stages import it and no others.

The profile is the exception, and it is the module a reader opens most. To answer *what
does stage 8 ask of a profile* you must know that `publish` needs `answer_config`, and
that `answer_config` is in a file called `ask_annotator.py`. Nothing in the tree tells
you that.

### That the regrouping is a pure move, measured

`ToolDecisionProfile` is eleven members, and every one is a one-line forward to exactly
one module. So the modules can be regrouped by phase without touching a single
expression:

| profile member | forwards to | phase that asks for it | stage |
|---|---|---|---|
| `build_record` | `build_record.build_record` | `data_quality` | 0 `load` |
| `validity_checks` | `build_record.validity_checks` | `data_quality` | 1 `remove_invalid` |
| `vote_consensus` | `answer.vote_consensus` | `ai_review` | 5 `jury` |
| `question_text` | `ask_annotator.question_text` | `human_review` | 7 `generate_questions` |
| `readable_catalog` | `ask_annotator.readable_catalog` | `human_review` | 8 `publish` |
| `answer_config` | `ask_annotator.answer_config` | `human_review` | 8 `publish` |
| `scenario_hash` | `build_record.scenario_hash` | `release` | 12 `split` |
| `training_example` | `answer.training_example` | `release` | 13 `export` |
| `answer_distance` | `answer.answer_distance` | **two** — 5, 6, 10 | — |
| `answer_schema_for` | `schema.answer_schema_for` | **two** — 5, and 9/11 | — |
| `answer_schema` | `schema.ANSWER_SCHEMA` | none — it is the type | — |

Read down the phase column: `build_record.py` holds one phase's work plus one of
`release`'s, `answer.py` holds one of `ai_review`'s plus one of `release`'s plus a
cross-phase computation. `scenario_hash` and `training_example` are both `release` and
they are in different files, each named after a different phase's job. That is the
chaos, and it is not a matter of taste — it is two members of one phase in two modules
named for other phases.

### The naming failure, measured

`test_naming.py` guards public functions in `modalities/`, `profiles/` and `declared/`
against a nine-word denylist and against stage names. It does not look at private
functions, and `shared/` is out of scope by its own docstring. Inside that blind spot:

- `tools_to_catalog(tools)` returns **`str`**, and `catalog_to_tools(text)` returns
  **`Catalog`**. Two functions, opposite directions, and each one's name promises what
  the other returns. Neither can be read at a call site without opening it.
- `read_catalog`, `record_catalog`, `catalog_names`, `catalog_hash` — four adjacent
  names differing by one word, only two of which say what comes back.
- `_spec_from(declared, rest)` returns a three-tuple. *From* what, *to* what, and which
  of the three is the return?
- `_note`, `_says`, `_coerce`, `_attribute`, `_leaves`, `_turn`, `_records`, `_of`-shaped
  names throughout. AGENTS.md §5 closes this explicitly: *"A private `_` prefix is not an
  excuse — you still have to read it."*

## Requirements

1. `shared/` is renamed `core/`, and its docstring states what it *is* rather than who
   imports it.
2. `core/` contains exactly: `record.py`, `errors.py`, `manifest.py`, `gates.py`,
   `flow.py`, and `artifacts/` (one module per phase plus `base.py`). Nothing else may be
   added to `core/` without a second consumer.
3. `core/`, `modalities/`, `profiles/` and `pipeline/` never open a file and never name a
   path under `config/`, `data/`, `metrics/` or `params.yaml`. (Restated from
   `engine-api-split`; already enforced by `tests/unit/test_layering.py`.)
4. `core/flow.py` names the four phases and their stage ranges, once, as data.
5. The phase names in `core/flow.py` equal the phase column of the core spec's stage
   table, asserted by a test that parses the table.
6. Every profile package contains exactly these files and no others:
   `__init__.py`, `schema.py`, `utils.py`, `data_quality.py`, `ai_review.py`,
   `human_review.py`, `release.py` — plus any number of modules whose docstring begins
   `TOOL ·`, which are by definition not in the flow.
7. Each phase module's docstring first line is `STEP · <phase> (stages N-M)`, with the
   phase and range matching `core/flow.py`.
8. No profile phase module imports a sibling phase module. Anything two phases need is in
   `schema.py` or `utils.py`.
9. `schema.py` holds only shapes and the schemas over them; `utils.py` holds every
   conversion and computation over those shapes. Neither imports a phase module.
10. `Gap` moves to `utils.py`, its only producer and only consumer. (Carried from the
    review of `schema.py`; the same finding, now with a layout rule behind it.)
11. `Catalog.is_empty` is deleted — one expression, zero production callers.
12. No function in `core/`, `modalities/`, `profiles/` or `declared/`, **public or
    private**, is named for a bare operation or for a stage. The rename table in
    § *Design* is applied, and every name removed by it is added to the guard's denylist
    so it cannot return.
13. `registry.py` moves to `api/`, and `shared/gates/` — a package holding one module and
    an empty `__init__.py` — is flattened to `core/gates.py`.
14. `shared/schemas/` becomes `core/artifacts/`, because what those modules describe is
    artifacts, and because `schemas/` one directory away from every profile's `schema.py`
    is the ambiguity AGENTS.md §5 names as its third failure.
15. `source_contract.py` is dissolved: `SourceContract` into `schema.py`,
    `read_source_contract` into `utils.py`.
16. No behaviour changes. Proof is stated in § *Invariants* and is a precondition of the
    last commit, not a hope about it.

## Design

### Target tree

```
src/dataforce/
  core/                    what the flow is written against
    flow.py                DEFINITION · the four phases and their stage ranges
    record.py              DEFINITION · the one shape that flows through every stage
    errors.py              DEFINITION · every error DataForce raises
    manifest.py            DEFINITION · what an implementation is, declared
    gates.py               LOGIC · the gate engine: what stops a run
    artifacts/             DEFINITION · what each phase's artifacts must contain
      base.py  data_quality.py  ai_review.py  human_review.py  release.py
  modalities/              axis 1 — what content is
    base.py                the contract
    text/__init__.py       one module until it needs splitting (see Decision 7)
  profiles/                axis 2 — what an answer is
    base.py                the contract, ordered and sectioned by phase
    tool_decision/
      __init__.py          the profile object: declarations bound to the six below
      schema.py            DEFINITION · Tool, Catalog, the answer type and space
      utils.py             LOGIC · every conversion and computation over those
      data_quality.py      STEP · data_quality (stages 0-4)
      ai_review.py         STEP · ai_review (stages 5-6)
      human_review.py      STEP · human_review (stages 7-11)
      release.py           STEP · release (stages 12-14)
      measure_corpus.py    TOOL · not in the flow
  pipeline/                the fifteen stages, one package per phase
  declared/                the only reader of config/
  api/                     the published surface, plus registry.py
  cli.py
```

### Every module, and where it goes

| today | lines | goes to | why |
|---|---|---|---|
| `shared/record.py` | 171 | `core/record.py` | base, 11 importers |
| `shared/errors.py` | 26 | `core/errors.py` | base, 14 importers |
| `shared/manifest.py` | 41 | `core/manifest.py` | base, 4 importers |
| `shared/gates/runner.py` | 113 | `core/gates.py` | the flow's spine; package flattened |
| `shared/gates/__init__.py` | 0 | deleted | an empty file around one module |
| `shared/schemas/*` | 387 | `core/artifacts/*` | already one per phase; renamed for what it holds |
| `shared/registry.py` | 100 | `api/registry.py` | one production caller, and it is `api/engine.py` |
| `tool_decision/schema.py` | 132 | `schema.py` | stays; loses `Gap` and `is_empty` |
| `tool_decision/utils.py` | 497 | `utils.py` | stays; gains `Gap`, δ, `calls_by_name`, `read_source_contract` |
| `tool_decision/build_record.py` | 242 | `data_quality.py` | minus `scenario_hash` → `release.py` |
| `tool_decision/answer.py` | 202 | split three ways | `vote_consensus` → `ai_review.py`; `training_example` → `release.py`; δ and `calls_by_name` → `utils.py` |
| `tool_decision/ask_annotator.py` | 190 | `human_review.py` | whole module, one phase |
| `tool_decision/source_contract.py` | 116 | `schema.py` + `utils.py` | a shape and its reader, split by kind |
| `tool_decision/measure_corpus.py` | 250 | unchanged | `TOOL ·`, not in the flow |

`ai_review.py` (~45 lines) and `release.py` (~40) start small. That is the price of every
profile reading the same way, and it is stated rather than hidden: Phase 4 adds the
jury's answer-space call to the first and Phase 5 adds pull-time validation, so both grow
where the flow says they should.

### Why δ and the answer space are not in a phase module

Both have consumers in two phases — δ at stages 5, 6 and 10; the answer space at stage 5
and again at 9/11. Putting either in `ai_review.py` would make `human_review.py` import a
sibling phase, which is the coupling `core/artifacts/` already refuses ("stages 5-6 import
this module and no other"). So the layering rule is:

```
__init__.py  →  any
phase module →  schema.py, utils.py, core/          never a sibling phase
utils.py     →  schema.py, core/                    never a phase module
schema.py    →  core/                               never utils.py, never a phase module
```

Enforced by an AST test in the style of the three that exist, not by discipline.

### Naming — public

| today | returns | becomes |
|---|---|---|
| `catalog_to_tools(text)` | `Catalog` | `catalog_from_text` |
| `tools_to_catalog(tools)` | `str` | `catalog_text` |
| `openai_to_tools(entries)` | `Catalog` | `catalog_from_openai` |
| `to_strict_openai(tool)` | `dict` | `openai_function` |
| `build_system_prompt(tools)` | `str` | `system_prompt_text` |
| `read_catalog(tools, parts, contract)` | `Catalog` | `catalog_from_source` |
| `readable_catalog(record)` | `str` | `annotator_catalog_text` |
| `answer_schema_for(catalog)` | `dict` | `answer_space` |
| `record_catalog`, `catalog_names`, `catalog_hash`, `calls_by_name`, `answer_distance`, `vote_consensus`, `training_example`, `scenario_hash`, `question_text`, `validity_checks` | — | unchanged; each already states its result |

### Naming — private

| today | returns | becomes |
|---|---|---|
| `_spec_from(declared, rest)` | `(dict, bool, str \| None)` | `_parsed_parameter`, returning a named tuple instead of a bare triple |
| `_note(gaps, ...)` | appends a `Gap` | `_append_gap` |
| `_says(text, signals)` | `bool` | `_mentions_any` |
| `_coerce(text, declared)` | `Any` | `_typed_value` |
| `_attribute(value)` | `str` | `_xml_attribute_text` |
| `_is_rich(spec)` | `bool` | `_needs_nested_rendering` |
| `_effective_required(parameters)` | `set[str]` | `_required_parameter_names` |
| `_parse_tool(name, body, gaps)` | `Tool` | `_tool_from_text` |
| `_render_tool(tool)` | `str` | `_tool_text` |
| `_argument_fields(tool)` | `str` | `_argument_controls_text` |
| `_arguments(function)` | `Any` | `_call_arguments` |
| `_call_text(calls)` | `str` | `_canonical_call_text` |
| `_one_part(turn)` | `TextPart` | `_turn_as_part` |
| `_percentile`, `_leaves`, `_turn`, `_records` | — | `_percentile_value`, `_leaf_values`, `_turn_text`, `_read_records` |
| `_usable`, `_deduped`, `_split` | `DataFrameSchema` | `_usable_schema`, `_deduped_schema`, `_split_schema` |
| `_parser`, `_profile` (cli) | — | `_argument_parser`, `_named_profile` |
| `_provenance`, `_restated_answer`, `_default_text`, `_parameter_lines`, `_argument_agreement`, `_agreed_arguments` | — | unchanged; each already states its result |

### Order of work

Six commits, each independently verifiable, each leaving the suite green:

1. `shared/` → `core/`, `gates/` flattened, `schemas/` → `artifacts/`, `registry.py` →
   `api/`. Imports only.
2. `core/flow.py`, plus the test that checks it against the core spec's stage table.
3. `tool_decision/` regrouped into the seven files. Moves only — no expression changes.
4. The layout and layering guards (requirements 6, 7, 8, 9).
5. The renames, public then private, plus the denylist additions.
6. `profiles/base.py` and `modalities/base.py` re-ordered and sectioned by phase; docs
   updated: this spec's status, the plan's file table, `engine-api-split` marked
   superseded, and the two stale figures in `docs/profiles/tool-decision/spec.md`.

## Decisions

1. **`shared/` → `core/`, not `base/`.** *Alternatives:* keep `shared/`; call it `base/`.
   *Why:* the docs already say "the core spec" and "core requirements", so `core/` is the
   word this project already uses for what everything is written against; `base/` would
   collide with `profiles/base.py` and `modalities/base.py`, which are contracts, not a
   base layer. Keeping `shared/` keeps the name that cannot reject a candidate. *Reversible:*
   yes — one mechanical rename.
2. **Four phase modules, not the three you named.** You listed `data_quality`,
   `ai_review`, `human_review`, `utils`, `schema`. I am adding `release.py`, because
   `scenario_hash` and `training_example` are `release` work and today they sit in two
   modules named for other phases — the single clearest instance of the problem. Four
   phase modules also make the profile mirror `core/artifacts/`, which already has four.
   *Reversible:* yes, but then those two members need a home and the mirror breaks.
3. **Cross-phase members go in `utils.py` / `schema.py`, not in the earliest phase.**
   *Alternative:* δ in `ai_review.py` and let `human_review.py` import it. *Why not:* it
   makes phase modules import each other, which is the coupling the artifact schemas
   already refuse. *Reversible:* yes.
4. **`registry.py` → `api/` is the weakest move here.** One production caller says it is
   `api/`'s code (§6); a Registry reads like a base type. Recorded as the one I would undo
   first if it reads worse in place. *Reversible:* yes.
5. **`source_contract.py` is dissolved rather than kept.** *Why:* it is a shape plus its
   reader, and requirement 9 puts those in two different files by kind. It costs one
   module in the profile's public vocabulary and buys the seven-file rule having no
   exceptions. *Reversible:* yes.
6. **Protocol member renames are separable and are proposed, not assumed.** `build_record`
   names an operation and `answer_config` says "config" where it returns the capture
   control. Renaming either edits the core spec's requirement text, the rules table,
   `test_protocols.py` and `api/engine.py`. Recommendation: `build_record` →
   `canonical_record`, `answer_config` → `answer_control`, as a seventh commit that this
   spec does not block on. *Assumption:* the other six protocol names stay.
7. **A one-module implementation is exempt until it splits.** `modalities/text/__init__.py`
   is 185 lines and stays one file; when it splits it splits into the same names.
   Requirement 6 binds packages with more than one flow module. *Reversible:* n/a.
8. **`Gap` to `utils.py` and `is_empty` deleted**, folding in the two findings from the
   review of `schema.py` rather than leaving them to drift. Whether the gap *channel*
   survives at all is a separate open decision and is out of scope here.

## Invariants

What must not break, and what proves it:

| invariant | check |
|---|---|
| No behaviour change | 332 tests pass — 298 unit, 34 integration, 1 skipped — with only import lines and names changed in the test files |
| No output change | `metrics/corpus_profile.json` byte-identical before and after; `git diff --stat` on it empty |
| Types still hold | `mypy --strict` clean |
| The engine still opens no file | `test_layering.py` unchanged and passing with `core` substituted for `shared` |
| The library is still not reimplemented | `test_no_reimplementation.py`'s `NOT_OURS` guard passing over the renamed tree |
| Nothing lost in the move | every name in every `__all__` before the change is present after it, or named in the rename table — asserted once, by a test written for the move and deleted with it |

## Testing Strategy

Four new tests, all in the style of the four AST guards that already exist:

- `test_layout.py` — every profile package's file set equals the seven names plus
  `TOOL ·` modules (requirement 6); every phase module's docstring first line matches
  `STEP · <phase> (stages N-M)` and agrees with `core/flow.py` (requirement 7).
- `test_layout.py` — no phase module imports a sibling; `schema.py` imports no `utils.py`
  (requirements 8, 9).
- `test_flow.py` — `core/flow.py`'s phase names equal the phase column of the core spec's
  stage table (requirement 5). Extends `test_naming.py`'s existing table parser, which
  already asserts its own parse is non-empty so it cannot pass vacuously.
- `test_naming.py` — scope widened to include `core/` and private functions; denylist
  grown by every name the rename table removes (requirement 12).

Each guard is proved against synthetic source and run against the tree as it stands
before the change, where it must fail — the discipline `test_layering.py` and
`test_import_graph.py` already document.

## Out of Scope

- Writing any stage. `pipeline/` stays empty; this spec only settles where a stage will
  find what it needs.
- Whether the parser's gap channel survives (see Decision 8) and the pending baseline
  regeneration with its three riders. Both are open decisions, not layout.
- `shared/schemas/` pandera → pydantic. The modules move and are renamed; their contents
  are untouched.
- The `README.md` and `pyproject.toml` staleness, and `docs/dataforce-platform/spec.md`
  and `docs/guided-validation/spec.md`, which this spec neither uses nor supersedes.
- A second profile. The seven-file rule is written so that adding one is mechanical, but
  adding one is not this spec.
