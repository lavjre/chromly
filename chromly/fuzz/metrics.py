"""Metrics v0 — M1-07: sampler 60s → metrics.jsonl + DB (M3 mở rộng rollup/alert).

`chromly fuzz metrics` chạy sampler; status tổng đọc qua metrics.total_execs.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from chromly.fuzz import farm
from chromly.store import db


def metrics_jsonl() -> Path:
    return farm.FUZZ_DIR / "metrics.jsonl"


def sample_once() -> dict:
    st = farm.status()
    sample = {"ts": time.time(), "units": st}
    path = metrics_jsonl()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(sample) + "\n")

    con = db.ensure_db()
    try:
        with con:
            for name, info in st.items():
                if not info.get("alive"):
                    continue
                tags = json.dumps({"type": info.get("type")})
                if isinstance(info.get("execs_per_sec"), (int, float)):
                    con.execute(
                        "INSERT INTO metrics (ts, scope, name, value, tags) "
                        "VALUES (datetime('now'), ?, 'execs_per_sec', ?, ?)",
                        (name, float(info["execs_per_sec"]), tags),
                    )
                if info.get("rss_mb") is not None:
                    con.execute(
                        "INSERT INTO metrics (ts, scope, name, value, tags) "
                        "VALUES (datetime('now'), ?, 'rss_mb', ?, ?)",
                        (name, float(info["rss_mb"]), tags),
                    )
    finally:
        con.close()
    return sample


def total_execs(st: dict | None = None) -> float:
    st = st if st is not None else farm.status()
    total = 0.0
    for info in st.values():
        value = info.get("execs_per_sec")
        if isinstance(value, (int, float)):
            total += float(value)
    return total


def run_sampler(interval: float = 60.0, once: bool = False) -> int:
    while True:
        sample_once()
        if once:
            return 0
        time.sleep(interval)
