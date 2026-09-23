# DataForce

A collaborative data annotation platform for labeling, reviewing, and validating datasets for AI model training. Teams import raw data, label it against a declarative project schema, review each other's work, and export immutable, versioned snapshots in training-ready formats.

What is built today is one task's flow, end to end: `tool_decision` — eight independent steps over a tool-calling sample, an endpoint per step, and a labelling UI that imports a corpus and walks it a sample at a time. A reviewed record lands in two tables — the whole review, and the de-identified half a buyer gets — and the corpus can be asked what it is short of.

## Running it

Python 3.12 and [uv](https://docs.astral.sh/uv/). Nothing else to install, nothing to create:

```bash
uv run dataforce
```

That serves <http://localhost:8000/ui/>. `uv run` syncs the environment against `uv.lock` itself,
so there is no virtualenv to activate and no `uv sync` to remember, and `dataforce` is a console
script, so an install has it on `PATH` and needs to be told no import path.

**Another port:**

```bash
uv run dataforce --port 8123
```

**Restarting on every source change, while editing:**

```bash
uv run dataforce --reload
```

**Both:**

```bash
uv run dataforce --reload --port 8123
```

`make run` is that last line with `PORT` defaulted to 8000, so `make run` and `make run PORT=8123`
are the same two commands under a shorter name. `uvicorn` is underneath all of them and takes
everything else — a host to bind, a worker count, TLS:

```bash
uv run uvicorn dataforce.edge.main:app --reload --port 8000 --host 0.0.0.0
```

**From the repository root.** `config/prompts/` and `config/model/` are read relative to the working
directory, and so is the database — so starting it elsewhere gives an empty model list, a
`ConfigError` on the first prompt, and a second, empty corpus.

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

A model whose file declares no `base_url` is refused with 422 naming it, before any call is made —
there is no endpoint to ask:

```
422  no-endpoint: no base_url in its config file and none passed, so there is no endpoint to ask
```

Put one in the file. **`LLM_BASE_URL` and `LLM_API_KEY` are not read**: `agent-toolkit` reads them
in its own resolver, and `create_app` replaces that with one over `config/model/` — so every model
carries its own endpoint and there is no environment to inherit one from.

With no reachable model you can still import a corpus, walk it, edit labels, tick facets and store records — the personal-data scan and the reviewers' vote are the only steps that need an endpoint.

## Labelling a corpus

There is nothing to configure. Start the service and open <http://localhost:8000/ui/>:

1. **Two ways in.** **Import** (in the header) takes a `.jsonl` — one JSON object per line, `{messages, tools, label}` — and every line becomes a sample waiting to be labelled; importing the same file twice imports nothing the second time, and a line that is not a JSON object is reported by its number while the rest go in. Or **Paste a sample**, in the sample pane itself, for one that came from somewhere else — that path touches no queue and no database at all, so it is the one that still works
   against a database that cannot be reached.
2. **Samples** lists the queue: every row with its state, in the order it arrived. Click a row to open it, or tick several and label just those.
3. Each sample opens with the conversation on the left and two decisions on the right: which detected spans really are personal data, and whether the label is right. The two machine checks are two buttons — **Find personal data** and **Ask the reviewers** — and the model each one spends is picked on that check's own row, so one can be re-run without paying for the other. Every span you keep is replaced as you tick, so there is nothing to press for that. A value the scan missed is typed in with what kind it is — and the kind can be one the scans never declared, so an address or an account number is redacted as `<ADDRESS_1>` rather than filed as the nearest thing on a list.
4. Tick what kind of sample it is. **domain** has a box beside it that adds one the list does not carry; an added domain stays offered once a sample is stored with it, because the page reads the values back off the corpus.
5. **Submit & next** stores the record and opens the next sample. **Skip** passes one over and keeps the row, so a corpus can be asked what was passed over.

The header names the database a record will land in, so you can see where you are writing before you write four hundred rows. It never shows the connection string — a page anyone can open is not a place to put a password — and nothing on the page can change it.

## Where the rows go

**`dataforce.sqlite3`, in the directory you start the service from** — made on the way to the first
write, gitignored. There is nothing to configure and nothing to create: an install nobody touched
still has somewhere to put a row.

The tables are made on the way to every session, not once at startup, so a database that goes out
from under a running service is made again by the next write. Delete the file mid-afternoon and the
next Submit lands; no restart, and no `500` at the end of a sample somebody just finished reviewing.

Because the default is resolved against the working directory, and resolved once when the process
starts, a service started from two different directories is two different corpora.

**Nothing outside the code names a different database today.** `DATAFORCE_DATABASE_URL` is not read
anywhere — a `Database` is handed a URL or it is the file above, and the only caller that hands one
in is a test. Postgres is one argument away and no seam away: `Database("postgresql+psycopg://…")`
works, and reading that argument from a variable, a flag or a config file is the thing to add the
day a deployment needs it.

A database that is named and cannot be reached is refused rather than quietly replaced with the
default, because a service writing to a second place while the first is down splits the corpus and
nobody finds out until an export comes back short. Every route that keeps something answers `503`
naming the database — never the URL, which carries a password.

## Checks

```bash
make check
```

`ruff check`, `ruff format --check`, `mypy --strict src/dataforce`, and pytest without the
`integration` mark. That is what CI runs and what must pass before a commit. `make integration` is
the rest, and needs a running service.

Every test writes to a database of its own, and the suite reaches for no file in the checkout — so
running it beside your own service leaves that service's corpus alone. It used to delete it.

## Specs

| Doc | What it covers |
|---|---|
| [`docs/tool-decision-pipeline/spec.md`](docs/tool-decision-pipeline/spec.md) | **Start here.** The flow above: what each of the eight steps declares and answers, the endpoint per step, the record at the end, and the two pages — the one that draws the flow and the one that labels with it |
| [`docs/tool-decision-pipeline/plan.md`](docs/tool-decision-pipeline/plan.md) | How it was built: four phases, and what each task settled or withdrew |
| [`AGENTS.md`](AGENTS.md) | The house rules the code is held to, and the guards that enforce them |

`agent-toolkit` — the LLM client and the string, JSON and file utilities everything here is written against — is a dependency and lives in [`giangchicken/agent-toolkit`](https://github.com/giangchicken/agent-toolkit).

The specs this README used to list (the generic annotation pipeline, the platform, guided validation, and the `tool-decision` profile under `docs/profiles/`) were deleted in `cd54228`, when two axes replaced the pipeline. `docs/` holds what stands.
