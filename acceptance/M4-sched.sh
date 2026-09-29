#!/usr/bin/env bash
# acceptance/M4-sched.sh — M4-04: rules + hold/dwell + decision log + override
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "rules (fixture)"
if "$VENV_BIN/python" - <<'PY'
from chromly.orchestrator import scheduler

base = {"mem_available_gb": 4, "psi_cpu": 0, "psi_mem": 0, "disk_free_gb": 100,
        "case_running": False, "budget_tier": "flash"}
assert scheduler.desired_mode({**base, "mem_available_gb": 0.5})[0] == "RED"
assert scheduler.desired_mode({**base, "case_running": True})[0] == "CASE_PRIORITY"
assert scheduler.desired_mode({**base, "budget_tier": "window-cap"})[0] == "FUZZ_LEAN"
assert scheduler.desired_mode(base)[0] == "NORMAL"
print("rules ok")
PY
then
    pass "5 mode rules đúng"
else
    fail "rules sai"
fi

section "hold 60s + dwell + decision row"
if "$VENV_BIN/python" - <<'PY'
from chromly.orchestrator import scheduler
from chromly.store import db

con = db.ensure_db()
before = con.execute("SELECT COUNT(*) AS n FROM scheduler_decisions").fetchone()["n"]
# expire mọi override cũ để test đúng nhánh rules
with con:
    con.execute(
        "UPDATE overrides SET expires = datetime('now', '-1 hour') WHERE expires > datetime('now')"
    )

saved = scheduler._load_state()
scheduler._save_state({"mode": "NORMAL", "mode_since": 0.0})
scheduler.PRESSURE_HOLD = {"since": None, "candidate": None}
import unittest.mock as mock

snap = {"mem_available_gb": 4, "psi_cpu": 0, "psi_mem": 0, "disk_free_gb": 100,
        "case_running": True, "budget_tier": "flash"}
with mock.patch.object(scheduler, "snapshot", lambda: snap):
    r1 = scheduler.tick(now=0.0)
    assert r1["changed"] is False  # bắt đầu giữ
    r2 = scheduler.tick(now=61.0)
    assert r2["changed"] is False  # dwell chưa đủ
    r3 = scheduler.tick(now=700.0)
    assert r3["changed"] is True and r3["mode"] == "CASE_PRIORITY"

after = con.execute("SELECT COUNT(*) AS n FROM scheduler_decisions").fetchone()["n"]
print(f"decisions +{after - before}")
assert after - before == 1
# khôi phục state
scheduler._save_state(saved)
PY
then
    pass "hold/dwell + 1 decision row"
else
    fail "hold/dwell sai"
fi

section "override CLI"
"$VENV_BIN/chromly" sched override RED --minutes 1 --reason "acceptance" | tee "$LOG_DIR/m4-sched.log"
OUT="$("$VENV_BIN/chromly" sched eval)"
echo "$OUT"
grep -q '"mode": "RED"' <<<"$OUT" && pass "override RED hiệu lực" || fail "override không ăn"

"$VENV_BIN/chromly" sched status | tee -a "$LOG_DIR/m4-sched.log" | grep -q '"override"' \
    && pass "status thấy override" || fail "status thiếu override"

# dọn: override NORMAL cho chắc
"$VENV_BIN/chromly" sched override NORMAL --minutes 1 --reason "acceptance cleanup" >/dev/null

ac_summary
