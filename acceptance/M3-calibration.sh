#!/usr/bin/env bash
# acceptance/M3-calibration.sh — M3-03: revert-fix ground truth (bug đầu tiên trong calibration/bugs.json)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

BUGS="$REPO_ROOT/calibration/bugs.json"
if [[ ! -s "$BUGS" ]]; then
    pend "calibration/bugs.json trống — chưa có bug nào (task M3-03 mở)"
    ac_summary
    exit 0
fi

BUG_ID="$("$VENV_BIN/python" -c "import json; print(json.load(open('$BUGS'))[0]['id'])")"
note "bug: $BUG_ID (build out/calib — lần đầu ~40', sau incremental)"

section "calibrate"
OUT="$("$VENV_BIN/chromly" calibrate --bug "$BUG_ID" 2>&1 | tee "$LOG_DIR/m3-calibration.log")"
echo "$OUT"

if grep -q '"status": "ok"' <<<"$OUT"; then
    pass "ground truth đứng vững (revert build crash)"
else
    fail "calibration fail: $(head -c200 <<<"$OUT")"
fi

section "artifacts + DB"
RES="$REPO_ROOT/store/calibration/$BUG_ID/result.json"
[[ -s "$RES" ]] && pass "result.json" || fail "thiếu result.json"
if "$VENV_BIN/python" - "$BUG_ID" <<'PY'
import sys

from chromly.store import db

con = db.ensure_db()
row = con.execute(
    "SELECT bug, coverage_note FROM calibration WHERE bug = ? ORDER BY id DESC LIMIT 1",
    (sys.argv[1],),
).fetchone()
print(f"calibration row: {row['bug']} — {row['coverage_note']}")
assert row is not None
PY
then
    pass "DB calibration row"
else
    fail "DB thiếu row"
fi

ac_summary
