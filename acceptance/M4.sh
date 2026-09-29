#!/usr/bin/env bash
# acceptance/M4.sh — milestone M4 (§13): case · mcp · budget · sched · bench
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SCRIPTS=(M4-mcp M4-budget M4-sched M4-bench)
overall=0
for s in "${SCRIPTS[@]}"; do
    section "$s"
    bash "$REPO_ROOT/acceptance/$s.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "$s đỏ (rc=$rc)"; }
done

section "case E2E (dùng lại evidence nếu case đã chạy)"
CASE_DONE="$("$VENV_BIN/python" - <<'PY'
import json
from pathlib import Path

cases = sorted(Path("cases").glob("CASE-*/meta.json")) if Path("cases").is_dir() else []
for p in cases:
    m = json.loads(p.read_text())
    if m.get("state") in ("VERDICT", "TIMEOUT", "HELP"):
        print(m["id"])
        break
PY
)"
if [[ -n "$CASE_DONE" ]]; then
    note "case $CASE_DONE đã kết thúc (evidence từ M4-case.sh) — không chạy lại agent"
    if "$VENV_BIN/python" - "$CASE_DONE" <<'PY'
import sys
from pathlib import Path

from chromly.store import db

cid = sys.argv[1]
d = Path("cases") / cid
assert d.is_dir()
con = db.ensure_db()
row = con.execute(
    "SELECT model, wall_s, outcome FROM runs WHERE case_id = ? ORDER BY id DESC LIMIT 1", (cid,)
).fetchone()
print(f"{cid}: {row['outcome']} wall={row['wall_s']}s model={row['model']}")
assert row is not None
# report
rep = Path("store/reports")
rep.mkdir(parents=True, exist_ok=True)
(rep / "m4-case-e2e.md").write_text(
    f"# M4 case E2E\n\n- case: {cid}\n- run: {row['outcome']} wall={row['wall_s']}s model={row['model']}\n"
)
PY
    then
        pass "case E2E evidence"
    else
        fail "case E2E thiếu runs"
    fi
else
    section "M4-case (chưa có case nào — chạy đầy đủ)"
    bash "$REPO_ROOT/acceptance/M4-case.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "M4-case đỏ"; }
fi

printf '\n'
if [[ $overall -eq 0 ]]; then
    printf '========= M4 ACCEPTANCE: GREEN =========\n'
else
    printf '========= M4 ACCEPTANCE: RED ===========\n'
fi
exit $overall
