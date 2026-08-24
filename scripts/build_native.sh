#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
swift build -c release --package-path "$PROJECT_ROOT/native" \
  --product elasticuma-pressure-monitor

BINARY="$PROJECT_ROOT/native/.build/release/elasticuma-pressure-monitor"
test -x "$BINARY"
echo "native pressure monitor ready: $BINARY"
