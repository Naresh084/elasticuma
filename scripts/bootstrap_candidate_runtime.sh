#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ELASTICUMA_CACHE_ROOT=${ELASTICUMA_CACHE_ROOT:-"$HOME/Library/Caches/elasticuma"}
RUNTIME_ROOT=${ELASTICUMA_RUNTIME_ROOT:-"$ELASTICUMA_CACHE_ROOT/runtime"}
RUNTIME_SOURCE=${ELASTICUMA_RUNTIME_SOURCE:-"https://github.com/dwijenpatel/slipstream.git"}
UPSTREAM_REVISION="01f7d5e774ca940982ea3aa012bd880b5c9d634e"
MECHANISM_PATCH_PATH="$PROJECT_ROOT/runtime/patches/elasticuma-purgeable.patch"
APP_PATCH_PATH="$PROJECT_ROOT/runtime/patches/elasticuma-app.patch"
MECHANISM_PATCH_SHA256="433f38c094aca85701129bdaa9b1e3397a0a7f8f45759c4af2050f2f0bdfbde9"
APP_PATCH_SHA256="d02b916072148f6fe8c05ad8352a767f828e0eaea0c8ee010d16f52c1666e4de"
PATCHSET_SHA256="a009e905b3483f9e894cc8627a58de1353437565b22f3e13107364c7acb4739b"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "ElasticUMA requires an Apple-Silicon Mac." >&2
  exit 2
fi
if ! command -v swift >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  echo "Swift and Git are required. Install Xcode 26 or newer first." >&2
  exit 2
fi
for PATCH_PATH in "$MECHANISM_PATCH_PATH" "$APP_PATCH_PATH"; do
  if [ ! -f "$PATCH_PATH" ]; then
    echo "bundled runtime patch is missing: $PATCH_PATH" >&2
    exit 2
  fi
done

ACTUAL_MECHANISM_SHA=$(shasum -a 256 "$MECHANISM_PATCH_PATH" | awk '{print $1}')
ACTUAL_APP_SHA=$(shasum -a 256 "$APP_PATCH_PATH" | awk '{print $1}')
if [ "$ACTUAL_MECHANISM_SHA" != "$MECHANISM_PATCH_SHA256" ]; then
  echo "bundled mechanism patch hash mismatch" >&2
  exit 2
fi
if [ "$ACTUAL_APP_SHA" != "$APP_PATCH_SHA256" ]; then
  echo "bundled app patch hash mismatch" >&2
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
  git -C "$RUNTIME_ROOT" apply --check "$MECHANISM_PATCH_PATH"
  git -C "$RUNTIME_ROOT" apply --index "$MECHANISM_PATCH_PATH"
  git -C "$RUNTIME_ROOT" apply --check "$APP_PATCH_PATH"
  git -C "$RUNTIME_ROOT" apply --index "$APP_PATCH_PATH"
fi

if ! git -C "$RUNTIME_ROOT" diff --quiet \
  || [ -n "$(git -C "$RUNTIME_ROOT" ls-files --others --exclude-standard)" ]; then
  echo "runtime checkout has unstaged or untracked source changes" >&2
  exit 2
fi
CURRENT_PATCH_SHA=$(git -C "$RUNTIME_ROOT" diff --cached --binary --no-ext-diff | shasum -a 256 | awk '{print $1}')
if [ "$CURRENT_PATCH_SHA" != "$PATCHSET_SHA256" ]; then
  echo "runtime checkout contains changes beyond the bundled ElasticUMA patch set" >&2
  exit 2
fi
git -C "$RUNTIME_ROOT" diff --cached --check

swift build -c release --product slipstream-repack --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream-server --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream-decode-service --package-path "$RUNTIME_ROOT"
swift build -c release --product slipstream-mac --package-path "$RUNTIME_ROOT"

test -x "$RUNTIME_ROOT/.build/release/slipstream-repack"
test -x "$RUNTIME_ROOT/.build/release/slipstream"
test -x "$RUNTIME_ROOT/.build/release/slipstream-server"
test -x "$RUNTIME_ROOT/.build/release/slipstream-decode-service"
test -x "$RUNTIME_ROOT/.build/release/slipstream-mac"
echo "ElasticUMA runtime ready at $RUNTIME_ROOT"
echo "upstream=$UPSTREAM_REVISION patchset=$PATCHSET_SHA256"
