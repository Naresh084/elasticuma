#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNTIME_ROOT="$PROJECT_ROOT/.runtime/slipstream"
RUNTIME_REPO="https://github.com/dwijenpatel/slipstream.git"
RUNTIME_REVISION="01f7d5e774ca940982ea3aa012bd880b5c9d634e"

if [ -d "$RUNTIME_ROOT/.git" ]; then
  CURRENT_REVISION=$(git -C "$RUNTIME_ROOT" rev-parse HEAD)
  if [ "$CURRENT_REVISION" != "$RUNTIME_REVISION" ]; then
    echo "refusing to alter an existing runtime checkout at $CURRENT_REVISION" >&2
    echo "expected $RUNTIME_REVISION at $RUNTIME_ROOT" >&2
    exit 2
  fi
elif [ -e "$RUNTIME_ROOT" ]; then
  echo "refusing to overwrite non-Git path: $RUNTIME_ROOT" >&2
  exit 2
else
  mkdir -p "$PROJECT_ROOT/.runtime"
  git clone --filter=blob:none --no-checkout "$RUNTIME_REPO" "$RUNTIME_ROOT"
  git -C "$RUNTIME_ROOT" fetch --depth 1 origin "$RUNTIME_REVISION"
  git -C "$RUNTIME_ROOT" checkout --detach "$RUNTIME_REVISION"
fi

git -C "$RUNTIME_ROOT" diff --quiet
git -C "$RUNTIME_ROOT" diff --cached --quiet

swift build -c release --product slipstream --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream-repack --package-path "$RUNTIME_ROOT"

if [ "${ELASTICUMA_RUN_UPSTREAM_TESTS:-0}" = "1" ]; then
  "$RUNTIME_ROOT/Scripts/test.sh"
fi

ACTUAL_REVISION=$(git -C "$RUNTIME_ROOT" rev-parse HEAD)
test "$ACTUAL_REVISION" = "$RUNTIME_REVISION"
test -x "$RUNTIME_ROOT/.build/release/slipstream"
test -x "$RUNTIME_ROOT/.build/release/slipstream-repack"
echo "pinned runtime ready: $ACTUAL_REVISION"
