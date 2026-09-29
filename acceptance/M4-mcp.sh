#!/usr/bin/env bash
# acceptance/M4-mcp.sh — M4-02: chromly-tools MCP server (stdio)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "smoke: initialize + tools/list + calls"
if "$VENV_BIN/python" "$REPO_ROOT/tools/chromly_mcp_smoke.py" 2>&1 | tee "$LOG_DIR/m4-mcp.log"; then
    pass "MCP smoke OK"
else
    fail "MCP smoke lỗi — xem $LOG_DIR/m4-mcp.log"
fi

section "mcp-log.jsonl"
if "$VENV_BIN/python" - <<'PY'
import json
from pathlib import Path

p = Path("store/mcp-log.jsonl")
assert p.is_file(), "thiếu mcp-log.jsonl"
lines = [json.loads(x) for x in p.read_text().strip().splitlines()]
called = {x["tool"] for x in lines}
print(f"logged calls: {len(lines)} (tools: {sorted(called)})")
assert {"crash.list", "kg.query", "store.put", "store.get"} <= called
PY
then
    pass "mcp-log đủ call"
else
    fail "mcp-log thiếu"
fi

ac_summary
