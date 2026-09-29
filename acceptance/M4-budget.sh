#!/usr/bin/env bash
# acceptance/M4-budget.sh — M4-03: tier decision theo caps (§11) trên DB tạm
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

TMPD="$(mktemp -d /tmp/opencode/m4budget.XXXXXX)"
export CHROMLY_STORE="$TMPD/store"
note "DB tạm: $CHROMLY_STORE"

add_run() { # add_run <cost>
    "$VENV_BIN/python" - "$1" <<'PY'
import sys

from chromly.store import db

con = db.ensure_db()
with con:
    con.execute(
        "INSERT INTO runs (cost_est, created, outcome) VALUES (?, datetime('now'), 'fixture')",
        (float(sys.argv[1]),),
    )
PY
}

section "mặc định → flash"
add_run 0.5
OUT="$("$VENV_BIN/chromly" budget status)"
echo "$OUT"
grep -q "tier: flash" <<<"$OUT" && pass "tier flash" || fail "không phải flash"

section "vượt cửa sổ 5h → free"
add_run 12.5
OUT="$("$VENV_BIN/chromly" budget status)"
echo "$OUT"
grep -q "tier: window-cap" <<<"$OUT" && pass "window-cap" || fail "tier sai"
grep -q "free" <<<"$OUT" && pass "rơi về free" || fail "không rơi free"

section "vượt tháng → plan B"
add_run 60
OUT="$("$VENV_BIN/chromly" budget status)"
echo "$OUT"
grep -q "tier: exhausted" <<<"$OUT" && pass "exhausted" || fail "tier sai"
grep -qE "glm|mimo" <<<"$OUT" && pass "plan B" || fail "thiếu plan B"

section "check case vượt cap"
OUT="$("$VENV_BIN/chromly" budget check --est-cost 3.0)"
echo "$OUT"
grep -q '"allow": false' <<<"$OUT" && pass 'từ chối case est $3' || fail "phải từ chối"

rm -rf "$TMPD"
ac_summary
