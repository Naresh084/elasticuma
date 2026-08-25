#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNTIME_ROOT=${ELASTICUMA_RUNTIME_ROOT:-"$PROJECT_ROOT/.runtime/elasticuma"}
RUNTIME_SOURCE=${ELASTICUMA_RUNTIME_SOURCE:-"https://github.com/dwijenpatel/slipstream.git"}
UPSTREAM_REVISION="01f7d5e774ca940982ea3aa012bd880b5c9d634e"
PATCH_PATH="$PROJECT_ROOT/runtime/patches/elasticuma-purgeable.patch"
PATCH_SHA256="9db7cbc8ce330068f292174e06834af43bf1607091a538d3dbad9f3eba4e1733"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "ElasticUMA requires an Apple-Silicon Mac." >&2
  exit 2
fi
if ! command -v swift >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  echo "Swift and Git are required. Install Xcode 26 or newer first." >&2
  exit 2
fi
if [ ! -f "$PATCH_PATH" ]; then
  echo "bundled runtime patch is missing: $PATCH_PATH" >&2
  exit 2
fi

ACTUAL_PATCH_SHA=$(shasum -a 256 "$PATCH_PATH" | awk '{print $1}')
if [ "$ACTUAL_PATCH_SHA" != "$PATCH_SHA256" ]; then
  echo "bundled runtime patch hash mismatch" >&2
  exit 2
fi

if [ -d "$RUNTIME_ROOT/.git" ]; then
  CURRENT_REVISION=$(git -C "$RUNTIME_ROOT" rev-parse HEAD)
  if [ "$CURRENT_REVISION" != "$UPSTREAM_REVISION" ]; then
    echo "refusing to alter runtime at $CURRENT_REVISION" >&2
    echo "expected pinned upstream $UPSTREAM_REVISION" >&2
    exit 2
  fi
elif [ -e "$RUNTIME_ROOT" ]; then
  echo "refusing to overwrite non-Git path: $RUNTIME_ROOT" >&2
  exit 2
else
  mkdir -p "$(dirname -- "$RUNTIME_ROOT")"
  git clone --no-checkout "$RUNTIME_SOURCE" "$RUNTIME_ROOT"
  git -C "$RUNTIME_ROOT" checkout --detach "$UPSTREAM_REVISION"
fi

if git -C "$RUNTIME_ROOT" diff --cached --quiet \
  && git -C "$RUNTIME_ROOT" diff --quiet \
  && [ -z "$(git -C "$RUNTIME_ROOT" ls-files --others --exclude-standard)" ]; then
  git -C "$RUNTIME_ROOT" apply --check "$PATCH_PATH"
  git -C "$RUNTIME_ROOT" apply --index "$PATCH_PATH"
fi

if ! git -C "$RUNTIME_ROOT" diff --quiet \
  || [ -n "$(git -C "$RUNTIME_ROOT" ls-files --others --exclude-standard)" ]; then
  echo "runtime checkout has unstaged or untracked source changes" >&2
  exit 2
fi
CURRENT_PATCH_SHA=$(git -C "$RUNTIME_ROOT" diff --cached --binary --no-ext-diff | shasum -a 256 | awk '{print $1}')
if [ "$CURRENT_PATCH_SHA" != "$PATCH_SHA256" ]; then
  echo "runtime checkout contains changes beyond the bundled ElasticUMA patch" >&2
  exit 2
fi
git -C "$RUNTIME_ROOT" diff --cached --check

swift build -c release --product slipstream-repack --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream-server --package-path "$RUNTIME_ROOT"

test -x "$RUNTIME_ROOT/.build/release/slipstream-repack"
test -x "$RUNTIME_ROOT/.build/release/slipstream"
test -x "$RUNTIME_ROOT/.build/release/slipstream-server"
echo "ElasticUMA runtime ready at $RUNTIME_ROOT"
echo "upstream=$UPSTREAM_REVISION patch=$PATCH_SHA256"
