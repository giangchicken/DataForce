# `make check` is what CI runs and what must pass before a commit. It excludes
# tests marked `integration`, which need the network or a running service.
.PHONY: check lint types test integration repro

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

repro:
	uv run dvc repro
