# M0-06 — IDA MCP handshake

**Status:** done
**Deliverable:** `tools/ida_smoke.py` — MCP client stdio nói chuyện với `uvx ida-mcp stdio --agent=opencode` (đúng command trong `runtime/opencode.json`): `initialize` → `notifications/initialized` → `tools/list` (≥5 tool `ida.*`) → `tools/call ida.open_database` (binary test nhỏ, tự compile bằng clang) → `ida.execute_python` in `IDA-SMOKE-OK` → `ida.close_database` → exit 0. `acceptance/M0-ida.sh` gọi script + ghi log `store/logs/acceptance/ida-smoke.log`.
**Files:** `tools/ida_smoke.py`, `acceptance/M0-ida.sh`, `docs/ida-mcp-notes.md` (cách chạy, license, dashboard, fallback http)
**Acceptance:** `bash acceptance/M0-ida.sh` exit 0.
**Evidence:** tools/list count + output `IDA-SMOKE-OK` trong commit body.
**Out of scope:** tích hợp IDA vào case container (M4) · idalib batch (skill M3).
**Phụ thuộc:** IDA 9.4 + license trên VM (đã có), `uv` trong PATH.
