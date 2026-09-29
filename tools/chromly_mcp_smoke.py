#!/usr/bin/env python3
"""Smoke client cho chromly-tools MCP (M4-02).

Spawn `python -m chromly.cli.app mcp serve`, chạy:
initialize → tools/list (≥12) → crash.list → kg.query → store.put/get → check mcp-log.

Exit 0 = OK.
"""

from __future__ import annotations

import json
import select
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CMD = [sys.executable, "-m", "chromly.cli.app", "mcp", "serve"]


def log(msg: str) -> None:
    print(f"[mcp-smoke] {msg}", flush=True)


class Client:
    def __init__(self, cmd: list[str]):
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(REPO),
        )
        self._next = 0

    def request(self, method: str, params: dict | None = None, timeout: float = 60) -> dict:
        self._next += 1
        mid = self._next
        assert self.proc.stdin is not None
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
            + "\n"
        )
        self.proc.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timeout {method}")
            ready, _, _ = select.select([self.proc.stdout], [], [], min(remaining, 5))
            if not ready:
                continue
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("server đóng stdout")
            msg = json.loads(line)
            if msg.get("id") == mid:
                return msg

    def notify(self, method: str, params: dict | None = None) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n"
        )
        self.proc.stdin.flush()

    def call_tool(self, name: str, args: dict | None = None) -> dict:
        resp = self.request("tools/call", {"name": name, "arguments": args or {}})
        result = resp.get("result", {})
        if result.get("isError"):
            raise RuntimeError(f"tool {name} lỗi: {result.get('content')}")
        text = "".join(c.get("text", "") for c in result.get("content", []))
        return json.loads(text) if text else {}

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


def main() -> int:
    client = Client(CMD)
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "chromly-mcp-smoke", "version": "0.1"},
            },
        )
        srv = init.get("result", {}).get("serverInfo", {})
        log(f"server: {srv.get('name')} {srv.get('version')}")
        client.notify("notifications/initialized")

        listing = client.request("tools/list")
        tools = listing["result"]["tools"]
        names = [t["name"] for t in tools]
        log(f"tools: {len(tools)} — {', '.join(names)}")
        required = {
            "case.get",
            "case.update",
            "crash.list",
            "crash.detail",
            "repro.run",
            "build.request",
            "build.status",
            "fuzz.status",
            "store.put",
            "store.get",
            "runs.append",
            "kg.query",
            "kg.neighbors",
        }
        missing = required - set(names)
        if missing:
            log(f"FAIL: thiếu tool {missing}")
            return 1

        r = client.call_tool("crash.list", {"limit": 5})
        log(f"crash.list → {r['count']} rows")

        r = client.call_tool("kg.query", {"type": "hypothesis"})
        log(f"kg.query → {r['count']} nodes")

        client.call_tool("store.put", {"key": "smoke", "value": {"ok": True}})
        r = client.call_tool("store.get", {"key": "smoke"})
        assert r["value"]["ok"] is True, r

        r = client.call_tool("fuzz.status")
        log(f"fuzz.status → execs_total={r['execs_per_sec_total']}")

        log("MCP OK")
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
