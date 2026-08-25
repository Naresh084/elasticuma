.PHONY: install bootstrap runtime test lint check doctor paper-clean

install:
	./install.sh

bootstrap:
	uv sync --extra dev

runtime:
	./scripts/bootstrap_candidate_runtime.sh

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

check: lint test

doctor:
	uv run elasticuma doctor --json

paper-clean:
	rm -rf paper/latex/build
