"""Upstream-regress delta audit — M2-06: quét test mới trong các commit mirror
sau revision của checkout → chạy trên out/calib → crash thật → crash store.

Ý tưởng: mỗi fix upstream (mới hơn snapshot) thường kèm regression test; nếu test
đó còn crash trên snapshot của mình thì bug đang SỐNG trong cây (ground truth tự
nhiên, khác calibration tự cài). Đây là trạm discovery "1-day" bổ sung cho Track B.

- `chromly intel audit [--max N] [--dry-run]` — chạy audit, in outcome từng test.
- Crash (ASAN/Check/signal) → store/crashes/<hash> (source='upstream-regress') +
  triage artifacts → auto-case pipeline bắt.
- Dedup theo sha256(nội dung test). Không commit gì vào checkout.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from chromly import paths
from chromly.intel.watcher import _git, mirror_dir_for
from chromly.store import db

CRASH_CODES = {134, 135, 136, 137, 138, 139}
FLAG_CONFLICT_MARKERS = (
    "Flag processing error",
    "Contradictory value for readonly flag",
)
CRASH_MARKERS = (
    "ERROR: AddressSanitizer",
    "Fatal error",
    "Check failed",
    "Received signal",
    "Fatal process out of memory",
)
TEST_NAME_RE = re.compile(r"(regress|turbolev|maglev|turboshaft)", re.IGNORECASE)
FLAGS_RE = re.compile(r"^// Flags:(.*)$", re.MULTILINE)


def audit_dir() -> Path:
    return paths.STORE_DIR / "regress-audit"


def _checkout_rev() -> str:
    proc = subprocess.run(
        ["git", "-C", str(paths.V8_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout.strip()


def _new_tests(mirror: Path, since_rev: str) -> list[dict]:
    """Trả [{path, sha}] — file test mới thêm sau since_rev, tên thuộc nhóm regress/jit."""
    rc, out = _git(
        ["log", "--diff-filter=A", "--name-only", "--format=@@%H", f"{since_rev}..origin/main"],
        mirror,
        timeout=300,
    )
    if rc != 0:
        raise RuntimeError(f"git log lỗi: {out[-300:]}")
    tests: list[dict] = []
    sha = None
    for line in out.splitlines():
        if line.startswith("@@"):
            sha = line[2:]
            continue
        if not line.startswith("test/") or not line.endswith(".js"):
            continue
        if "filecheck" in line or "test262" in line or "benchmark" in line:
            continue
        if not TEST_NAME_RE.search(Path(line).name):
            continue
        tests.append({"path": line, "sha": sha})
    return tests


def _extract(mirror: Path, sha: str, path: str) -> str | None:
    rc, out = _git(["show", f"{sha}:{path}"], mirror, timeout=120)
    return out if rc == 0 else None


def parse_flags(source: str) -> list[str]:
    flags: list[str] = []
    for m in FLAGS_RE.finditer(source):
        flags.extend(m.group(1).split())
    # --allow-natives-syntax luôn có (runner thêm), tránh trùng
    return [f for f in flags if f != "--allow-natives-syntax"]


def run_test(test_path: Path, source: str, timeout: int = 180) -> dict:
    d8 = paths.V8_ROOT / "out" / "calib" / "d8"
    if not d8.is_file():
        raise FileNotFoundError(f"thiếu {d8}")
    flags = parse_flags(source)
    cmd = [
        str(d8),
        "--allow-natives-syntax",
        *flags,
        "test/mjsunit/mjsunit.js",
        str(test_path),
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=paths.V8_ROOT, capture_output=True, text=True, timeout=timeout
        )
        rc = proc.returncode
        full = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return {"rc": None, "outcome": "timeout", "output_tail": "(timeout)", "flags": flags}
    output = full[-4000:]
    if any(m in full for m in FLAG_CONFLICT_MARKERS):
        outcome = "flag-conflict"
    elif rc in CRASH_CODES or rc < 0 or any(m in full for m in CRASH_MARKERS):
        outcome = "crash"
    elif rc != 0 or "FAILED" in full or "MjsUnitAssertionError" in full:
        outcome = "fail"
    else:
        outcome = "ok"
    return {"rc": rc, "outcome": outcome, "output_tail": output, "flags": flags}


def _file_crash(test_path: Path, source: str, sha: str, res: dict) -> str:
    from chromly.triage import classify, score

    # canonical text: mirror _extract strip() lại thêm "\n" — hash ổn định giữa các lần chạy
    text = source + "\n"
    h = hashlib.sha256(text.encode()).hexdigest()
    d = paths.STORE_DIR / "crashes" / h
    d.mkdir(parents=True, exist_ok=True)
    (d / f"program_{test_path.stem}.js").write_text(text)
    (d / "repro.flags.txt").write_text("\n".join(res["flags"]) + "\n")
    (d / "meta.json").write_text(
        json.dumps(
            {
                "hash": h,
                "unit": "upstream-regress",
                "source_sha": sha,
                "orig_test": f"upstream:{sha[:12]}:{test_path.name}",
                "created": time.time(),
            },
            indent=2,
        )
    )
    td = paths.STORE_DIR / "triage" / h
    td.mkdir(parents=True, exist_ok=True)
    (td / "repro.js").write_text(text)
    (td / "asan.txt").write_text(res["output_tail"])
    frames = [ln for ln in res["output_tail"].splitlines() if re.search(r"0x[0-9a-f]{8,}", ln)][
        :200
    ]
    (td / "symbols.txt").write_text("\n".join(frames))
    fault = classify.classify_text(res["output_tail"])
    sc = score.score(fault, res["output_tail"])
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT INTO crashes "
                "(hash, fault_type, severity, build_rev, source, state) "
                "VALUES (?, ?, ?, ?, 'upstream-regress', 'triaged') "
                "ON CONFLICT(hash) DO UPDATE SET "
                "fault_type=excluded.fault_type, severity=excluded.severity, state=excluded.state",
                (h, fault["class"], sc["score"], _checkout_rev()[:12]),
            )
    finally:
        con.close()
    return h


def audit(max_tests: int = 40, dry_run: bool = False) -> dict:
    mirror = mirror_dir_for("v8")
    if not (mirror / ".git").is_dir():
        raise FileNotFoundError(f"mirror chưa có: {mirror}")
    rev = _checkout_rev()
    tests = _new_tests(mirror, rev)[:max_tests]
    results: list[dict] = []
    for t in tests:
        source = _extract(mirror, t["sha"], t["path"])
        if source is None:
            continue
        name = Path(t["path"]).name
        if dry_run:
            results.append({"test": t["path"], "outcome": "dry"})
            continue
        tmp = audit_dir() / "tests" / Path(t["path"]).parent
        tmp.mkdir(parents=True, exist_ok=True)
        f = tmp / name
        f.write_text(source)
        res = run_test(f, source)
        row = {"test": t["path"], "sha": t["sha"][:12], "outcome": res["outcome"], "rc": res["rc"]}
        if res["outcome"] == "crash":
            row["crash_hash"] = _file_crash(f, source, t["sha"], res)[:12]
        results.append(row)
        print(f"[audit] {res['outcome']:<12} {name:<38} rc={res['rc']}", flush=True)
    summary = {
        "rev": rev,
        "scanned": len(results),
        "crashes": sum(1 for r in results if r["outcome"] == "crash"),
        "results": results,
        "ran": time.time(),
    }
    audit_dir().mkdir(parents=True, exist_ok=True)
    (audit_dir() / f"audit-{int(time.time())}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    return summary


def run_audit_cmd(args) -> int:
    def once() -> int:
        try:
            s = audit(max_tests=getattr(args, "max", 40), dry_run=getattr(args, "dry_run", False))
        except (FileNotFoundError, RuntimeError) as e:
            print(f"audit: {e}", flush=True)
            return 1
        print(
            f"[{datetime.now():%H:%M:%S}] audit: scanned={s['scanned']} crashes={s['crashes']} "
            f"(rev {s['rev'][:12]} → mirror origin/main)",
            flush=True,
        )
        for r in s["results"]:
            if r["outcome"] == "crash":
                print(f"  CRASH  {r['test']} → {r.get('crash_hash', '?')}", flush=True)
        return 0

    if getattr(args, "loop", False):
        interval = getattr(args, "interval", 86400.0)
        while True:
            once()
            time.sleep(interval)
    return once()
