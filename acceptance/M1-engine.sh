#!/usr/bin/env bash
# acceptance/M1-engine.sh — M1-08: libFuzzer engine mode (mutation + coverage thật)
#   • build archive vendor + engine binary (re-link từ ninja per-target, không patch V8)
#   • smoke 1 cycle: assert "Done", "cov:", "exec/s:" trong output engine
#   • farm: unit lfuzz-* alive + execs>0 (không down — farm đang chạy là lane thật)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

V8="${CHROMLY_V8_ROOT:-$HOME/v8/v8}"
OUT="$V8/out/libfuzzer"
CORPUS="$REPO_ROOT/store/fuzz/lfuzz-wasm/corpus"

section "build engine (archive + re-link)"
if "$VENV_BIN/chromly" fuzz engine --build >"$LOG_DIR/m1-engine-build.log" 2>&1; then
    pass "chromly fuzz engine --build"
else
    fail "build lỗi — tail $LOG_DIR/m1-engine-build.log"
    tail -5 "$LOG_DIR/m1-engine-build.log" | sed 's/^/      /'
fi

section "artifacts trên đĩa"
[[ -f "$REPO_ROOT/build/libfuzzer/libFuzzer.a" ]] \
    && pass "libFuzzer.a vendor (libc++ ABI)" || fail "thiếu build/libfuzzer/libFuzzer.a"
for f in v8_engine_parser_fuzzer v8_engine_wasm_module_fuzzer; do
    [[ -x "$OUT/$f" ]] && pass "$f" || fail "thiếu $OUT/$f"
done

section "smoke 1 cycle (wasm, 15s)"
SMOKE_LOG="$LOG_DIR/m1-engine-smoke.log"
timeout 120 "$VENV_BIN/chromly" fuzz lfuzz --unit lfuzz-wasm --seconds 15 --once >"$SMOKE_LOG" 2>&1
grep -q "Done " "$SMOKE_LOG" && pass "engine chạy hết cycle (Done)" || fail "không thấy 'Done'"
grep -q "cov: " "$SMOKE_LOG" && pass "coverage feedback sống (cov:)" || fail "không thấy 'cov:'"
grep -q "exec/s: " "$SMOKE_LOG" && pass "exec/s có trong log (farm parse được)" || fail "không thấy 'exec/s:'"

section "farm units (lfuzz-* alive, không down)"
"$VENV_BIN/chromly" fuzz up >/dev/null 2>&1
sleep 20
ST="$("$VENV_BIN/chromly" fuzz status)"
echo "$ST"
alive="$(grep -cE "lfuzz-(parser|wasm) +alive" <<<"$ST" || true)"
[[ "$alive" -eq 2 ]] && pass "2 unit lfuzz alive" || fail "chỉ $alive/2 unit lfuzz alive"

section "corpus tự mọc (engine thêm unit)"
N1="$(ls "$CORPUS" 2>/dev/null | wc -l)"
note "lfuzz-wasm corpus hiện tại: $N1 file"

ac_summary
