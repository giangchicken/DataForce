# DataForce

A collaborative data annotation platform for labeling, reviewing, and validating datasets for AI model training. Teams import raw data, label it against a declarative project schema, review each other's work, and export immutable, versioned snapshots in training-ready formats.

What is built today is one task's flow, end to end: `tool_decision` — eight independent steps over a tool-calling sample, an endpoint per step, and a labelling UI that walks one sample through all of them. Nothing stores a record yet; the flow's last answer is the record the UI assembles, and the store is deferred.

## Running it

Python 3.12 and [uv](https://docs.astral.sh/uv/). `uv run` syncs the environment against `uv.lock` itself, so there is no virtualenv to activate and no `uv sync` to remember:

```bash
uv run uvicorn dataforce.edge.main:app --reload --port 8000
```

From the repository root: `config/prompts/` and `config/model/` are read relative to the working directory, so starting it elsewhere gives an empty model list and a `ConfigError` on the first prompt.

| | |
|---|---|
| the labelling UI | <http://localhost:8000/ui/> |
| the flow, drawn and explained | <http://localhost:8000/text2text/tool-decision/> |
| the API | <http://localhost:8000/docs> |

## Which models answer

A model is served when `config/model/<model name>.json` exists. That directory *is* the list — `GET /text2text/tool-decision/models` reads it per call, and the UI's tick lists are that answer, asked for again whenever you come back to the tab, so a file added while the service is up needs no restart and no reload.

Those files are the deployment's own and are gitignored: a file naming an endpoint and holding a key is never committed. One looks like this, and everything but `model` is optional:

```json
{
  "model": "gemma-4-31B-it",
  "base_url": "https://your-endpoint/v1",
  "api_key": "...",
  "temperature": 0.0,
  "max_concurrency": 8
}
```

`DATAFORCE_MODEL_DIR` points somewhere else if you keep them outside the repository.

A model whose file declares no `base_url` is refused with 422 naming it, before any call is made — there is no endpoint to ask. Either put one in the file, or leave both to the environment and let every model share them:

```bash
LLM_BASE_URL=https://your-endpoint/v1 LLM_API_KEY=... \
  uv run uvicorn dataforce.edge.main:app --reload --port 8000
```

With no reachable model you can still drive the sample, the two checks that report nothing, the label editor and the record — the two model steps are the only ones that need an endpoint.

## Checks

```bash
make check
```

`ruff check`, `ruff format --check`, `mypy --strict src/dataforce`, and pytest without the `integration` mark. That is what CI runs and what must pass before a commit. `make integration` is the rest, and needs a running service.

## Specs

| Doc | What it covers |
|---|---|
| [`docs/tool-decision-pipeline/spec.md`](docs/tool-decision-pipeline/spec.md) | **Start here.** The flow above: what each of the eight steps declares and answers, the endpoint per step, the record at the end, and the two pages — the one that draws the flow and the one that labels with it |
| [`docs/tool-decision-pipeline/plan.md`](docs/tool-decision-pipeline/plan.md) | How it was built: four phases, and what each task settled or withdrew |
| [`AGENTS.md`](AGENTS.md) | The house rules the code is held to, and the guards that enforce them |

`agent-toolkit` — the LLM client and the string, JSON and file utilities everything here is written against — is a dependency and lives in [`giangchicken/agent-toolkit`](https://github.com/giangchicken/agent-toolkit).

The specs this README used to list (the generic annotation pipeline, the platform, guided validation, and the `tool-decision` profile under `docs/profiles/`) were deleted in `cd54228`, when two axes replaced the pipeline. `docs/` holds what stands.
