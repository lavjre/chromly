#!/usr/bin/env bash
# acceptance/M8-info.sh — M8-01: chromly info + chromly trace
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

section "chromly info"
OUT="$("$VENV_BIN/chromly" info 2>&1 | tee "$LOG_DIR/m8-info.log")"
echo "$OUT" | head -14
for sec in "══ chromly info" "FARM" "AUX" "INTEL" "CASES" "CRASH" "BUILD" "BUDGET"; do
    grep -q "$sec" <<<"$OUT" && : || fail "thiếu section «$sec»"
done
[[ $? -eq 0 ]] && pass "info đủ section"
grep -q "event gần nhất" <<<"$OUT" && pass "có feed event" || fail "thiếu feed event"

section "info --json"
if "$VENV_BIN/chromly" info --json >"$LOG_DIR/m8-info.json" 2>/dev/null && "$VENV_BIN/python" - "$LOG_DIR/m8-info.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for k in ("farm", "aux", "intel", "cases", "crash_total", "budget", "events"):
    assert k in d, f"thiếu {k}"
print("json ok:", sorted(d.keys()))
PY
then
    pass "info --json hợp lệ"
else
    fail "info --json lỗi"
fi

section "trace one-shot"
OUT="$("$VENV_BIN/chromly" trace --limit 20 --since 240 2>&1 | tee "$LOG_DIR/m8-trace.log")"
echo "$OUT" | tail -5
if grep -qE '^[0-9]{2}:[0-9]{2}:[0-9]{2} \[' <<<"$OUT"; then
    pass "trace in event đúng format"
else
    fail "trace không có event hợp lệ"
fi
"$VENV_BIN/chromly" trace --source shell --limit 5 --since 240 >/dev/null 2>&1 && pass "trace --source lọc được" || fail "trace --source lỗi"

section "trace -f (follow)"
timeout 3 "$VENV_BIN/chromly" trace -f --limit 1 >"$LOG_DIR/m8-trace-f.log" 2>&1
grep -q "theo dõi trực tiếp" "$LOG_DIR/m8-trace-f.log" && pass "follow mode chạy" || fail "follow không vào được"

ac_summary
