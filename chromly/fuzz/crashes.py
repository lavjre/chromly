"""Crash store — M1-05: incoming → store/crashes/<hash>/ + DB (dedup), <5'.

Sources: fuzzilli `crashes/`, libFuzzer `artifacts/` (M1-03). Ingest loop mặc định 15s.
Registry `ingest_seen.json` (path:size:mtime) — không đụng file gốc của fuzzer.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm
from chromly.store import db


def crashes_dir() -> Path:
    return paths.STORE_DIR / "crashes"


def seen_path() -> Path:
    return farm.FUZZ_DIR / "ingest_seen.json"


def _sources() -> dict[str, Path]:
    """unit name → dir chứa file crash (chỉ dir tồn tại)."""
    base = farm.FUZZ_DIR
    candidates = {
        "fuzzilli": base / "fuzzilli" / "crashes",
        "libfuzzer-parser": base / "libfuzzer-parser" / "artifacts",
        "libfuzzer-wasm": base / "libfuzzer-wasm" / "artifacts",
    }
    return {name: d for name, d in candidates.items() if d.is_dir()}


def _load_seen() -> set[str]:
    p = seen_path()
    if p.is_file():
        try:
            return set(json.loads(p.read_text()))
        except json.JSONDecodeError:
            pass
    return set()


def _save_seen(seen: set[str]) -> None:
    seen_path().parent.mkdir(parents=True, exist_ok=True)
    seen_path().write_text(json.dumps(sorted(seen), indent=0))


def _v8_rev() -> str:
    state = farm._load_state()
    for rec in state["units"].values():
        if rec.get("v8_rev"):
            return rec["v8_rev"]
    return "?"


def ingest_once() -> list[dict]:
    """Quét sources, nhập file mới → store + DB. Trả danh sách đã nhập."""
    seen = _load_seen()
    results: list[dict] = []
    con = db.ensure_db()
    try:
        for unit_name, src in _sources().items():
            for f in sorted(src.iterdir()):
                if not f.is_file():
                    continue
                # fuzzilli: .fzil là canonical; .js là sidecar cùng basename (ghi SAU .js
                # trong Storage.swift — .js xuất hiện trước). .js mồ côi (thoát giữa chừng,
                # không có .fzil) vẫn phải nhập, nếu không crash đó bị bỏ vĩnh viễn.
                if (
                    unit_name == "fuzzilli"
                    and f.suffix == ".js"
                    and f.with_suffix(".fzil").is_file()
                ):
                    continue
                st = f.stat()
                key = f"{f}:{st.st_size}:{int(st.st_mtime)}"
                if key in seen:
                    continue
                sidecar = None
                if unit_name == "fuzzilli" and f.suffix == ".fzil":
                    cand = f.with_suffix(".js")
                    if cand.is_file():
                        sidecar = cand
                data = f.read_bytes()
                h = hashlib.sha256(data).hexdigest()
                row = con.execute("SELECT dup_count FROM crashes WHERE hash = ?", (h,)).fetchone()
                if row is not None:
                    with con:
                        con.execute(
                            "UPDATE crashes SET dup_count = dup_count + 1 WHERE hash = ?", (h,)
                        )
                    results.append({"hash": h[:12], "unit": unit_name, "dup": True})
                else:
                    dest = crashes_dir() / h
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest / f.name)
                    if sidecar is not None:
                        shutil.copy2(sidecar, dest / sidecar.name)
                        sst = sidecar.stat()
                        seen.add(f"{sidecar}:{sst.st_size}:{int(sst.st_mtime)}")
                    (dest / "meta.json").write_text(
                        json.dumps(
                            {
                                "hash": h,
                                "unit": unit_name,
                                "orig_path": str(f),
                                "v8_rev": _v8_rev(),
                                "created": time.time(),
                            },
                            indent=2,
                        )
                    )
                    with con:
                        con.execute(
                            "INSERT INTO crashes (hash, fault_type, build_rev, source, state) "
                            "VALUES (?, ?, ?, ?, 'raw')",
                            (h, None, _v8_rev(), unit_name),
                        )
                    results.append({"hash": h[:12], "unit": unit_name, "dup": False})
                seen.add(key)
        _save_seen(seen)
    finally:
        con.close()
    return results


def run_ingest(once: bool = False, interval: float = 15.0) -> int:
    while True:
        for r in ingest_once():
            tag = "dup" if r["dup"] else "new"
            print(f"crash [{tag}] {r['hash']} ← {r['unit']}", flush=True)
        if once:
            return 0
        time.sleep(interval)
