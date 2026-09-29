#!/usr/bin/env bash
# acceptance/M3-triage.sh — M3-01: repro ×5 + artifacts + DB
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

D8="${CHROMLY_V8_ROOT:-$HOME/v8/v8}/out/asan/d8"
[[ -x "$D8" ]] || fail "thiếu $D8"

section "fixture crash artifact (abort-on-uncaught)"
HASHFULL="$("$VENV_BIN/python" - <<'PY'
import hashlib
import json

from chromly import paths
from chromly.store import db

data = b'throw new Error("chromly-triage-fixture");\n'
h = hashlib.sha256(data).hexdigest()
td = paths.STORE_DIR / "crashes" / h
td.mkdir(parents=True, exist_ok=True)
(td / "program_fixture.js").write_bytes(data)
(td / "repro.flags.txt").write_text("--abort-on-uncaught-exception\n")
(td / "meta.json").write_text(json.dumps({"hash": h, "unit": "fixture", "v8_rev": "fixture"}))
con = db.ensure_db()
con.execute("DELETE FROM crashes WHERE hash = ?", (h,))
con.execute("INSERT INTO crashes (hash, source, state) VALUES (?, 'fixture', 'raw')", (h,))
con.commit()
print(h)
PY
)"
HASH12="${HASHFULL:0:12}"
note "fixture hash: $HASH12"

section "chromly triage --hash $HASH12"
OUT="$("$VENV_BIN/chromly" triage --hash "$HASH12" --runs 5 | tee "$LOG_DIR/m3-triage.log")"
echo "$OUT"

grep -q "repro=5/5" <<<"$OUT" && pass "repro 5/5 (stable)" || fail "repro không ổn định"

TD="$REPO_ROOT/store/triage/$HASHFULL"
for f in repro.js asan.txt symbols.txt; do
    [[ -f "$TD/$f" ]] && pass "artifact $f" || fail "thiếu $TD/$f"
done

if "$VENV_BIN/python" - "$HASH12" <<'PY'
import sys

from chromly.store import db

con = db.ensure_db()
row = con.execute(
    "SELECT state, fault_type, severity FROM crashes WHERE hash LIKE ?", (sys.argv[1] + "%",)
).fetchone()
print(f"state={row['state']} fault_type={row['fault_type']} score={row['severity']}")
assert row["state"] == "triaged"
assert row["fault_type"] is not None
PY
then
    pass "DB cập nhật triaged"
else
    fail "DB chưa cập nhật"
fi

ac_summary
