#!/usr/bin/env bash
# acceptance/M1-watchdog.sh — M1-04: hang → kill + restart (hang_s test = 5s, điều khiển bằng --once)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

export CHROMLY_WATCHDOG_HANG_S=5
EV="$REPO_ROOT/store/fuzz/events.jsonl"

section "spawn unit treo (sleep 600, zero CPU)"
if "$VENV_BIN/python" - <<'PY'
from chromly.fuzz import farm

unit = farm.Unit("fake-hang", "fuzzilli", ["/usr/bin/sleep", "600"], farm.LOGS_DIR / "fake-hang.log")
print("up:", farm.up([unit]))
PY
then
    pass "unit treo đã spawn"
else
    fail "spawn lỗi"
fi

section "tick 1 — ghi baseline"
"$VENV_BIN/chromly" fuzz watchdog --once
sleep 6

section "tick 2 — phải phát hiện hang → kill + restart"
"$VENV_BIN/chromly" fuzz watchdog --once | tee "$LOG_DIR/watchdog-run.log"

section "events kill + restart"
if grep -q '"event": "kill"' "$EV" && grep -q '"event": "restart"' "$EV"; then
    pass "events kill + restart có mặt"
else
    fail "thiếu events (xem $EV)"
fi

section "unit sống lại"
if "$VENV_BIN/python" - <<'PY'
from chromly.fuzz import farm

rec = farm.status().get("fake-hang", {})
assert rec.get("alive"), rec
print("alive, pid =", rec["pid"])
PY
then
    pass "restart OK"
else
    fail "unit không sống lại"
fi

section "cleanup"
"$VENV_BIN/chromly" fuzz down >/dev/null

ac_summary
