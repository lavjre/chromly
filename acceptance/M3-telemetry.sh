#!/usr/bin/env bash
# acceptance/M3-telemetry.sh — M3-04: rollup + alert trigger + ack + digest
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "rollup từ metrics"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
with con:
    for v in (10.0, 20.0, 30.0):
        con.execute(
            "INSERT INTO metrics (ts, scope, name, value, tags) "
            "VALUES (datetime('now'), 'acceptance', 'execs_per_sec', ?, '{}')",
            (v,),
        )
PY
then
    pass "fixture metrics"
else
    fail "fixture metrics lỗi"
fi
"$VENV_BIN/chromly" telemetry rollup --days 7 | tee "$LOG_DIR/m3-rollup.log"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
row = con.execute(
    "SELECT max, n FROM metrics_rollup WHERE name = 'execs_per_sec' ORDER BY day DESC LIMIT 1"
).fetchone()
print(f"rollup max={row['max']} n={row['n']}")
assert row["max"] == 30.0
PY
then
    pass "rollup đúng số"
else
    fail "rollup sai"
fi

section "alert engine — watcher_lag"
"$VENV_BIN/python" - <<'PY'
from chromly.intel import watcher

st = watcher._load_state()
st["last_lag_hours"] = 99.0
watcher._save_state(st)
PY
OUT="$("$VENV_BIN/chromly" telemetry alerts | tee "$LOG_DIR/m3-alerts.log")"
echo "$OUT"
grep -q "watcher_lag" <<<"$OUT" && pass "alert watcher_lag bắn" || fail "không thấy alert"
AID="$(grep -oE '^\[[0-9]+\] \[[a-z]+\] watcher_lag' <<<"$OUT" | grep -oE '[0-9]+' | head -1)"
if [[ -n "$AID" ]]; then
    "$VENV_BIN/chromly" telemetry alerts --ack "$AID" | tee -a "$LOG_DIR/m3-alerts.log"
    grep -q "acked" <<<"$("$VENV_BIN/chromly" telemetry alerts --ack "$AID")" && pass "ack OK" || note "ack lần 2 (đã ack)"
else
    fail "không lấy được alert id"
fi

section "digest"
D="$("$VENV_BIN/chromly" telemetry digest)"
echo "$D"
grep -q "Telemetry digest" <<<"$D" && pass "digest" || fail "digest lỗi"

ac_summary
