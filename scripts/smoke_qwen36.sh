#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

ADMITTED="$PROJECT_ROOT/artifacts/admitted/smoke-m1max-qwen36-q4.json"
if [ -e "$ADMITTED" ]; then
  echo "refusing to overwrite an existing smoke artifact: $ADMITTED" >&2
  echo "inspect it or create a newly named config after documenting the reason" >&2
  exit 2
fi

uv run elasticuma model packed-preflight
./scripts/build_native.sh
uv run elasticuma experiment validate-config --config configs/smoke.example.toml
uv run elasticuma experiment run --config configs/smoke.example.toml

jq '{complete, measured_count, admitted_count, decisions}' "$ADMITTED"
jq -e '.complete == true and .measured_count == 2 and .admitted_count == 2' "$ADMITTED" \
  >/dev/null
echo "smoke evidence admitted: $ADMITTED"
