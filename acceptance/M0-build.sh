#!/usr/bin/env bash
# acceptance/M0-build.sh — M0-04: build sạch ASAN d8 ≤90' + d8 chạy được
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

V8_ROOT="${CHROMLY_V8_ROOT:-$HOME/v8/v8}"
D8="$V8_ROOT/out/asan/d8"

section "v8 checkout"
if [[ -d "$V8_ROOT/.git" ]]; then
    pass "checkout: $V8_ROOT"
else
    note "chưa có checkout — fetch (30–60'), chạy nền được"
    if "$VENV_BIN/chromly" build --config asan --fetch-only; then
        pass "gclient sync xong"
    else
        fail "gclient sync — xem store/builds/"
    fi
fi

section "build asan d8"
if "$VENV_BIN/chromly" build --config asan >"$LOG_DIR/m0-build.log" 2>&1; then
    pass "chromly build --config asan"
else
    fail "build lỗi — tail $LOG_DIR/m0-build.log"
fi

section "record + ngưỡng ≤90'"
if "$VENV_BIN/python" - "$REPO_ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
recs = sorted((root / "store/builds").glob("*.json"), key=lambda p: p.stat().st_mtime)
asan = [json.loads(r.read_text()) for r in recs if json.loads(r.read_text()).get("config") == "asan"]
if not asan:
    print("không có record asan"); sys.exit(1)
latest = asan[-1]
# evidence full-build = record ok có duration lớn nhất (full ≈ phút; incremental ≈ giây)
full = [r for r in asan if r.get("status") == "ok" and isinstance(r.get("duration_s"), (int, float))]
if not full:
    print("không có record asan ok"); sys.exit(1)
rec = max(full, key=lambda r: r["duration_s"])
print(f"full build: {rec.get('id')} rev={(rec.get('rev') or '')[:12]} "
      f"status={rec.get('status')} duration_s={rec.get('duration_s')} clean={rec.get('clean', '?')}")
print(f"latest:     {latest.get('id')} status={latest.get('status')} "
      f"duration_s={latest.get('duration_s')} clean={latest.get('clean', '?')}")
if rec["duration_s"] > 5400:
    print(f"full build quá 90': {rec['duration_s']}s"); sys.exit(1)
print("full build trong ngưỡng 90'")
sys.exit(0)
PY
then
    pass "build ≤90' theo full-build record"
else
    fail "build >90' hoặc record lỗi"
fi

section "d8 chạy được"
if [[ ! -x "$D8" ]]; then
    fail "thiếu $D8"
else
    if "$D8" --version >/dev/null 2>&1; then
        pass "d8 --version: $("$D8" --version 2>&1 | head -1)"
    else
        # rebuild asan runtime path nếu cần
        ASAN_LIB_DIR="$(find "$V8_ROOT/third_party/llvm-build" -name 'libclang_rt.asan-x86_64.so' 2>/dev/null | head -1)"
        if [[ -n "$ASAN_LIB_DIR" ]] && LD_LIBRARY_PATH="$(dirname "$ASAN_LIB_DIR")" "$D8" --version >/dev/null 2>&1; then
            pass "d8 --version (cần LD_LIBRARY_PATH tới llvm-build — ghi chú cho harness)"
        else
            fail "d8 không chạy được"
        fi
    fi
fi

ac_summary
