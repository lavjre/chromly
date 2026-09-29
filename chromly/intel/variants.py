"""Variant test runner — M2-03: variants.json → test JS + chạy trên d8 builds.

- generate: mỗi variant có `test_js` → `tests/INTEL-<sha12>/variant-N.js` (kèm header comment).
- run: chạy từng test trên `out/asan/d8` (+ `out/release/d8` nếu có) — timeout 60s,
  outcome: crash | error | ok | timeout. Kết quả ghi results.json + DB intel.variant_flag.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.intel.watcher import intel_dir
from chromly.store import db

TIMEOUT_S = 60
CRASH_CODES = {134, 135, 136, 137, 138, 139}


def builds_dir() -> Path:
    return paths.V8_ROOT / "out"


def tests_dir_for(sha: str) -> Path:
    return paths.REPO_ROOT / "tests" / f"INTEL-{sha[:12]}"


def generate_for(sha: str) -> list[dict]:
    src = intel_dir() / sha / "variants.json"
    if not src.is_file():
        return []
    try:
        variants = json.loads(src.read_text())
    except json.JSONDecodeError:
        return []
    out_dir = tests_dir_for(sha)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    idx = 0
    for v in variants:
        test_js = (v.get("test_js") or "").strip()
        if not test_js:
            continue
        idx += 1
        fname = f"variant-{idx}.js"
        header = (
            f"// chromly variant — {v.get('title', '?')} "
            f"(confidence: {v.get('confidence', '?')})\n"
            f"// nguồn: store/intel/{sha}/variants.json — sinh tự động, review trước khi tin\n"
        )
        (out_dir / fname).write_text(header + test_js + "\n")
        generated.append({"file": fname, "title": v.get("title", "?"), "variant": v})
    return generated


def run_test(d8: Path, test: Path) -> dict:
    try:
        proc = subprocess.run(
            [str(d8), "--allow-natives-syntax", str(test)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
        rc = proc.returncode
        output = (proc.stdout + proc.stderr)[-2000:]
        if rc in CRASH_CODES or rc < 0:
            outcome = "crash"
        elif rc != 0 or "Uncaught" in output or "uncaught" in output:
            outcome = "error"
        else:
            outcome = "ok"
    except subprocess.TimeoutExpired:
        rc = None
        output = "(timeout)"
        outcome = "timeout"
    return {"rc": rc, "outcome": outcome, "output_tail": output}


def run_variants(sha: str) -> dict:
    generated = generate_for(sha)
    builds = []
    for name in ("asan", "release"):
        d8 = builds_dir() / name / "d8"
        if d8.is_file():
            builds.append((name, d8))

    results = []
    for g in generated:
        test = tests_dir_for(sha) / g["file"]
        for build_name, d8 in builds:
            r = run_test(d8, test)
            results.append({"variant": g["file"], "title": g["title"], "build": build_name, **r})

    summary = {
        "sha": sha,
        "generated": len(generated),
        "builds": [b[0] for b in builds],
        "ran": time.time(),
        "results": results,
    }
    out_dir = intel_dir() / sha
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "variant-results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    crashes = sum(1 for r in results if r["outcome"] == "crash")
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                'UPDATE intel SET variant_flag = ? WHERE "commit" = ?',
                (1 if crashes or generated else 0, sha),
            )
    finally:
        con.close()
    return summary


def run_variants_cmd(args) -> int:
    sha = getattr(args, "sha", None)
    if not sha:
        con = db.ensure_db()
        try:
            row = con.execute(
                "SELECT \"commit\" FROM intel WHERE review_status = 'reviewed' "
                "ORDER BY created DESC LIMIT 1"
            ).fetchone()
        finally:
            con.close()
        if not row:
            print("variant: không có commit reviewed")
            return 0
        sha = row["commit"]
    summary = run_variants(sha)
    print(
        f"variant {sha[:12]}: generated={summary['generated']} builds={summary['builds']} "
        f"crashes={sum(1 for r in summary['results'] if r['outcome'] == 'crash')}"
    )
    for r in summary["results"]:
        print(f"  {r['build']:<8} {r['variant']:<14} {r['outcome']:<8} rc={r['rc']}")
    return 0
