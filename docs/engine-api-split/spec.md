# Engine / API split

## What

Split `dataforce` into an **engine** that computes and never touches the filesystem, a **loader** that is the only code reading the `config/` directory, and an **`api/` package** that is the published surface every caller goes through — the CLI included. DVC keeps its data-versioning job and loses its orchestration job: there is no `dvc.yaml` stage DAG and no `dvc repro`, and `api/` sequences the fifteen stages in-process instead. A dataset is versioned when a person decides it is worth versioning, with `dvc add`.

Nothing about what a record is, what an answer is, or what a stage does changes. What changes is who reads files, who orchestrates, and what the reproducibility claim is checked by.

## Context

**Why now.** `dvc.yaml` is `stages: {}` — zero stages, and no `.dvc` files. The entire orchestration story is planned and none of it is built, so this costs a documentation rewrite today and fifteen stage rewrites after Phase 6. T11 is the first task that would commit to it.

**What is wrong today, precisely.** Five places in `src/` read files off hardcoded relative paths:

| where | what |
|---|---|
| `shared/manifest.py:27` | `CONFIG = Path("config")` |
| `shared/prompts.py:29` | `PROMPTS = Path("config/prompts")` |
| `shared/gates/runner.py:40` | `GATES_CONFIG = Path("config/gates.yaml")`, and `check()` writes two files |
| `profiles/tool_decision/build_record.py:57` | `PARAMS = Path("params.yaml")`, read by `max_answer_cardinality` |
| `profiles/tool_decision/measure_corpus.py:39` | reads the corpus, reads and writes `metrics/corpus_profile.json` |

Both axes are also constructed **at import time** — `TEXT = TextModality(manifest.load(...))`, `TOOL_DECISION = ToolDecisionProfile(manifest.load(...))` — so importing the library reads YAML off a relative path. The library therefore only works when the process's cwd is the repo root. An in-process caller (a web handler, a notebook, another codebase) fails on import, which makes an `api/` package impossible as things stand.

Both registries are module-level mutable dicts (`_REGISTRY`), which `tests/conftest.py` has an autouse fixture to snapshot and restore because *"Registration is process-global; a test that registers must not leak."*

**What this overturns.** Four things in the core spec are decided against here, and each is named in *Decisions* below with what replaces it: the tooling table's DVC row (`spec.md:54`), the Decision *"The pipeline is DVC stages, not a service"* (`spec.md:581`), invariant 14 (`spec.md:618`), and the definition of done (`spec.md:670`). `plan.md` mentions `dvc repro` 22 times, 14 of them in the *Verify* line of a task.

**Blast radius, measured.** 8 test files import a singleton; 5 source sites do file I/O; 30 source modules exist today.

## Requirements

1. **No module under `modalities/`, `profiles/`, `pipeline/` or `shared/` performs file I/O.** No `open()`, no `Path` literal naming a config or data location, no import from `agent_toolkit.file_utils`. Checkable by AST over the source tree.
2. **Neither axis is constructed at import time.** Importing `dataforce.profiles.tool_decision` reads no file and touches no network. A modality or profile is built by being handed an already-parsed `Manifest`.
3. **`dataforce.declared` is the only package that reads `config/`.** It returns objects the engine accepts and imports nothing from `pipeline/`.
4. **Every path is a required parameter with no module-level default.** A function that needs a file location is told one; it never infers one from cwd.
5. **`api/` is the only surface a caller outside `src/dataforce` imports.** `cli.py` is a thin argparse shell over it and holds no behaviour of its own beyond argument parsing, logging setup, and exit codes.
6. **Registries hold no module-level state.** A `Registry` is an object; two of them can coexist in one process with different contents.
7. **A gate raises with its results and writes nothing.** Persisting a gate's verdict is the caller's job.
8. **`dvc.yaml` declares no stages** and `dvc repro` is not how anything runs. DVC is used for `dvc add` / `push` / `pull` only.
9. **Every run writes a run manifest** recording the SHA-256 of every policy file it read, the `name@version` of both axes, and the SHA-256 of every artifact it wrote. This is what replaces DVC's declared-dependency lineage.
10. **Two runs of the same command from a clean checkout produce byte-identical artifacts,** proved by diffing the run manifests. This replaces invariant 14 and is the new definition of the pipeline being done.

