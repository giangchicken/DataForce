# DataForce

A collaborative data annotation platform for labeling, reviewing, and validating datasets for AI model training. Teams import raw data, label it against a declarative project schema, review each other's work, and export immutable, versioned snapshots in training-ready formats.

Status: **specification**. No implementation yet.

## Specs

| Spec | What it covers |
|---|---|
| [`docs/sft-dataset-pipeline`](docs/sft-dataset-pipeline/spec.md) | **Start here.** The end-to-end workflow that produces a released SFT dataset — gated DVC stages over existing open source, with the annotation surface on Label Studio |
| [`docs/agent-toolkit`](docs/agent-toolkit/spec.md) | Shared Python library — LLM client, JSON/string/file utilities. Built and released in [`giangchicken/agent-toolkit`](https://github.com/giangchicken/agent-toolkit); the spec and plan stay here because the other three specs depend on them |
| [`docs/guided-validation`](docs/guided-validation/spec.md) | Presentation mode serving LLM-generated validation questions one at a time |
| [`docs/dataforce-platform`](docs/dataforce-platform/spec.md) | Core platform — projects, label schemas, task distribution, review, agreement metrics, export, dataset catalog and subscriptions. Deferred behind the pipeline's Label Studio v0 |

Build order: `agent-toolkit` → `sft-dataset-pipeline` (smoke → pilot → scale) → the platform, if the pilot shows it is needed.

`agent-toolkit` 0.1.0 is done and lives in its own repository. Everything below it is still specification, so this repository holds no code.
