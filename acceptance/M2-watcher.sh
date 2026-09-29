#!/usr/bin/env bash
# acceptance/M2-watcher.sh — M2-01: mirror + poll + filter + DB
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

parse() { # parse <key> <text>
    "$VENV_BIN/python" - "$1" "$2" <<'PY'
import re, sys

text = sys.argv[2]
m = re.search(rf"{sys.argv[1]}=([0-9.]+|None|[\w-]+)", text)
print(m.group(1) if m else "")
PY
}

section "đặt mốc test (last_sha = HEAD~200) để có cửa sổ commit"
"$VENV_BIN/python" - <<'PY'
import subprocess

from chromly.intel import watcher

rev = subprocess.run(
    ["git", "-C", str(watcher.mirror_dir()), "rev-parse", "HEAD~200"],
    capture_output=True,
    text=True,
).stdout.strip()
st = watcher._load_state()
st["last_sha"] = rev
watcher._save_state(st)
print("last_sha →", rev[:12])
PY

section "watch --once"
OUT="$("$VENV_BIN/chromly" intel watch --once --max 100 2>&1 | tee "$LOG_DIR/m2-watcher.log")"
echo "$OUT"

seen="$(parse seen "$OUT")"
matched="$(parse matched "$OUT")"
lag="$(parse lag "$OUT")"
new1="$(parse new "$OUT")"
note "seen=$seen matched=$matched new=$new1 lag=$lag"

[[ -n "$seen" && "$seen" -gt 0 ]] 2>/dev/null && pass "mirror đọc được commits ($seen)" || fail "seen=$seen"
[[ -n "$matched" && "$matched" -ge 1 ]] 2>/dev/null && pass "filter bắt được commits ($matched)" || fail "matched=$matched"
if [[ -n "$lag" && "$lag" != "None" ]]; then
    "$VENV_BIN/python" -c "import sys; sys.exit(0 if float('$lag') < 24 else 1)" \
        && pass "lag <24h ($lag h)" || fail "lag ≥24h ($lag h)"
else
    fail "không đo được lag"
fi

section "idempotent (lần 2 — cửa sổ đã insert hết)"
OUT2="$("$VENV_BIN/chromly" intel watch --once --max 100 2>&1)"
new2="$(parse new "$OUT2")"
[[ "${new2:-1}" -eq 0 ]] 2>/dev/null && pass "không nhân đôi (new=0)" || fail "new lần 2 = $new2"

section "diff dump + DB"
n_diff="$(ls "$REPO_ROOT"/store/intel/*/commit.diff 2>/dev/null | wc -l)"
[[ "$n_diff" -ge 1 ]] && pass "commit.diff dumps: $n_diff" || fail "không có diff dump"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
n = con.execute("SELECT COUNT(*) AS n FROM intel").fetchone()["n"]
print(f"intel rows = {n}")
assert n >= 1
PY
then
    pass "DB intel rows"
else
    fail "DB intel trống"
fi

ac_summary
