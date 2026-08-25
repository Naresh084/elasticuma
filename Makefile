.PHONY: bootstrap runtime runtime-upstream native test lint check doctor smoke gate1 analyze paper-clean

bootstrap:
	uv sync --extra dev

runtime:
	./scripts/bootstrap_candidate_runtime.sh

runtime-upstream:
	./scripts/bootstrap_runtime.sh

native:
	./scripts/build_native.sh

test:
	uv run pytest

lint:
	uv run ruff check .

check: lint test

doctor:
	uv run elasticuma doctor --json

smoke:
	./scripts/smoke_qwen36.sh

gate1:
	uv run elasticuma experiment validate-config --config configs/gate1.v4.example.toml

analyze:
	uv run elasticuma experiment analyze --input artifacts/admitted

paper-clean:
	rm -rf paper/latex/build
