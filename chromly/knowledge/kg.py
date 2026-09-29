"""Knowledge layer v0 — M2-04: nodes/edges/lessons + ingest + query (§7.3).

Graph-ready trong SQLite. Nguồn ghi (M2): intel review (commit + variant hypotheses).
Query log mọi lần gọi vào store/kg_log.jsonl — chuẩn bị cho kg.query qua MCP (M4).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from chromly import paths
from chromly.store import db


def kg_log_path() -> Path:
    return paths.STORE_DIR / "kg_log.jsonl"


def intel_case_dir(sha: str) -> Path:
    return paths.STORE_DIR / "intel" / sha


def add_node(
    con, type_: str, ref: str, attrs: dict | None = None, case_id: str | None = None
) -> int:
    cur = con.execute(
        "INSERT INTO kg_nodes (type, ref, attrs_json, case_id) VALUES (?, ?, ?, ?)",
        (type_, ref, json.dumps(attrs or {}, ensure_ascii=False), case_id),
    )
    return int(cur.lastrowid)


def find_node(con, type_: str, ref: str):
    return con.execute("SELECT * FROM kg_nodes WHERE type = ? AND ref = ?", (type_, ref)).fetchone()


def upsert_node(
    con, type_: str, ref: str, attrs: dict | None = None, case_id: str | None = None
) -> int:
    row = find_node(con, type_, ref)
    if row is not None:
        return int(row["id"])
    return add_node(con, type_, ref, attrs, case_id)


def add_edge(con, src_id: int, dst_id: int, rel: str, attrs: dict | None = None) -> None:
    row = con.execute(
        "SELECT 1 FROM kg_edges WHERE src_id = ? AND dst_id = ? AND rel = ?",
        (src_id, dst_id, rel),
    ).fetchone()
    if row is not None:
        return
    con.execute(
        "INSERT INTO kg_edges (src_id, dst_id, rel, attrs_json) VALUES (?, ?, ?, ?)",
        (src_id, dst_id, rel, json.dumps(attrs or {}, ensure_ascii=False)),
    )


def neighbors(con, node_id: int, rel: str | None = None) -> list[dict]:
    q = (
        "SELECT e.rel AS rel, e.src_id AS src_id, e.dst_id AS dst_id, "
        "n.type AS type, n.ref AS ref "
        "FROM kg_edges e JOIN kg_nodes n ON n.id = e.dst_id WHERE e.src_id = ?"
    )
    params: list = [node_id]
    if rel:
        q += " AND e.rel = ?"
        params.append(rel)
    return [dict(r) for r in con.execute(q, params)]


def log_query(entry: dict) -> None:
    p = kg_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps({"ts": time.time(), **entry}, ensure_ascii=False) + "\n")


def ingest_review(sha: str) -> dict:
    """Ingest một intel review: commit node + variant hypothesis nodes (+ edge derived_from)."""
    d = intel_case_dir(sha)
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").is_file() else {}
    variants_path = d / "variants.json"
    variants: list = []
    if variants_path.is_file():
        try:
            variants = json.loads(variants_path.read_text())
        except json.JSONDecodeError:
            variants = []

    con = db.ensure_db()
    try:
        with con:
            commit_id = upsert_node(
                con, "commit", sha, {"subject": meta.get("subject", ""), "date": meta.get("date")}
            )
            for v in variants:
                title = str(v.get("title", "?"))
                vid = upsert_node(con, "hypothesis", f"{sha}:{title}", v)
                add_edge(con, vid, commit_id, "derived_from")
        return {"sha": sha[:12], "commit_node": commit_id, "variants": len(variants)}
    finally:
        con.close()


def query(type_: str | None = None, ref_contains: str | None = None) -> list[dict]:
    con = db.ensure_db()
    q = "SELECT * FROM kg_nodes WHERE 1=1"
    params: list = []
    if type_:
        q += " AND type = ?"
        params.append(type_)
    if ref_contains:
        q += " AND ref LIKE ?"
        params.append(f"%{ref_contains}%")
    rows = [dict(r) for r in con.execute(q, params)]
    con.close()
    log_query({"kind": "query", "type": type_, "ref_contains": ref_contains, "n": len(rows)})
    return rows


def run_kg_cmd(args) -> int:
    cmd = getattr(args, "kg_cmd", None)
    if cmd == "ingest":
        sha = args.sha
        res = ingest_review(sha)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if cmd == "query":
        rows = query(type_=getattr(args, "type", None), ref_contains=getattr(args, "ref", None))
        for r in rows:
            print(f"[{r['id']}] {r['type']} :: {r['ref']}")
        print(f"({len(rows)} nodes)")
        return 0
    if cmd == "neighbors":
        con = db.ensure_db()
        try:
            rows = neighbors(con, args.id)
        finally:
            con.close()
        for r in rows:
            print(f"--{r['rel']}--> [{r['type']}] {r['ref']}")
        print(f"({len(rows)} edges)")
        return 0
    print("usage: chromly kg {ingest|query|neighbors}")
    return 2
