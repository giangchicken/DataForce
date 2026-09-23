# `make check` is what CI runs and what must pass before a commit. It excludes
# tests marked `integration`, which need the network or a running service.
.PHONY: run check lint types test integration

# The port the labelling UI is served on. `make run PORT=8123` moves it.
PORT ?= 8000

run:
	uv run dataforce --reload --port $(PORT)

check: lint types test

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run mypy --strict src/dataforce

test:
	uv run pytest -q -m "not integration"

integration:
	uv run pytest -q -m integration
