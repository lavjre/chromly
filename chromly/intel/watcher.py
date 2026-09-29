"""Intel watcher — M2-01: mirror V8 (shallow/blob:none) + poll + filter commits (§5.3).

Filter: path labels (jit/maglev/turboshaft/wasm/regexp/parser/compiler/sandbox...) hoặc
keyword security trong subject. Commit lọt → DB `intel` (pending) + diff dump store/intel/<sha>/.
Lag = giờ kể từ commit mới nhất nhìn thấy (mục tiêu <24h).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from chromly import paths
from chromly.store import db

V8_URL = "https://github.com/v8/v8.git"  # GitHub mirror (§5.3) — partial clone nhẹ hơn googlesource

PATH_LABELS = (
    "src/jit/",
    "src/maglev/",
    "src/turboshaft/",
    "src/compiler/",
    "src/parsing/",
    "src/regexp/",
    "src/wasm/",
    "src/objects/",
    "src/runtime/",
    "src/builtins/",
    "src/codegen/",
    "src/sandbox/",
)

KEYWORDS = (
    "security",
    "sandbox",
    "bounds",
    "out of bounds",
    "out-of-bounds",
    "overflow",
    "underflow",
    "use-after-free",
    "use after free",
    "uaf",
    "type confusion",
    "cve",
    "exploit",
    "fix crash",
    "regression",
    "dcheck",
    "fuzz",
)


def mirror_dir() -> Path:
    return Path.home() / "mirrors" / "v8"


def state_path() -> Path:
    return paths.STORE_DIR / "intel" / "state.json"


def intel_dir() -> Path:
    return paths.STORE_DIR / "intel"


def _git(args: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _load_state() -> dict:
    p = state_path()
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_state(state: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2))


def ensure_mirror() -> None:
    m = mirror_dir()
    if (m / ".git").is_dir():
        return
    m.parent.mkdir(parents=True, exist_ok=True)
    rc, out = _git(
        ["clone", "--filter=blob:none", "--no-checkout", V8_URL, str(m)],
        m.parent,
        timeout=7200,
    )
    if rc != 0:
        raise RuntimeError(f"clone mirror lỗi: {out[-500:]}")


def match_commit(subject: str, changed_paths: list[str]) -> bool:
    for p in changed_paths:
        if any(label in p for label in PATH_LABELS):
            return True
    s = subject.lower()
    return any(k in s for k in KEYWORDS)


def parse_lag_hours(iso_date: str) -> float | None:
    try:
        dt = datetime.fromisoformat(iso_date)
    except ValueError:
        return None
    return round((time.time() - dt.timestamp()) / 3600.0, 1)


MAX_DIFF_BYTES = 300_000


def poll_once(since_days: int = 7, max_commits: int = 200) -> dict:
    ensure_mirror()
    m = mirror_dir()
    rc, out = _git(["fetch", "-q", "origin", "main", "--filter=blob:none"], m, timeout=3600)
    if rc != 0:
        raise RuntimeError(f"fetch lỗi: {out[-500:]}")

    state = _load_state()
    last = state.get("last_sha")
    fmt = "--format=%H\x1f%cI\x1f%s"
    if last:
        log_args = ["log", fmt, f"--max-count={max_commits}", f"{last}..FETCH_HEAD"]
    else:
        log_args = [
            "log",
            fmt,
            f"--since={since_days} days ago",
            f"--max-count={max_commits}",
            "FETCH_HEAD",
        ]
    rc, out = _git(log_args, m)
    if rc != 0:
        raise RuntimeError(f"git log lỗi: {out[-500:]}")

    commits: list[dict] = []
    for line in out.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) == 3:
            commits.append({"sha": parts[0], "date": parts[1], "subject": parts[2]})

    result = {
        "seen": len(commits),
        "matched": 0,
        "new": 0,
        "latest_sha": commits[0]["sha"] if commits else last,
        "lag_hours": parse_lag_hours(commits[0]["date"]) if commits else None,
    }
    if not commits:
        # vẫn tính lag từ head hiện tại (không có commit mới nhưng mirror vẫn fresh)
        rc, out = _git(["log", "-1", "--format=%cI", "FETCH_HEAD"], m)
        if rc == 0 and out.strip():
            result["lag_hours"] = parse_lag_hours(out.strip())
        return result

    con = db.ensure_db()
    try:
        for c in commits:
            rc, paths_out = _git(["show", "--name-only", "--format=", c["sha"]], m)
            changed = [p for p in paths_out.splitlines() if p.strip()]
            if not match_commit(c["subject"], changed):
                continue
            result["matched"] += 1
            row = con.execute('SELECT 1 FROM intel WHERE "commit" = ?', (c["sha"],)).fetchone()
            if row is not None:
                continue
            out_dir = intel_dir() / c["sha"]
            out_dir.mkdir(parents=True, exist_ok=True)
            _, diff = _git(["show", "--stat", "--patch", c["sha"]], m, timeout=180)
            if len(diff.encode()) > MAX_DIFF_BYTES:
                _, stat = _git(["show", "--stat", "--format=%H%n%cI%n%s", c["sha"]], m)
                hint = f"xem full: git -C {m} show {c['sha']}"
                diff = f"{stat}\n\n(diff >{MAX_DIFF_BYTES} bytes — bỏ bớt; {hint})\n"
            (out_dir / "commit.diff").write_text(diff)
            (out_dir / "meta.json").write_text(
                json.dumps(
                    {"sha": c["sha"], "date": c["date"], "subject": c["subject"], "paths": changed},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            with con:
                con.execute(
                    'INSERT INTO intel ("commit", paths, review_status, variant_flag) '
                    "VALUES (?, ?, 'pending', 0)",
                    (c["sha"], json.dumps(changed)),
                )
            result["new"] += 1
    finally:
        con.close()

    state["last_sha"] = commits[0]["sha"]
    state["last_poll"] = time.time()
    state["last_lag_hours"] = result["lag_hours"]
    _save_state(state)
    return result


def run_intel_cmd(args: argparse.Namespace) -> int:
    cmd = getattr(args, "intel_cmd", None)
    if cmd == "watch":
        if getattr(args, "once", False):
            res = poll_once(since_days=args.since_days, max_commits=args.max)
            print(
                f"intel watch: seen={res['seen']} matched={res['matched']} new={res['new']} "
                f"lag={res['lag_hours']}h latest={res['latest_sha']}"
            )
            return 0
        while True:
            try:
                res = poll_once(since_days=args.since_days, max_commits=args.max)
                print(
                    f"[{datetime.now():%H:%M:%S}] seen={res['seen']} matched={res['matched']} "
                    f"new={res['new']} lag={res['lag_hours']}h"
                )
            except Exception as exc:  # noqa: BLE001 — loop dài hạn: log rồi thử lại
                print(f"[{datetime.now():%H:%M:%S}] watch lỗi: {type(exc).__name__}: {exc}")
            time.sleep(3600)
    if cmd == "status":
        from chromly.intel.status import run_status

        return run_status()
    if cmd == "review":
        from chromly.intel.runner import run_intel_review

        return run_intel_review(limit=getattr(args, "limit", 5), sha=getattr(args, "sha", None))
    if cmd == "variants":
        from chromly.intel.variants import run_variants_cmd

        return run_variants_cmd(args)
    print("usage: chromly intel {watch|review|variants|status}")
    return 2
