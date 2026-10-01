#!/usr/bin/env bash
# acceptance/M1-libfuzzer.sh — M1-03: build out/libfuzzer + replay lane (fallback v0)
#   Engine thật (mutation/coverage) = M1-engine.sh (M1-08). Đây là lane replay
#   toàn corpus — chạy 1 lượt mỗi unit, không đụng farm (không up/down).
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

OUT="${CHROMLY_V8_ROOT:-$HOME/v8/v8}/out/libfuzzer"

section "build (incremental nếu đã có)"
if "$VENV_BIN/chromly" build --config libfuzzer >"$LOG_DIR/m1-libfuzzer-build.log" 2>&1; then
    pass "chromly build --config libfuzzer"
else
    fail "build lỗi — tail $LOG_DIR/m1-libfuzzer-build.log"
fi

section "binaries"
for f in v8_simple_parser_fuzzer v8_simple_wasm_module_fuzzer; do
    [[ -x "$OUT/$f" ]] && pass "$f" || fail "thiếu $OUT/$f"
done

section "replay fallback — 1 lượt mỗi unit"
for u in libfuzzer-parser libfuzzer-wasm; do
    L="$LOG_DIR/m1-libfuzzer-$u.log"
    timeout 900 "$VENV_BIN/chromly" fuzz lfreplay --unit "$u" --once >"$L" 2>&1
    files="$(grep -oE "files=[0-9]+" "$L" | tail -1)"
    if [[ "$files" =~ files=([1-9][0-9]*) ]]; then
        pass "$u replay thật (${files})"
    else
        fail "$u replay không chạy file nào — tail $L"
        tail -3 "$L" | sed 's/^/      /'
    fi
done

ac_summary
