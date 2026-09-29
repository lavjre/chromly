#!/usr/bin/env bash
# acceptance/M1-libfuzzer.sh — M1-03: build out/libfuzzer + 2 wrapper v0 (replay)
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

section "2 wrapper v0 chạy 120s"
"$VENV_BIN/chromly" fuzz up
sleep 120
ST="$("$VENV_BIN/chromly" fuzz status)"
echo "$ST"
lib_alive="$(grep -cE "libfuzzer-(parser|wasm) +alive" <<<"$ST" || true)"
[[ "$lib_alive" -eq 2 ]] && pass "2 wrapper alive" || fail "chỉ $lib_alive/2 alive"

pfiles="$(grep -oE "files=[0-9]+" "$REPO_ROOT/store/fuzz/logs/libfuzzer-parser.log" 2>/dev/null | tail -1)"
note "parser replay: $pfiles"
if [[ "$pfiles" =~ files=([1-9][0-9]*) ]]; then
    pass "parser replay chạy thật (${BASH_REMATCH[1]} file)"
else
    fail "parser replay chưa chạy file nào"
fi

"$VENV_BIN/chromly" fuzz down >/dev/null
pass "down sau test"

ac_summary
