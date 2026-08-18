# DataForce

A collaborative data annotation platform for labeling, reviewing, and validating datasets for AI model training. Teams import raw data, label it against a declarative project schema, review each other's work, and export immutable, versioned snapshots in training-ready formats.

Status: **specification**. No implementation yet.

## Specs

| Spec | What it covers |
|---|---|
| [`docs/annotation-pipeline`](docs/annotation-pipeline/spec.md) | **Start here.** The generic gated pipeline — fifteen DVC stages over existing open source, with the annotation surface on Label Studio. Task- and modality-agnostic: a run is one modality × one profile |
| [`docs/profiles/tool-decision`](docs/profiles/tool-decision/spec.md) | The first profile and the first dataset — tool selection over 21,172 Vietnamese call-centre conversations. Holds the corpus measurements, the marker DSL, Vietnamese PII, the jury panel, and the thresholds |
| [`docs/agent-toolkit`](docs/agent-toolkit/spec.md) | Shared Python library — LLM client, JSON/string/file utilities. Built and released in [`giangchicken/agent-toolkit`](https://github.com/giangchicken/agent-toolkit); the spec and plan stay here because the other three specs depend on them |
| [`docs/guided-validation`](docs/guided-validation/spec.md) | Presentation mode serving LLM-generated validation questions one at a time |
| [`docs/dataforce-platform`](docs/dataforce-platform/spec.md) | Core platform — projects, label schemas, task distribution, review, agreement metrics, export, dataset catalog and subscriptions. Deferred behind the pipeline's Label Studio v0 |

Build order: `agent-toolkit` → `annotation-pipeline` + the `tool-decision` profile (smoke → pilot → scale) → the platform, if the pilot shows it is needed.

## Plans

| Plan | Covers |
|---|---|
| [`docs/annotation-pipeline/plan.md`](docs/annotation-pipeline/plan.md) | **Next up.** Six phases, 33 tasks, from an empty repository to a reproducible `release/v1` — the core and the `tool-decision` profile together, since neither is buildable alone |
| [`docs/agent-toolkit/plan.md`](docs/agent-toolkit/plan.md) | Done. The library, released as v0.1.0 |

`agent-toolkit` 0.1.0 is done and lives in its own repository. Everything below it is still specification, so this repository holds no code.
