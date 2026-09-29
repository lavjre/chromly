#!/usr/bin/env bash
# infra/fuzzilli-setup.sh — cài deps node cho JS→FuzzIL parser (chạy sau khi build fuzzilli)
# Dùng bởi: corpus sync (M1-06). Idempotent.
set -euo pipefail

FZ="${FUZZILLI_DIR:-$HOME/tools/fuzzilli}"

if [[ ! -d "$FZ" ]]; then
    echo "fuzzilli chưa clone: $FZ" >&2
    exit 1
fi

echo "== parser deps (source) =="
(cd "$FZ/Sources/Fuzzilli/Compiler/Parser" && npm i --silent)

BUNDLE="$(find "$FZ/.build" -type d -name 'Fuzzilli_Fuzzilli.bundle' 2>/dev/null | head -1)"
if [[ -n "$BUNDLE" ]]; then
    echo "== parser deps (bundle: $BUNDLE/Parser) =="
    (cd "$BUNDLE/Parser" && npm i --silent)
else
    echo "bundle chưa có — build fuzzilli trước: (cd $FZ && swift build -c release)" >&2
    exit 1
fi

echo "fuzzilli parser setup OK"
