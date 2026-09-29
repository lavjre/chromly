# M4-02 — MCP bridge `chromly-tools` (boundary duy nhất)

**Status:** done
**Deliverable:** `chromly mcp serve` — MCP stdio server zero-dep (JSON-RPC thuần, format như `tools/ida_smoke.py`), version `/v1`; tools: `case.get/update` · `crash.list/detail` · `repro.run` · `build.request/status` · `fuzz.status` · `store.put/get` · `runs.append` · `kg.query/kg.neighbors` (§5.7); log mọi call `store/mcp-log.jsonl`; timeout mặc định 15' (server-side per-tool).
**Files:** `chromly/mcp/__init__.py`, `chromly/mcp/server.py`, `chromly/mcp/tools.py`, `tests/test_mcp.py`, `acceptance/M4-mcp.sh`
**Acceptance:** `bash acceptance/M4-mcp.sh` → initialize/tools.list đủ 13 tool; call thật: `crash.list` + `kg.query` (fixture) qua JSON-RPC; log ghi.
**Evidence:** tools count + call outputs.
**Phụ thuộc:** schema v4 (M3-04).