## Design

### Layers, and who may import whom

```
              api/          the published surface; orchestrates, persists
                │
       ┌────────┼─────────────────┐
       ▼        ▼                 ▼
  declared/   pipeline/       cli.py  (argparse only)
  reads       the fifteen
  config/     stages, pure
                │
       ┌────────┴────────┐
       ▼                 ▼
  modalities/        profiles/          ← engine: no I/O, no cwd
       └────────┬────────┘
                ▼
             shared/                    ← engine: no I/O, no cwd
```

The arrow direction is the whole rule: **`api/` and `declared/` may import the engine; the engine may not import them.** `declared/` and `pipeline/` do not import each other.

### File changes

```
src/dataforce/
├── api/                          NEW
│   ├── __init__.py               the surface: one function per stage, records in → records out
│   ├── engine.py                 Engine — a resolved (modality, profile, policy) triple
│   └── artifacts.py              the only place an artifact is read or written
├── declared/                     NEW — the only package that reads config/
│   ├── manifest.py               was shared/manifest.py, unchanged but for the default path
│   ├── prompts.py                was shared/prompts.py; load → read_prompt, render → fill_prompt
│   └── thresholds.py             was gates/runner.thresholds
├── modalities/                   unchanged, minus the import-time TEXT
├── profiles/                     unchanged, minus the import-time TOOL_DECISION
├── pipeline/                     the fifteen stages, each a pure function over records
├── shared/
│   ├── record.py                 unchanged
│   ├── registry.py               NEW — one Registry class, replacing both module globals
│   └── gates/runner.py           raises; writes nothing
└── cli.py                        argparse over api/
```

Six named changes to existing code:

1. `manifest.load(axis, name, *, root=CONFIG)` → `declared.manifest.read_manifest(axis, name, *, root)` — `root` required.
2. `prompts.load` / `prompts.render` → `declared.prompts.read_prompt` / `fill_prompt`, `root` required. This also closes the naming exemption R1 recorded: `prompts.load` shared a name with stage 0 and `render` was a bare operation, and both were left alone because they sat in `shared/`.
3. `validity_checks(contract, *, params=PARAMS)` → `validity_checks(contract, *, ceiling: int)`. `max_answer_cardinality` moves to `declared/`.
4. `corpus_measurements(path, modality, profile)` → `corpus_measurements(raw_items: Iterable[Mapping], modality, profile, *, digest: str)`. The file reading and the baseline read/write move to `api/`; the measuring stays in the profile.
5. `gates.runner.check(stage, results, *, out_dir)` → `assert_gates(stage, results)`, which raises `GateFailed` carrying the results and writes nothing. `api/` writes `metrics.json` and `GATE_FAILED.json`. `require_upstream_ok` moves to `api/artifacts.py` — it is a filesystem check.
6. Both `registry` modules collapse into one `Registry` class in `shared/registry.py`, holding instance state. The autouse `_isolated_registries` fixture in `tests/conftest.py` is deleted, because there is no longer global state to leak.

### How a run works

```python
from dataforce import api

engine = api.open_engine(modality="text", profile="tool_decision", config_root=Path("config"))

# all fifteen
result = api.run(engine, source=Path("data/raw/corpus.json"))

# or the stages you name
result = api.run(engine, source=Path("data/raw/corpus.json"), stages=("embed", "dedup"))

# or no filesystem at all
records = list(api.build_records(engine, raw_items))
```

`api.run` sequences stages by name, calling each `pipeline/` function with the previous one's records, asserting its gate between them, and writing each artifact through `api/artifacts.py`. `api.build_records` is the same engine with no filesystem in sight — raw dicts in, records out, no path named.

`stages=` exists because the fifteen stages are a sequence and a person stops at the end of a phase, or re-does one stage after fixing it. On the CLI it is positional -- `dataforce run` runs all fifteen, `dataforce run embed dedup` runs two. It is not caching: a run that starts mid-sequence re-reads the artifact the previous run wrote.

