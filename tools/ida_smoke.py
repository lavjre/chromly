#!/usr/bin/env python3
"""IDA MCP handshake smoke — task M0-06.

Nói chuyện trực tiếp với `uvx ida-mcp stdio --agent=opencode` (đúng command trong
runtime/opencode.json) qua JSON-RPC line-delimited (MCP stdio):

    initialize → notifications/initialized → tools/list
    → ida.open_database (binary test) → ida.execute_python → ida.close_database

Exit 0 = handshake OK; khác 0 = fail (in lý do, log ở store/logs/acceptance/ida-smoke.log).
"""

from __future__ import annotations

import json
import select
import subprocess
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = REPO / "store" / "logs" / "acceptance"
WORK_DIR = Path("/tmp/opencode/ida-smoke")
STDERR_LOG = LOG_DIR / "ida-smoke-stderr.log"

CMD = ["uvx", "--exclude-newer=1s", "ida-mcp", "stdio", "--agent=opencode"]
PROTOCOL_VERSION = "2025-06-18"


def log(msg: str) -> None:
    print(f"[ida-smoke] {msg}", flush=True)


class MCPClient:
    def __init__(self, cmd: list[str], err_path: Path):
        err_path.parent.mkdir(parents=True, exist_ok=True)
        self._err = err_path.open("w")
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._err,
            text=True,
            bufsize=1,
        )
        self._next_id = 0

    def _write(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict | None = None, timeout: float = 180) -> dict:
        self._next_id += 1
        mid = self._next_id
        self._write({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timeout chờ response id={mid} ({method})")
            ready, _, _ = select.select([self.proc.stdout], [], [], min(remaining, 5.0))
            if not ready:
                continue
            line = self.proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                raise RuntimeError("server đóng stdout")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._err.write(f"NON-JSON line: {line!r}\n")
                continue
            if msg.get("id") == mid:
                return msg

    def notify(self, method: str, params: dict | None = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except OSError:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self._err.close()


def build_test_binary() -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    src = WORK_DIR / "smoke.c"
    src.write_text(
        textwrap.dedent(
            """
            #include <stdio.h>
            int check(int x) { return x * 2 + 1; }
            int main(void) { printf("%d\\n", check(21)); return 0; }
            """
        ).strip()
        + "\n"
    )
    binary = WORK_DIR / "smoke.bin"
    subprocess.run(["clang", "-O0", "-g", "-o", str(binary), str(src)], check=True)
    return binary


def tool_text(resp: dict) -> str:
    parts = []
    for item in resp.get("result", {}).get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts)


def pick_tool(tools: list[dict], suffix: str) -> dict | None:
    for t in tools:
        name = t.get("name", "")
        if name == suffix or name.split(".")[-1] == suffix or name.endswith("_" + suffix):
            return t
    return None


def pick_key(schema: dict, *candidates: str) -> str | None:
    props = (schema or {}).get("properties", {})
    for c in candidates:
        if c in props:
            return c
    for c in candidates:
        for k in props:
            if c in k.lower():
                return k
    return None


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    binary = build_test_binary()
    log(f"binary test: {binary}")

    client = MCPClient(CMD, STDERR_LOG)
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "chromly-ida-smoke", "version": "0.1.0"},
            },
            timeout=120,
        )
        if "error" in init:
            log(f"initialize lỗi: {init['error']}")
            return 1
        srv = init.get("result", {}).get("serverInfo", {})
        log(f"server: {srv.get('name', '?')} {srv.get('version', '')}".strip())
        client.notify("notifications/initialized")

        listing = client.request("tools/list", timeout=60)
        tools = listing.get("result", {}).get("tools", [])
        names = [t.get("name") for t in tools]
        log(f"tools/list: {len(tools)} tools: {', '.join(n for n in names if n)}")
        if len(tools) < 5:
            log("FAIL: cần ≥5 tool ida.*")
            return 1

        open_tool = pick_tool(tools, "open_database")
        exec_tool = pick_tool(tools, "execute_python")
        close_tool = pick_tool(tools, "close_database")
        for t in (open_tool, exec_tool, close_tool):
            if t is None:
                log("FAIL: thiếu tool open/execute/close")
                return 1

        # --- open_database
        schema = open_tool.get("inputSchema", {})
        key = pick_key(schema, "path", "file")
        if not key:
            log(f"FAIL: không đoán được param open_database: {json.dumps(schema)[:400]}")
            return 1
        resp = client.request(
            "tools/call",
            {"name": open_tool["name"], "arguments": {key: str(binary)}},
            timeout=240,
        )
        text = tool_text(resp)
        log(f"open_database → {text[:200]!r}")
        if resp.get("result", {}).get("isError"):
            log("FAIL: open_database isError")
            return 1

        # --- execute_python
        schema = exec_tool.get("inputSchema", {})
        key = pick_key(schema, "code", "script", "python")
        if not key:
            log(f"FAIL: không đoán được param execute_python: {json.dumps(schema)[:400]}")
            return 1
        resp = client.request(
            "tools/call",
            {
                "name": exec_tool["name"],
                "arguments": {key: "print('IDA-SMOKE-OK')"},
            },
            timeout=240,
        )
        text = tool_text(resp)
        log(f"execute_python → {text[:300]!r}")
        if "IDA-SMOKE-OK" not in text:
            log("FAIL: không thấy IDA-SMOKE-OK trong output")
            return 1

        # --- close_database
        schema = close_tool.get("inputSchema", {})
        args: dict = {}
        key = pick_key(schema, "save")
        if key:
            args[key] = False
        resp = client.request(
            "tools/call",
            {"name": close_tool["name"], "arguments": args},
            timeout=240,
        )
        log(f"close_database → {tool_text(resp)[:200]!r}")

        log("HANDSHAKE OK — IDA MCP sống, license + idalib hoạt động")
        return 0
    except Exception as exc:  # noqa: BLE001 — smoke: in mọi lỗi để debug
        log(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
