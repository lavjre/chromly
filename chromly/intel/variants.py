"""Variant test runner — M2-03: variants.json → test JS + chạy trên d8 builds.

- generate: mỗi variant có `test_js` → `tests/INTEL-<sha12>/variant-N.js` (kèm header comment).
- run: chạy từng test trên `out/asan/d8` (+ `out/release/d8` nếu có) — timeout 60s,
  outcome: crash | flag-conflict | oom | error | ok | timeout. Kết quả ghi results.json
  + DB intel.variant_flag.
- crash → crash store row (source='variant', score 5, triaged) → auto-case pipeline bắt.
- flag-conflict: d8 abort vì cờ xung đột build (readonly flag, vd --verify-turboshaft) —
  test không chạy được, KHÔNG phải crash (FP filter).
- run_pending_variants: quét reviewed commits chưa chạy (chỉ V8-runnable) — dùng sau review.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.intel.watcher import intel_dir
from chromly.store import db

TIMEOUT_S = 60
CRASH_CODES = {134, 135, 136, 137, 138, 139}
OOM_MARKERS = (
    "Fatal JavaScript out of memory",
    "CALL_AND_RETRY_LAST",
    "Fatal process out of memory",
)
# d8 abort khi cờ xung đột build (DEFINE_BOOL_READONLY) — test không chạy được,
# không phải lỗi của V8. Vd: variant hypothesis cần --verify-turboshaft nhưng build
# tắt cứng (is_debug=false) → "Contradictory value for readonly flag".
FLAG_CONFLICT_MARKERS = (
    "Flag processing error",
    "Contradictory value for readonly flag",
)


def _extract_run_flags(test: Path) -> list[str]:
    """Đọc flags gợi ý từ header test (`// run: d8 ... --flag` hoặc `// flags: --flag`)."""
    try:
        lines = test.read_text(errors="replace").splitlines()[:12]
    except OSError:
        return []
    for line in lines:
        low = line.strip()
        if low.startswith("// run:") or low.startswith("// flags:"):
            return [
                tok
                for tok in low.split()
                if tok.startswith("--") and tok != "--allow-natives-syntax"
            ]
    return []


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
    extra_flags = _extract_run_flags(test)
    try:
        proc = subprocess.run(
            [str(d8), "--allow-natives-syntax", *extra_flags, str(test)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
        rc = proc.returncode
        full = proc.stdout + proc.stderr
        output = full[-2000:]
        if any(m in full for m in OOM_MARKERS):
            outcome = "oom"  # test tự ép OOM → không phải crash (FP filter §5.4)
        elif any(m in full for m in FLAG_CONFLICT_MARKERS):
            outcome = "flag-conflict"  # cờ xung đột build → không chạy được (FP filter)
        elif rc in CRASH_CODES or rc < 0:
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
    for r in results:
        if r["outcome"] == "crash":
            _file_variant_crash(sha, r)
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


def _file_variant_crash(sha: str, result: dict) -> None:
    """Variant crash → crash store (source='variant') để auto-case pipeline bắt."""
    test = tests_dir_for(sha) / result["variant"]
    if not test.is_file():
        return
    data = test.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    art = paths.STORE_DIR / "crashes" / h
    art.mkdir(parents=True, exist_ok=True)
    shutil.copy2(test, art / f"program_{sha[:12]}_{result['variant']}")
    (art / "meta.json").write_text(
        json.dumps(
            {"hash": h, "unit": "variant", "orig_path": str(test), "created": time.time()},
            indent=2,
        )
    )
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT OR IGNORE INTO crashes (hash, fault_type, severity, build_rev, "
                "source, state) VALUES (?, 'variant-crash', 5, ?, 'variant', 'triaged')",
                (h, sha[:12]),
            )
    finally:
        con.close()
    print(f"[variants] CRASH → store/crashes/{h[:12]} (từ {sha[:12]})", flush=True)


def run_pending_variants(limit: int = 5) -> list[dict]:
    """Chạy variants cho reviewed commits chưa có kết quả (chỉ V8-runnable: paths src/ hoặc v8/)."""
    con = db.ensure_db()
    try:
        rows = con.execute(
            'SELECT "commit", paths FROM intel '
            "WHERE review_status = 'reviewed' AND variant_flag = 1"
        ).fetchall()
    finally:
        con.close()
    out: list[dict] = []
    for r in rows:
        if len(out) >= limit:
            break
        sha = r["commit"]
        d = intel_dir() / sha
        if (d / "variant-results.json").is_file():
            continue
        try:
            changed = json.loads(r["paths"] or "[]")
        except json.JSONDecodeError:
            changed = []
        if not any(p.startswith(("src/", "v8/")) for p in changed):
            continue  # chromium-only (Blink/Mojo...) — cần Chrome lab (M5+)
        out.append(run_variants(sha))
    return out


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
