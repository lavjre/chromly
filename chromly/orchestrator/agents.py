"""Helpers cho agent runs — parse cost/tokens từ output `opencode run --format json`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def find_opencode() -> str | None:
    """Tìm opencode binary — kể cả khi PATH của systemd không có ~/.opencode/bin."""
    exe = shutil.which("opencode")
    if exe:
        return exe
    cand = Path.home() / ".opencode" / "bin" / "opencode"
    return str(cand) if cand.is_file() else None


def parse_session_usage(output: str) -> dict:
    """Sum cost + tokens từ các dòng step_finish trong output json."""
    cost = 0.0
    tokens_in = 0
    tokens_out = 0
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "step_finish":
            continue
        part = obj.get("part") or {}
        cost += float(part.get("cost") or 0)
        toks = part.get("tokens") or {}
        cache = toks.get("cache") or {}
        tokens_in += int(toks.get("input") or 0) + int(cache.get("read") or 0)
        tokens_out += int(toks.get("output") or 0)
    return {"cost_est": round(cost, 6), "tokens_in": tokens_in, "tokens_out": tokens_out}
