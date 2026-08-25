#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "ElasticUMA requires an Apple-Silicon Mac." >&2
  exit 2
fi

for tool in git swift python3 uv; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 2
  fi
done

if [ "$#" -gt 1 ]; then
  echo "usage: ./install.sh [model-id]" >&2
  exit 2
fi

cd "$PROJECT_ROOT"
uv sync --locked
uv run euma runtime install

if [ "$#" -eq 1 ]; then
  uv run euma setup "$1"
else
  echo
  echo "ElasticUMA is installed. Next:"
  echo "  uv run euma app open"
  echo "  uv run euma models"
  echo "  uv run euma setup qwen36"
fi
