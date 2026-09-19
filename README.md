# DataForce

A collaborative data annotation platform for labeling, reviewing, and validating datasets for AI model training. Teams import raw data, label it against a declarative project schema, review each other's work, and export immutable, versioned snapshots in training-ready formats.

What is built today is one task's flow, end to end: `tool_decision` — eight independent steps over a tool-calling sample, an endpoint per step, and a labelling UI that imports a corpus and walks it a sample at a time. A reviewed record lands in two tables — the whole review, and the de-identified half a buyer gets — and the corpus can be asked what it is short of.

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

With no reachable model you can still import a corpus, walk it, edit labels, tick facets and store records — the personal-data scan and the reviewers' vote are the only steps that need an endpoint.

## Labelling a corpus

There is nothing to configure. Start the service and open <http://localhost:8000/ui/>:

1. **Two ways in.** **Import** (in the header) takes a `.jsonl` — one JSON object per line, `{messages, tools, label}` — and every line becomes a sample waiting to be labelled; importing the same file twice imports nothing the second time, and a line that is not a JSON object is reported by its number while the rest go in. Or **Paste a sample**, in the sample pane itself, for one that came from somewhere else — that path touches no queue at all, so it is the one that works with the store turned off.
2. **Samples** lists the queue: every row with its state, in the order it arrived. Click a row to open it, or tick several and label just those.
3. Each sample opens with the conversation on the left and two decisions on the right: which detected spans really are personal data, and whether the label is right. **Run all checks** does both machine checks in one click — the personal-data scan and the reviewers' vote — and the model each one spends sits on that check's own row. Every span you keep is replaced as you tick, so there is nothing to press for that.
4. Tick what kind of sample it is. **domain** has a box beside it that adds one the list does not carry; an added domain stays offered once a sample is stored with it, because the page reads the values back off the corpus.
5. **Submit** stores the record and opens the next sample. **Skip** passes one over and keeps the row, so a corpus can be asked what was passed over.

The header names the database a record will land in, so you can see where you are writing before you write four hundred rows. It never shows the connection string — a page anyone can open is not a place to put a password — and nothing on the page can change it.

## Where the rows go

`DATAFORCE_DATABASE_URL` names the database. **Unset, it is a SQLite file in the working directory** — `dataforce.sqlite3`, made on startup, gitignored — so an install nobody configured still has somewhere to put a row:

```bash
DATAFORCE_DATABASE_URL=postgresql+psycopg://user:pass@host/db \
  uv run uvicorn dataforce.edge.main:app --reload --port 8000
```

The default is resolved against the working directory, so started from two different directories it is two different corpora. Name the DSN if that matters.

Set it to `off` to run with no store at all: the whole review works with nowhere to put the result, and the routes that keep something say which variable to set rather than failing.

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