### Versioning, in place of `dvc repro`

`dvc.yaml` keeps its header comment and `stages: {}`, so `test_repo_hygiene.py::test_raw_tier_is_outside_dvc` keeps working and the file records why it is empty. Versioning is a deliberate act at a milestone:

```
$ dataforce run load remove_invalid pii_check embed dedup
$ dvc add data/interim/3_human_review/curated.jsonl
$ git add -A && git commit -m "annotation round 2"
$ dvc push
```

`.dvc` files start appearing, which makes the vault-hygiene test (`data/raw` in no `.dvc` file) meaningful rather than vacuous.

### Order of work

Each step leaves the suite green.

1. `Registry` class; delete both module globals and the conftest fixture. *No behaviour change.*
2. Move `manifest.py`, `prompts.py`, `thresholds` into `declared/`, paths required. Add a session-scoped conftest fixture building `TEXT` and `TOOL_DECISION` from the real `config/`, so the 8 test files change one import each.
3. Remove the import-time singletons; `cli.py` becomes the composition root.
4. Inject `ceiling`; split `measure_corpus`; make gates raise-only.
5. Add the guard test. It must fail on the tree before step 1 and pass after step 4.
6. Add `api/` with the surface that exists today (`open_engine`, `build_records`, `measure_corpus`), and point `cli.py` at it.
7. Rewrite the 22 `dvc repro` references in `plan.md` and the four core-spec statements listed in *Decisions*.

## Decisions

**DVC versions data; it does not orchestrate.** *Choice:* no `dvc.yaml` stages, no `dvc repro`; `api/` sequences stages in-process and `dvc add` versions artifacts when a person chooses. *Alternatives:* keep both jobs with `pipeline/` stages as thin shells over `api/` (the recommendation this decision overrides); keep both and let `api/` be a second path; Airflow/Prefect. *Why:* a DVC stage is a process invocation, so if DVC orchestrates then `api/` is permanently a second path that has to be kept in step with the one the tests exercise — one behaviour, two implementations. *What it costs, stated once:* stage-level caching. `dvc repro` skipping an unchanged stage was free; now nothing is. The expensive case is partly covered because stage 5's vote cache on `(rid, model, prompt_version)` was always planned independently of DVC, and naming stages lets a person re-do one without re-doing the corpus. If a stage becomes slow enough to need real caching, the fix is a content-addressed cache inside that stage, not a DAG above it. *Reversible:* yes — every stage stays a pure function from records to records, so a `dvc.yaml` calling `dataforce run <stage>` could be added later without touching one of them.

**Overturned in the core spec, with the replacement.** `spec.md:54`'s tooling row narrows to "data versioning" only. `spec.md:581` (*"The pipeline is DVC stages, not a service"*) is replaced by this decision, keeping its reasoning that stages are pure functions — which is what makes in-process sequencing work. Invariant 14 (*"`dvc repro` from a clean checkout reproduces every artifact's SHA-256"*) becomes *"two `dataforce run` invocations from a clean checkout produce byte-identical artifacts, diffed through the run manifest"* — the same claim, no longer depending on DVC's cache being correct. `spec.md:670`'s definition of done changes verb and nothing else. `spec.md:455`'s argument for thresholds living in `params.yaml` loses its "declared DVC dependency" half; the committed-and-reviewable half stands, and requirement 9 restores attributability by recording every policy file's digest in the run manifest.

**The engine receives parsed data, not paths.** *Choice:* the engine takes `Manifest` objects, ints, and strings; `declared/` turns files into those. *Alternatives:* the engine keeps reading YAML but every path is an injected parameter. *Why:* injected paths still put the filesystem inside the engine, so an `api/` caller must materialise config on disk and the engine cannot be tested without a tmpdir. *Reversible:* yes, but going back re-introduces the cwd dependency.

**One `Registry` class, no module-level registry.** *Choice:* instance state. *Alternatives:* keep the globals and have `api/` resolve through them; keep the globals with an injectable dict. *Why:* the globals already needed a test fixture to contain them, and one process serving two configurations is exactly what an `api/` package invites. *Reversible:* yes.

