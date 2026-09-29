#!/usr/bin/env bash
# acceptance/M1-metrics.sh — M1-07: sampler + jsonl + DB
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "sampler một mẫu"
if "$VENV_BIN/chromly" fuzz metrics --once; then
    pass "metrics --once"
else
    fail "sampler lỗi"
fi

section "metrics.jsonl"
MJ="$REPO_ROOT/store/fuzz/metrics.jsonl"
[[ -f "$MJ" ]] && pass "jsonl tồn tại" || fail "thiếu $MJ"
if "$VENV_BIN/python" - "$MJ" <<'PY'
import json, pathlib, sys

p = pathlib.Path(sys.argv[1])
last = json.loads(p.read_text().strip().splitlines()[-1])
assert "ts" in last and "units" in last
print("units trong mẫu cuối:", list(last["units"]))
PY
then
    pass "jsonl parse được"
else
    fail "jsonl hỏng"
fi

section "DB metrics table"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
cols = {r[1] for r in con.execute("PRAGMA table_info(metrics)")}
assert {"ts", "scope", "name", "value", "tags"} <= cols
print("metrics table ok")
PY
then
    pass "schema metrics v2"
else
    fail "schema sai"
fi

ac_summary
