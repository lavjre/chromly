"""V8 build rig (§5.1): gclient shallow checkout + gn + ninja.

- Checkout: CHROMLY_V8_ROOT (default ~/v8/v8); gclient solution root = parent (~/v8).
- Build record: store/builds/<id>.json (+ .log), ghi DB bảng builds (§7.1).
- Systemd slice (§6.4) sẽ tự kế thừa khi supervisor chạy dưới chromly-build.slice (M1);
  ở M0 chạy nice 10 để không tranh CPU.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.builds.args import args_gn_text, load_config
from chromly.store import db

DEPOT_TOOLS = Path.home() / "tools" / "depot_tools"
JOBS = "6"
V8_URL = "https://chromium.googlesource.com/v8/v8.git"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{DEPOT_TOOLS}:{env.get('PATH', '')}"
    return env


def _run(cmd: list[str], cwd: Path, log: Path) -> int:
    with log.open("a") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n")
        fh.flush()
        proc = subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, env=_env())
    return proc.returncode


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _git_rev(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            env=_env(),
        )
        return out.stdout.strip()
    except OSError:
        return ""


def _save_record(rec: dict, log: Path) -> None:
    rec["log_path"] = str(log)
    rec_path = paths.BUILDS_DIR / f"{rec['id']}.json"
    rec_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT OR REPLACE INTO builds "
            "(id, config, rev, status, artifact_path, duration_s, started, finished) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec["id"],
                rec["config"],
                rec.get("rev"),
                rec["status"],
                rec.get("artifact_path"),
                rec.get("duration_s"),
                rec.get("started"),
                rec.get("finished"),
            ),
        )
    con.close()


def sync(rev: str | None = None, log: Path | None = None) -> int:
    """gclient shallow sync. Tạo .gclient nếu chưa có. Trả exit code."""
    root = paths.V8_ROOT
    parent = root.parent
    parent.mkdir(parents=True, exist_ok=True)
    log = log or paths.BUILDS_DIR / f"sync-{dt.datetime.now():%Y%m%d-%H%M%S}.log"
    if not (parent / ".gclient").exists():
        rc = _run(["gclient", "config", "--name", root.name, V8_URL], parent, log)
        if rc:
            return rc
    cmd = ["gclient", "sync", "--no-history", "-j8"]
    if rev:
        cmd += ["--revision", f"{root.name}@{rev}"]
    return _run(cmd, parent, log)


def run_build(config: str, rev: str | None = None, fetch_only: bool = False) -> int:
    paths.ensure_dirs()
    cfg = load_config(config)
    root = paths.V8_ROOT
    build_id = f"{config}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    log = paths.BUILDS_DIR / f"{build_id}.log"
    rec: dict = {
        "id": build_id,
        "config": config,
        "rev": rev,
        "status": "running",
        "started": _now(),
    }
    _save_record(rec, log)

    def finish(rc: int) -> int:
        rec["status"] = "ok" if rc == 0 else "error"
        rec["rev"] = _git_rev(root) or rev
        rec["finished"] = _now()
        _save_record(rec, log)
        return rc

    if fetch_only or not (root / ".git").is_dir() or rev:
        rc = sync(rev, log)
        if rc:
            return finish(rc)
        if fetch_only:
            return finish(0)

    out = root / "out" / config
    clean = not (out / ".ninja_log").exists()  # full build nếu out chưa từng ninja thành công
    out.mkdir(parents=True, exist_ok=True)
    (out / "args.gn").write_text(args_gn_text(config))
    rec["clean"] = clean

    rc = _run(["gn", "gen", str(out)], root, log)
    if rc:
        return finish(rc)

    t0 = time.monotonic()
    rc = _run(["nice", "-n", "10", "autoninja", "-C", str(out), "-j", JOBS, cfg.target], root, log)
    rec["duration_s"] = round(time.monotonic() - t0, 1)
    rec["artifact_path"] = str(out / cfg.target)
    return finish(rc)


def recent_builds(n: int = 10) -> list[dict]:
    paths.ensure_dirs()
    recs = sorted(paths.BUILDS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in recs[:n]:
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def run_build_cmd(args: argparse.Namespace) -> int:
    if args.status:
        rows = recent_builds()
        if not rows:
            print("chưa có build nào trong store/builds/")
            return 0
        for r in rows:
            dur = r.get("duration_s")
            dur_s = f"{dur:8.1f}s" if isinstance(dur, (int, float)) else "     —  "
            print(
                f"{r.get('id', '?'):<40} {r.get('status', '?'):<8} "
                f"{dur_s}  {(r.get('rev') or '')[:12]}"
            )
        return 0
    rc = run_build(args.config, rev=args.rev, fetch_only=args.fetch_only)
    if rc == 0:
        rows = recent_builds(1)
        if rows:
            r = rows[0]
            rev = (r.get("rev") or "")[:12]
            print(f"build {r['id']}: {r['status']} ({r.get('duration_s', '?')}s) rev={rev}")
    else:
        print(f"build lỗi (rc={rc}) — xem log trong {paths.BUILDS_DIR}/")
    return rc
