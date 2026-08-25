#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ELASTICUMA_CACHE_ROOT=${ELASTICUMA_CACHE_ROOT:-"$HOME/Library/Caches/elasticuma"}
RUNTIME_ROOT=${1:-${ELASTICUMA_RUNTIME_ROOT:-"$ELASTICUMA_CACHE_ROOT/runtime"}}
CONFIGURATION=${2:-release}
OUTPUT_ROOT=${3:-"$PROJECT_ROOT/dist"}
OUTPUT_APP="$OUTPUT_ROOT/ElasticUMA.app"

if [ ! -f "$RUNTIME_ROOT/Package.swift" ]; then
  echo "ElasticUMA runtime is missing at $RUNTIME_ROOT" >&2
  echo "Run 'euma runtime install' first." >&2
  exit 2
fi
if [ "$CONFIGURATION" != "debug" ] && [ "$CONFIGURATION" != "release" ]; then
  echo "configuration must be debug or release" >&2
  exit 2
fi

swift build -c "$CONFIGURATION" --product slipstream-mac --package-path "$RUNTIME_ROOT"
swift build -c "$CONFIGURATION" --product slipstream-decode-service --package-path "$RUNTIME_ROOT"
swift build -c "$CONFIGURATION" --product slipstream-server --package-path "$RUNTIME_ROOT"
BIN_ROOT=$(swift build -c "$CONFIGURATION" --show-bin-path --package-path "$RUNTIME_ROOT")

STAGING_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/elasticuma-app.XXXXXX")
trap 'rm -rf "$STAGING_ROOT"' EXIT
STAGING_APP="$STAGING_ROOT/ElasticUMA.app"
mkdir -p "$STAGING_APP/Contents/MacOS"

install -m 755 "$BIN_ROOT/slipstream-mac" "$STAGING_APP/Contents/MacOS/ElasticUMA"
install -m 755 "$BIN_ROOT/slipstream-decode-service" "$STAGING_APP/Contents/MacOS/slipstream-decode-service"
install -m 755 "$BIN_ROOT/slipstream-server" "$STAGING_APP/Contents/MacOS/slipstream-server"
install -m 644 "$PROJECT_ROOT/macos/Info.plist" "$STAGING_APP/Contents/Info.plist"

for BUNDLE in "$BIN_ROOT"/*.bundle; do
  [ -d "$BUNDLE" ] || continue
  case "$(basename "$BUNDLE")" in
    *Tests*) continue ;;
  esac
  ditto "$BUNDLE" "$STAGING_APP/$(basename "$BUNDLE")"
done

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - --no-strict "$STAGING_APP"
fi

mkdir -p "$OUTPUT_ROOT"
if [ -e "$OUTPUT_APP" ]; then
  rm -rf "$OUTPUT_APP"
fi
mv "$STAGING_APP" "$OUTPUT_APP"
echo "ElasticUMA app ready: $OUTPUT_APP"
