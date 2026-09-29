"""chromly-tools MCP server — M4-02 (§5.7): stdio JSON-RPC 2.0, zero-dep.

Chạy: `chromly mcp serve` — newline-delimited JSON (giống MCP stdio).
Timeout mặc định 15' (900s) per call. Log mọi call → store/mcp-log.jsonl.
`build.request` ghi nhận yêu cầu (spawn detached `chromly build`) — v0 trả build_id kèm config.
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import time

from chromly.mcp import tools as toolmod

PROTOCOL_VERSION = "2025-06-18"
CALL_TIMEOUT = 900.0


def _tools_list() -> list[dict]:
    items = []
    for name, spec in toolmod.HANDLERS.items():
        props = spec.get("schema")
        items.append(
            {
                "name": name,
                "description": spec["desc"],
                "inputSchema": props
                or {"type": "object", "properties": {}, "additionalProperties": True},
            }
        )
    return sorted(items, key=lambda t: t["name"])


def _call_tool(name: str, args: dict) -> dict:
    if name not in toolmod.HANDLERS:
        raise ValueError(f"tool không tồn tại: {name}")
    fn = toolmod.HANDLERS[name]["fn"]
    t0 = time.monotonic()
    ok = False
    try:
        result = fn(args)
        ok = True
        return result
    finally:
        toolmod._log(name, args, (time.monotonic() - t0) * 1000, ok)


def _handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "chromly-tools", "version": f"{toolmod.VERSION}.0"},
            },
        }
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": _tools_list()}}
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_call_tool, name, args)
                result = future.result(timeout=CALL_TIMEOUT)
            text = json.dumps(result, ensure_ascii=False, default=str)
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": text}], "isError": False},
            }
        except Exception as exc:  # noqa: BLE001 — server phải trả lỗi có cấu trúc
            text = f"{type(exc).__name__}: {exc}"
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": text}], "isError": True},
            }
    if mid is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": f"method không hỗ trợ: {method}"},
    }


def serve() -> int:
    """Vòng lặp stdio: đọc JSON mỗi dòng, trả JSON mỗi dòng."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def run_mcp_cmd(args) -> int:
    sub = getattr(args, "mcp_cmd", None)
    if sub == "serve":
        return serve()
    print("usage: chromly mcp serve")
    return 2
