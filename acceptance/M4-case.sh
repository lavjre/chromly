#!/usr/bin/env bash
# acceptance/M4-case.sh — M4-01: case pipeline từ calibration bug #1 (maglev repro, pre-fix)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "fixture crash (maglev repro 567177599)"
H12="$("$VENV_BIN/python" - <<'PY'
import hashlib
from pathlib import Path

from chromly import paths
from chromly.store import db

data = Path("store/calibration/repro-567177599.js").read_bytes()
h = hashlib.sha256(data).hexdigest()
art = paths.STORE_DIR / "crashes" / h
art.mkdir(parents=True, exist_ok=True)
(art / "program_567177599.js").write_bytes(data)
(art / "repro.flags.txt").write_text(
    "--allow-natives-syntax\n--turbolev\n--abort-on-uncaught-exception\n"
)
con = db.ensure_db()
con.execute("DELETE FROM crashes WHERE hash = ?", (h,))
con.execute(
    "INSERT INTO crashes (hash, fault_type, severity, state, build_rev) "
    "VALUES (?, 'miscompilation-type', 5, 'triaged', 'b8ffaab06761')",
    (h,),
)
con.commit()
print(h[:12])
PY
)"
note "crash fixture: $H12"

section "case new"
OUT="$("$VENV_BIN/chromly" case new --crash "$H12")"
echo "$OUT"
CID="$("$VENV_BIN/python" -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$OUT")"
[[ -n "$CID" ]] && pass "case $CID tạo" || fail "new lỗi"

section "case run (wall ≤25') — agent persona đi crash → root cause"
timeout 1700 "$VENV_BIN/chromly" case run "$CID" --wall 25 2>&1 | tee "$LOG_DIR/m4-case.log" || true

RESULT="$("$VENV_BIN/python" - "$CID" <<'PY'
import json
import sys
from pathlib import Path

cid = sys.argv[1]
meta = json.loads(Path(f"cases/{cid}/meta.json").read_text())
print(json.dumps({"state": meta["state"]}))
PY
)"
echo "meta: $RESULT"

if "$VENV_BIN/python" - "$CID" "$RESULT" <<'PY'
import json
import sys
from pathlib import Path

cid = sys.argv[1]
state = json.loads(sys.argv[2])["state"]
assert state in ("VERDICT", "TIMEOUT", "HELP"), state
d = Path(f"cases/{cid}")
if state == "VERDICT":
    text = (d / "VERDICT.md").read_text()
    assert "verdict:" in text
print(f"state={state} ok")
PY
then
    pass "case kết thúc hợp lệ ($RESULT)"
else
    fail "case state lạ"
fi

section "artifacts + runs"
if "$VENV_BIN/python" - "$CID" <<'PY'
import sys
from pathlib import Path

from chromly.store import db

cid = sys.argv[1]
d = Path(f"cases/{cid}")
assert (d / "meta.json").is_file() and (d / "brief.md").is_file()
con = db.ensure_db()
row = con.execute(
    "SELECT model, wall_s, outcome FROM runs WHERE case_id = ? ORDER BY id DESC LIMIT 1", (cid,)
).fetchone()
print(f"runs: model={row['model']} wall={row['wall_s']}s outcome={row['outcome']}")
assert row is not None and row["outcome"].startswith("case:")
PY
then
    pass "case dir + runs row"
else
    fail "thiếu artifacts/runs"
fi

ac_summary
