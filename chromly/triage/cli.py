"""Triage CLI — M3-01/02: `chromly triage <hash>` và `chromly triage list`."""

from __future__ import annotations

import argparse

from chromly.store import db
from chromly.triage import classify, dedup, repro, score


def _latest_raw_crash() -> str | None:
    con = db.ensure_db()
    try:
        row = con.execute(
            "SELECT hash FROM crashes WHERE state = 'raw' ORDER BY created DESC LIMIT 1"
        ).fetchone()
        return row["hash"][:12] if row else None
    finally:
        con.close()


def run_triage_cmd(args: argparse.Namespace) -> int:
    sub = getattr(args, "triage_cmd", None)
    if sub == "list":
        con = db.ensure_db()
        try:
            rows = con.execute(
                "SELECT hash, fault_type, severity, state, dup_count, created FROM crashes "
                "ORDER BY id DESC LIMIT 50"
            ).fetchall()
        finally:
            con.close()
        for r in rows:
            score_s = r["severity"] if r["severity"] is not None else "-"
            print(
                f"[{r['state']:<8}] {r['hash'][:12]} "
                f"{(r['fault_type'] or '-'):<24} score={score_s} dup={r['dup_count']}"
            )
        print(f"({len(rows)} rows)")
        return 0

    hash_prefix = getattr(args, "hash", None) or _latest_raw_crash()
    if not hash_prefix:
        print("triage: không có crash raw nào")
        return 0

    try:
        res = repro.run_triage(hash_prefix, runs=getattr(args, "runs", 5))
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"triage lỗi: {exc}")
        return 1

    asan_text = (repro.triage_dir(res["hash"]) / "asan.txt").read_text()
    fault = classify.classify_text(asan_text)
    sc = score.score(fault, asan_text)
    stack_h = dedup.stack_hash(asan_text, fault["class"])
    h12 = res["hash"][:12]

    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "UPDATE crashes SET fault_type = ?, stack_norm = ?, severity = ?, "
                "state = 'triaged' WHERE hash LIKE ?",
                (fault["class"], stack_h, sc["score"], f"{h12}%"),
            )
    finally:
        con.close()

    print(f"triage {h12}: repro={res['crashed']} stable={res['stable']}")
    reasons = ", ".join(sc["reasons"]) or "no reasons"
    print(f"  class={fault['class']} access={fault['access']} score={sc['score']} ({reasons})")
    print(f"  artifacts: {repro.triage_dir(res['hash'])}")
    return 0