**`api/` is a Python surface; HTTP is a later task over it.** *Choice:* no web framework, no endpoints, no dependency added now. *Alternatives:* FastAPI now. *Why:* an HTTP layer over a surface that does not exist yet would fix its request shapes before the surface is known, and it forces an auth decision this spec has no input for. *Reversible:* n/a — it is additive.

**`Assumption:` the fifteen stage names, the phases, and what each artifact contains are unchanged.** This spec moves who calls what. If a stage's *content* needs to change, that is a different spec.

**`Assumption:` `declared/` is the package name.** It matches the vocabulary already in the code (`Manifest.declared`, `manifest.require`). `config/` was rejected as a Python package name because a data directory called `config/` already exists and the spec says it is "never imported as Python".

## Invariants

1. No module under `modalities/`, `profiles/`, `pipeline/`, `shared/` opens a file. *Check:* AST guard over `SOURCE_ROOT`, asserting the guarded set is non-empty so it cannot pass vacuously.
2. Importing any engine module reads no file. *Check:* a subprocess importing `dataforce.profiles.tool_decision` from a cwd that is not the repo root, and succeeding.
3. Nothing under `pipeline/` or `shared/` imports a concrete modality or profile. *Check:* `test_import_graph.py`, unchanged.
4. The engine does not import `api/` or `declared/`. *Check:* the same import-graph test, extended.
5. `data/raw/` is in no `.dvc` file and in `.gitignore`. *Check:* `test_repo_hygiene.py`, unchanged — and no longer vacuous once `dvc add` is in use.
6. Two runs of one command produce byte-identical artifacts. *Check:* the end-to-end test, on the smoke fixture.

## Error Behavior

- **A gate fails.** `assert_gates` raises `GateFailed` carrying every `GateResult`. `api/` catches it, writes `metrics.json` and `GATE_FAILED.json` into the stage directory, and re-raises. `cli.py` catches it once and exits non-zero. A caller using `api/` in-process gets the exception with the results attached and no files written unless it asked for a filesystem run.
- **A stage's upstream failed.** `api/artifacts.py` refuses to read an artifact whose directory holds `GATE_FAILED.json`, as `require_upstream_ok` does today.
- **Config is missing or malformed.** `ConfigError` from `declared/`, naming the path and what the file does hold — the existing messages move unchanged.
- **A run is asked for an unknown stage name.** `ConfigError` naming the fifteen, raised before any work starts.
- **A profile's declared modality differs from the requested one.** `ConfigError`, never coerced. Unchanged, and it moves from the registry module to `Registry.get`.

## Testing Strategy

- **The guard test is the centrepiece.** An AST walk over `src/dataforce` asserting no guarded module contains `open(`, a `Path(...)` literal pointing into `config/`, `data/` or `metrics/`, or an import from `agent_toolkit.file_utils`. It must be shown to fail on the tree it was written against — five sites — the way `test_naming.py`'s guards were.
- **Import purity, as a subprocess.** `cwd=tmp_path`, `python -c "import dataforce.profiles.tool_decision"`. This is the test that would have caught the problem this spec exists to fix, and it cannot be written as an in-process assertion.
- **Two registries in one process,** holding different profiles, neither seeing the other's.
- **Every existing test keeps its assertions.** The 8 files importing a singleton change their import to a fixture and nothing else. The count moves only by the tests added here.
- **Reproducibility.** Two `api.run` invocations over the smoke fixture, diffing run manifests.
- **What is not covered.** Nothing replaces `dvc repro`'s caching, so no test asserts a second run is *fast* — only that it is *identical*.

## Out of Scope

- **The HTTP service.** Named as a later task that wraps `api/` without touching the engine.
- **`shared/schemas/` (pandera → pydantic).** A separate spec — but largely decided by this one: with DVC orchestration gone and the engine format-agnostic, file-level DataFrame validation has no place inside the engine at all. What survives is the per-row shape claims, which belong with `Record` and with the seven non-record artifacts that have no model today.
- **Implementing any stage.** T11 onward is unaffected in content; only its *Verify* line changes.
- **Renaming stages, or changing what any artifact contains.**
- **Replacing DVC for versioning.** It keeps that job.
