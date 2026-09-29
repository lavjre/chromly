#!/usr/bin/env bash
# acceptance/M1-fuzzilli.sh — M1-01: toolchain + out/fuzzilli REPRL smoke
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

export PATH="$HOME/.local/share/swiftly/bin:$PATH"
FUZZILLI="$HOME/tools/fuzzilli/.build/release/FuzzilliCli"
D8="${CHROMLY_V8_ROOT:-$HOME/v8/v8}/out/fuzzilli/d8"
SMOKE_DIR=/tmp/opencode/m1-fuzzilli-smoke
SMOKE_LOG="$LOG_DIR/fuzzilli-smoke.log"

section "components"
if swift --version >/dev/null 2>&1; then
    pass "swift: $(swift --version 2>&1 | head -1)"
else
    fail "swift thiếu trong PATH"
fi
[[ -x "$FUZZILLI" ]] && pass "FuzzilliCli built" || fail "FuzzilliCli chưa build: $FUZZILLI"
[[ -x "$D8" ]] && pass "out/fuzzilli/d8" || fail "d8 fuzzilli chưa build: $D8"

section "REPRL smoke (maxRuntime=90s)"
if [[ -x "$FUZZILLI" && -x "$D8" ]]; then
    rm -rf "$SMOKE_DIR"
    timeout 240 "$FUZZILLI" --profile=v8 --jobs=1 --storagePath="$SMOKE_DIR" \
        --overwrite --logLevel=info --maxRuntime=90s "$D8" >"$SMOKE_LOG" 2>&1
    rc=$?
    execs="$(grep -oE 'Execs[[:space:]]*/[[:space:]]*Second:[[:space:]]*[0-9.]+' "$SMOKE_LOG" | tail -1)"
    if [[ -n "$execs" ]]; then
        pass "REPRL sống — $execs (rc=$rc, log: $SMOKE_LOG)"
    else
        fail "không thấy execs (rc=$rc) — xem $SMOKE_LOG"
    fi
else
    note "bỏ qua smoke vì thiếu binary"
fi

ac_summary
