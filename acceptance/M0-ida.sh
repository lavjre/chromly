#!/usr/bin/env bash
# acceptance/M0-ida.sh — M0-06: IDA MCP handshake (stdio)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

IDA_LOG="$LOG_DIR/ida-smoke.log"

section "ida-mcp handshake"
if "$VENV_BIN/python" "$REPO_ROOT/tools/ida_smoke.py" 2>&1 | tee "$IDA_LOG"; then
    pass "handshake OK (log: store/logs/acceptance/ida-smoke.log)"
else
    fail "handshake thất bại — xem $IDA_LOG"
fi

ac_summary
