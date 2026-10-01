"""Triage CLI — M3-01/02 + M1-09: `chromly triage [<hash>] [--loop]` và `chromly triage list`.

Loop (Track A tự động khép vòng): raw → repro/classify/score → triaged/flaky.
- backoff: không thử lại cùng crash trong RAW_RETRY_S.
- flaky re-check: chạy lại runs=20 mỗi FLAKY_RETRY_S; ổn định → triaged.
"""

from __future__ import annotations

import argparse
import time

from chromly import paths
from chromly.store import db
from chromly.triage import classify, dedup, repro, score

RAW_RETRY_S = 6 * 3600.0
FLAKY_RETRY_S = 2 * 3600.0
FLAKY_RUNS = 20


def triage_state(crashed: str, stable: bool) -> str:
    """flaky filter (§5.4): 0 repro → raw; chập chờn → 'flaky' (không auto-case); ổn → triaged."""
    n_ok, _, _ = crashed.partition("/")
    crashed_n = int(n_ok) if n_ok.isdigit() else 0
    if crashed_n == 0:
        return "raw"
    if not stable:
        return "flaky"
    return "triaged"


def _triage_age(full_hash: str) -> float | None:
    """Tuổi (giây) của lần triage gần nhất (kể cả lần lỗi); None nếu chưa từng."""
    td = paths.STORE_DIR / "triage" / full_hash
    stamps = [p.stat().st_mtime for p in (td / "asan.txt", td / "error.txt") if p.is_file()]
    return time.time() - max(stamps) if stamps else None


def pick_candidate() -> tuple[str, int] | None:
    """(hash_prefix, runs): raw mới (qua backoff) trước, rồi flaky đến hạn re-check."""
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT hash FROM crashes WHERE state = 'raw' ORDER BY id DESC LIMIT 30"
        ).fetchall()
        for r in rows:
            age = _triage_age(r["hash"])
            if age is None or age > RAW_RETRY_S:
                return r["hash"][:12], 5
        rows = con.execute(
            "SELECT hash FROM crashes WHERE state = 'flaky' ORDER BY id ASC LIMIT 30"
        ).fetchall()
        for r in rows:
            age = _triage_age(r["hash"])
            if age is None or age > FLAKY_RETRY_S:
                return r["hash"][:12], FLAKY_RUNS
    finally:
        con.close()
    return None


def triage_one(hash_prefix: str, runs: int = 5) -> int:
    try:
        res = repro.run_triage(hash_prefix, runs=runs)
    except (FileNotFoundError, RuntimeError) as exc:
        # ghi dấu lỗi để backoff không quay crash không-triagable mỗi tick
        con = db.ensure_db()
        try:
            row = con.execute(
                "SELECT hash FROM crashes WHERE hash LIKE ?", (f"{hash_prefix}%",)
            ).fetchone()
        finally:
            con.close()
        if row:
            td = paths.STORE_DIR / "triage" / row["hash"]
            td.mkdir(parents=True, exist_ok=True)
            (td / "error.txt").write_text(str(exc))
        print(f"triage lỗi ({hash_prefix}): {exc}", flush=True)
        return 1

    asan_text = (repro.triage_dir(res["hash"]) / "asan.txt").read_text()
    fault = classify.classify_text(asan_text)
    sc = score.score(fault, asan_text)
    stack_h = dedup.stack_hash(asan_text, fault["class"])
    h12 = res["hash"][:12]

    state = triage_state(res["crashed"], res["stable"])

    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "UPDATE crashes SET fault_type = ?, stack_norm = ?, severity = ?, "
                "state = ? WHERE hash LIKE ?",
                (fault["class"], stack_h, sc["score"], state, f"{h12}%"),
            )
    finally:
        con.close()

    print(
        f"[{time.strftime('%H:%M:%S')}] triage {h12}: repro={res['crashed']} "
        f"stable={res['stable']} → state={state}",
        flush=True,
    )
    reasons = ", ".join(sc["reasons"]) or "no reasons"
    print(f"  class={fault['class']} access={fault['access']} score={sc['score']} ({reasons})")
    print(f"  artifacts: {repro.triage_dir(res['hash'])}")
    return 0


def triage_once() -> bool:
    """Xử lý 1 candidate (tôn trọng backoff). True nếu có việc."""
    cand = pick_candidate()
    if cand is None:
        return False
    prefix, runs = cand
    print(f"[{time.strftime('%H:%M:%S')}] triage: xử lý {prefix} (runs={runs})", flush=True)
    triage_one(prefix, runs=runs)
    return True


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

    if getattr(args, "loop", False):
        interval = getattr(args, "interval", 300.0)
        while True:
            try:
                if not triage_once():
                    print(f"[{time.strftime('%H:%M:%S')}] triage: 0 candidate", flush=True)
            except Exception as exc:  # noqa: BLE001 — loop dài hạn
                print(f"triage loop lỗi: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(interval)

    hash_prefix = getattr(args, "hash", None)
    if hash_prefix:
        return triage_one(hash_prefix, runs=getattr(args, "runs", 5))
    if not triage_once():
        print("triage: không có crash raw nào đến hạn")
    return 0
