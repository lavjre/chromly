#!/usr/bin/env bash
# acceptance/M4-bench.sh — M4-05: T3/T4 deterministic + gate + bench_runs
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "T4 harness sanity (repro pipeline)"
OUT="$(timeout 300 "$VENV_BIN/chromly" bench --suite t4 | tee "$LOG_DIR/m4-bench-t4.log")"
echo "$OUT"
grep -q '"pass": true' <<<"$OUT" && pass "T4 pass" || fail "T4 fail"

section "T3 classify accuracy"
OUT="$(timeout 300 "$VENV_BIN/chromly" bench --suite t3 | tee "$LOG_DIR/m4-bench-t3.log")"
echo "$OUT"
grep -q '"accuracy": 1.0' <<<"$OUT" && pass "T3 accuracy 100%" || fail "T3 thấp"
grep -q '"score_order_ok": true' <<<"$OUT" && pass "score order" || fail "score order sai"
grep -q '"pass": true' <<<"$OUT" && pass "gate pass (lần đầu/chênh 0)" || fail "gate fail"

section "bench_runs + report"
if "$VENV_BIN/python" - <<'PY'
from pathlib import Path

from chromly.store import db

con = db.ensure_db()
rows = con.execute("SELECT COUNT(*) AS n FROM bench_runs").fetchone()["n"]
assert rows >= 2, rows
assert Path("bench/latest.md").is_file()
print(f"bench_runs rows={rows}; latest.md ok")
PY
then
    pass "bench_runs + latest.md"
else
    fail "thiếu bench_runs/latest.md"
fi

ac_summary
