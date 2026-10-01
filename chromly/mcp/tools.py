"""chromly-tools — handlers M4-02 (§5.7): case/crash/repro/build/fuzz/store/runs/kg.

Boundary duy nhất agent ↔ hạ tầng. Versioned v1. Mọi call log ở store/mcp-log.jsonl.
"""

from __future__ import annotations

import json
import re
import time

from chromly import paths
from chromly.fuzz import farm
from chromly.knowledge import kg as kg_mod
from chromly.store import db
from chromly.triage import repro as repro_mod

VERSION = "v1"
SAFE_KEY = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _log(tool: str, args: dict, ms: float, ok: bool, err: str = "") -> None:
    p = paths.STORE_DIR / "mcp-log.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "tool": tool,
                    "args": args,
                    "ms": round(ms, 1),
                    "ok": ok,
                    "err": err[:200],
                }
            )
            + "\n"
        )


# ---------------------------------------------------------------- handlers


def crash_list(args: dict) -> dict:
    state = args.get("state")
    limit = int(args.get("limit", 50))
    con = db.ensure_db()
    try:
        if state:
            rows = con.execute(
                "SELECT hash, fault_type, severity, state, dup_count, created FROM crashes "
                "WHERE state = ? ORDER BY id DESC LIMIT ?",
                (state, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT hash, fault_type, severity, state, dup_count, created FROM crashes "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {"crashes": [dict(r) for r in rows], "count": len(rows)}
    finally:
        con.close()


def crash_detail(args: dict) -> dict:
    hash_prefix = str(args["hash"])
    con = db.ensure_db()
    try:
        row = con.execute(
            "SELECT * FROM crashes WHERE hash LIKE ? LIMIT 1", (f"{hash_prefix}%",)
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise ValueError(f"không thấy crash {hash_prefix}")
    out = dict(row)
    triage = paths.STORE_DIR / "triage" / row["hash"]
    if (triage / "asan.txt").is_file():
        out["asan"] = (triage / "asan.txt").read_text()[-8000:]
    return out


def case_get(args: dict) -> dict:
    case_id = str(args["case_id"])
    con = db.ensure_db()
    try:
        row = con.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        raise ValueError(f"không thấy case {case_id}")
    return dict(row)


def case_update(args: dict) -> dict:
    case_id = str(args["case_id"])
    patch = dict(args.get("patch") or {})
    allowed = {"state", "verdict", "notes_path", "budget_used"}
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        raise ValueError("patch rỗng hoặc field không hợp lệ")
    sets = ", ".join(f"{k} = ?" for k in fields)
    con = db.ensure_db()
    try:
        with con:
            cur = con.execute(f"UPDATE cases SET {sets} WHERE id = ?", (*fields.values(), case_id))
        if cur.rowcount == 0:
            raise ValueError(f"không thấy case {case_id}")
        return {"updated": fields}
    finally:
        con.close()


VALID_BUILDS = ("asan", "calib", "release", "fuzzilli")


def repro_run(args: dict) -> dict:
    hash_prefix = str(args["crash_id"])
    build = str(args.get("build", "asan"))
    if build not in VALID_BUILDS:
        raise ValueError(f"build không hợp lệ: {build} (chọn: {', '.join(VALID_BUILDS)})")
    d8 = paths.V8_ROOT / "out" / build / "d8"
    ad = repro_mod.artifact_dir(hash_prefix)
    script = repro_mod.pick_script(ad)
    res = repro_mod.repro_run(
        d8, script, runs=int(args.get("runs", 5)), extra_flags=repro_mod.load_flags(ad)
    )
    return {
        "crash_id": hash_prefix,
        "build": build,
        **{k: res[k] for k in ("crashed", "of", "stable")},
    }


def build_request(args: dict) -> dict:
    """Spawn build detached; trả build_id (theo dõi qua build.status)."""
    import subprocess
    import sys
    import uuid

    from chromly.builds.args import CONFIG_NAMES

    config = str(args.get("config", "asan"))
    if config not in CONFIG_NAMES:
        raise ValueError(f"config không hợp lệ: {config} (chọn: {', '.join(CONFIG_NAMES)})")
    build_id = f"{config}-{uuid.uuid4().hex[:8]}"
    log = paths.STORE_DIR / "builds" / f"{build_id}.request.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "chromly.cli.app", "build", "--config", config]
    with log.open("a") as fh:
        subprocess.Popen(
            cmd,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(paths.REPO_ROOT),
        )
    return {"build_id": build_id, "config": config, "note": "theo dõi qua build.status"}


def build_status(args: dict) -> dict:
    from chromly.builds.v8 import recent_builds

    return {"builds": recent_builds(int(args.get("limit", 10)))}


def fuzz_status(args: dict) -> dict:
    from chromly.fuzz.metrics import total_execs

    st = farm.status()
    return {"units": st, "execs_per_sec_total": total_execs(st)}


def store_put(args: dict) -> dict:
    key = str(args["key"])
    if not SAFE_KEY.match(key):
        raise ValueError("key không hợp lệ")
    d = paths.STORE_DIR / "kv"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(args.get("value"), ensure_ascii=False))
    return {"ok": True, "key": key}


def store_get(args: dict) -> dict:
    key = str(args["key"])
    if not SAFE_KEY.match(key):
        raise ValueError("key không hợp lệ")
    p = paths.STORE_DIR / "kv" / f"{key}.json"
    if not p.is_file():
        raise ValueError(f"không thấy key {key}")
    return {"key": key, "value": json.loads(p.read_text())}


def runs_append(args: dict) -> dict:
    rec = dict(args.get("record") or {})
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT INTO runs (case_id, session_id, model, prompt_hash, tokens_in, tokens_out, "
                "cost_est, wall_s, outcome) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.get("case_id"),
                    rec.get("session_id"),
                    rec.get("model"),
                    rec.get("prompt_hash"),
                    rec.get("tokens_in"),
                    rec.get("tokens_out"),
                    rec.get("cost_est"),
                    rec.get("wall_s"),
                    rec.get("outcome"),
                ),
            )
        return {"ok": True}
    finally:
        con.close()


def kg_query(args: dict) -> dict:
    rows = kg_mod.query(type_=args.get("type"), ref_contains=args.get("ref"))
    return {"nodes": rows, "count": len(rows)}


def kg_neighbors(args: dict) -> dict:
    con = db.ensure_db()
    try:
        edges = kg_mod.neighbors(con, int(args["id"]), rel=args.get("rel"))
    finally:
        con.close()
    return {"edges": edges, "count": len(edges)}


HANDLERS: dict[str, dict] = {
    "case.get": {"fn": case_get, "desc": "Case state theo case_id"},
    "case.update": {"fn": case_update, "desc": "Cập nhật case (state/verdict/notes/budget)"},
    "crash.list": {"fn": crash_list, "desc": "Danh sách crash (filter state, limit)"},
    "crash.detail": {"fn": crash_detail, "desc": "Crash metadata + asan (theo hash)"},
    "repro.run": {"fn": repro_run, "desc": "Chạy repro trên build (asan|calib), trả tỉ lệ"},
    "build.request": {"fn": build_request, "desc": "Yêu cầu build (config) — detached"},
    "build.status": {"fn": build_status, "desc": "Danh sách build gần đây"},
    "fuzz.status": {"fn": fuzz_status, "desc": "Farm units + execs/s tổng"},
    "store.put": {"fn": store_put, "desc": "Lưu KV vào store/kv"},
    "store.get": {"fn": store_get, "desc": "Đọc KV từ store/kv"},
    "runs.append": {"fn": runs_append, "desc": "Ghi run vào ledger"},
    "kg.query": {"fn": kg_query, "desc": "Tìm node theo type/ref"},
    "kg.neighbors": {"fn": kg_neighbors, "desc": "Edges từ node id (rel?)"},
}
