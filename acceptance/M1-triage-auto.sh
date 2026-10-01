#!/usr/bin/env bash
# acceptance/M1-triage-auto.sh — M1-09: Track A tự động khép vòng (triage loop + bisect + dedup)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

mk_fixture() { # mk_fixture <seed> → in ra hash prefix
    "$VENV_BIN/python" - "$1" <<'PY'
import hashlib, sys
from pathlib import Path

from chromly import paths
from chromly.store import db

seed = sys.argv[1]
src = f'// chromly acceptance triage fixture {seed}\n%AbortJS("acc-triage-{seed}");\n'
h = hashlib.sha256(src.encode()).hexdigest()
d = paths.STORE_DIR / "crashes" / h
d.mkdir(parents=True, exist_ok=True)
files = sorted(d.glob("program_*.js"))
if not files:
    (d / "program_acc_triage.js").write_text(src)
con = db.ensure_db()
with con:
    con.execute(
        "INSERT OR IGNORE INTO crashes (hash, source, state) VALUES (?, 'acceptance', 'raw')",
        (h,),
    )
con.close()
print(h[:12])
PY
}

rm_fixture() { # rm_fixture <hash12>
    "$VENV_BIN/python" - "$1" <<'PY'
import sys
from chromly import paths
from chromly.store import db

p = sys.argv[1]
con = db.ensure_db()
with con:
    row = con.execute("SELECT id, hash FROM crashes WHERE hash LIKE ?", (p + "%",)).fetchone()
    if row:
        con.execute("DELETE FROM crashes WHERE id = ?", (row["id"],))
con.close()
if row:
    import shutil

    for base in ("crashes", "triage"):
        d = paths.STORE_DIR / base / row["hash"]
        if d.is_dir():
            shutil.rmtree(d)
PY
}

section "fixture crash → triage tự động (chế độ một lượt)"
H1="$(mk_fixture a)"
OUT="$("$VENV_BIN/chromly" triage 2>&1 | tee "$LOG_DIR/m1-triage-1.log")"
echo "$OUT" | head -4
STATE="$("$VENV_BIN/python" -c "
from chromly.store import db
con = db.ensure_db()
r = con.execute(\"SELECT state FROM crashes WHERE hash LIKE '$H1%'\").fetchone()
print(r['state'] if r else 'missing')
")"
[[ "$STATE" == "triaged" ]] && pass "fixture $H1 → triaged" || fail "state=$STATE (kỳ vọng triaged)"

section "loop mode xử lý tiếp (timeout 8s)"
H2="$(mk_fixture b)"
timeout 8 "$VENV_BIN/chromly" triage --loop --interval 2 >"$LOG_DIR/m1-triage-loop.log" 2>&1
grep -q "xử lý $H2" "$LOG_DIR/m1-triage-loop.log" && pass "loop nhặt fixture $H2" || fail "loop không xử lý"
STATE2="$("$VENV_BIN/python" -c "
from chromly.store import db
con = db.ensure_db()
r = con.execute(\"SELECT state FROM crashes WHERE hash LIKE '$H2%'\").fetchone()
print(r['state'] if r else 'missing')
")"
[[ "$STATE2" == "triaged" ]] && pass "loop → triaged" || fail "loop state=$STATE2"

section "aux spec có triage"
grep -q '"triage": \["triage", "--loop"' chromly/orchestrator/supervisor.py \
    && pass "supervisor AUX_SPECS có triage" || fail "thiếu aux triage"

section "backend unit tests"
"$VENV_BIN/python" -m pytest -q tests/test_triage.py tests/test_replay_seed.py tests/test_case.py >/dev/null 2>&1 \
    && pass "triage + replay bisect + case dedup tests" || fail "unit tests đỏ"

rm_fixture "$H1"
rm_fixture "$H2"
ac_summary
