#!/usr/bin/env bash
# acceptance/M2-review.sh — M2-02: agent intel review 1 commit thật
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "review 1 commit (agent intel — flash)"
OUT="$("$VENV_BIN/chromly" intel review --limit 1 2>&1 | tee "$LOG_DIR/m2-review.log")"
echo "$OUT"

if grep -q '"status": "reviewed"' <<<"$OUT"; then
    pass "agent review xong"
else
    fail "review không hoàn tất (xem $LOG_DIR/m2-review.log)"
fi

section "artifacts review.md + variants.json"
LATEST="$(ls -td "$REPO_ROOT"/store/intel/*/ 2>/dev/null | head -1)"
if [[ -s "${LATEST}review.md" ]]; then
    pass "review.md ($(wc -c <"${LATEST}review.md") bytes)"
else
    fail "thiếu review.md"
fi
[[ -f "${LATEST}variants.json" ]] && pass "variants.json" || fail "thiếu variants.json"

section "DB + runs"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
reviewed = con.execute(
    "SELECT COUNT(*) AS n FROM intel WHERE review_status = 'reviewed'"
).fetchone()["n"]
runs = con.execute(
    "SELECT COUNT(*) AS n FROM runs WHERE outcome LIKE 'intel:%'"
).fetchone()["n"]
print(f"reviewed={reviewed} intel_runs={runs}")
assert reviewed >= 1 and runs >= 1
PY
then
    pass "DB cập nhật + run được ghi"
else
    fail "DB/runs chưa đúng"
fi

ac_summary
