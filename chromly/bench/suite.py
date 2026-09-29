"""Bench suite — M4-05 (§8): T3/T4 deterministic v0 + T1 runner (agent) + CI gate.

- T3 triage classify: 20 fixture đã label → accuracy + score order (deterministic, chấm bằng code).
- T4 harness sanity: repro pipeline trên crash fixture (deterministic).
- T1 root-cause: agent analyst trên calibration bug (runner có; chạy tốn LLM — mặc định queue).
- T2 diff review: chấm review đã có (variants.json của M2) — runner để dần.
Ghi `bench_runs` + bench/latest.md. Prompt CI gate: primary metric (T3 accuracy) không giảm >2%.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from chromly import paths
from chromly.store import db
from chromly.triage import classify, repro, score

BENCH_DIR = paths.BENCH_DIR
GATE_DROP = 0.02


def _t3_cases() -> list[tuple[str, str, bool]]:
    """(text, expected_class, expected_fp) — 20 case deterministic."""
    cases = []
    for i in range(4):
        cases.append(
            (
                f"=={i}==ERROR: AddressSanitizer: heap-buffer-overflow\nWRITE of size 8\n",
                "heap-buffer-overflow",
                False,
            )
        )
    for i in range(4):
        cases.append(
            (
                f"=={i}==ERROR: AddressSanitizer: heap-buffer-overflow\nREAD of size 4\n",
                "heap-buffer-overflow",
                False,
            )
        )
    for i in range(4):
        cases.append(
            (
                f"=={i}==ERROR: AddressSanitizer: heap-use-after-free\nREAD of size 4\n",
                "use-after-free",
                False,
            )
        )
    cases.append(
        ("ERROR: AddressSanitizer: stack-buffer-overflow\n", "stack-buffer-overflow", False)
    )
    cases.append(
        (
            "Fatal error in ../../src/objects/map.cc\nCheck failed: x.IsMap()\n",
            "type-confusion-dcheck",
            False,
        )
    )
    cases.append(
        ("Fatal error in ../../src/objects/foo.cc\nCheck failed: a == b\n", "dcheck-fail", False)
    )
    for i in range(3):
        cases.append((f"(timeout) {i}", "timeout", True))
    cases.append(("Fatal process out of memory: heap allocation failed", "oom", True))
    cases.append(("Uncaught Error: fixture", "other", True))
    return cases


def t3() -> dict:
    cases = _t3_cases()
    correct = 0
    fp_correct = 0
    for text, expected_cls, expected_fp in cases:
        got = classify.classify_text(text)
        if got["class"] == expected_cls:
            correct += 1
        if classify.is_false_positive(got["class"]) == expected_fp:
            fp_correct += 1
    # score order: write > read > dcheck
    w = score.score({"class": "heap-buffer-overflow", "access": {"kind": "write"}}, "")
    r = score.score({"class": "heap-buffer-overflow", "access": {"kind": "read"}}, "")
    order_ok = w["score"] > r["score"]
    return {
        "n": len(cases),
        "accuracy": correct / len(cases),
        "fp_accuracy": fp_correct / len(cases),
        "score_order_ok": order_ok,
    }


def t4() -> dict:
    """Harness sanity: fixture crash → repro pipeline 5/5."""
    d = paths.STORE_DIR / "bench"
    d.mkdir(parents=True, exist_ok=True)
    fixture = d / "t4_fixture.js"
    fixture.write_text('throw new Error("bench-t4");\n')
    d8 = paths.V8_ROOT / "out" / "asan" / "d8"
    if not d8.is_file():
        return {"pass": False, "reason": "thiếu out/asan/d8"}
    res = repro.repro_run(d8, fixture, runs=3, extra_flags=["--abort-on-uncaught-exception"])
    return {"pass": res["crashed"] == 3, "crashed": res["crashed"], "of": res["of"]}


def config_hash() -> str:
    h = hashlib.sha256()
    for f in (paths.REPO_ROOT / "runtime" / "persona.txt",):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


T1_REQUIRED = ["peel", "phi"]  # ground truth calib-567177599: loop-peeling mất phi type


def t1_run(bug_id: str = "calib-567177599") -> dict:
    """Chạy agent analyst trên calibration bug → chấm keyword root-cause (v0)."""
    import subprocess as _sp

    from chromly.orchestrator.agents import parse_session_usage

    bugs = json.loads((paths.REPO_ROOT / "calibration" / "bugs.json").read_text())
    bug = next((b for b in bugs if b["id"] == bug_id), None)
    if bug is None:
        return {"status": "no-bug"}

    scratch = Path("/tmp/opencode/chromly-bench") / f"t1-{int(time.time())}"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "repro.js").write_text(bug["repro_js"])
    flags = " ".join(bug.get("repro_flags", []))
    d8 = paths.V8_ROOT / "out" / "asan" / "d8"
    prompt = (
        f"You are the analyst lane of chromly. WORKDIR (absolute): {scratch}\n"
        f"Repro: {scratch}/repro.js.\n"
        f"d8: {d8} (chạy: {d8} --allow-natives-syntax {flags} repro.js).\n"
        "Nhiệm vụ: tìm ROOT CAUSE của crash/non-determinism này trong V8 (source tại "
        f"{paths.V8_ROOT}). Viết `{scratch}/root_cause.md` với: bug class · root cause "
        "(file:line + cơ chế) · cách verify. Xong thì DỪNG."
    )
    from chromly.orchestrator.agents import find_opencode

    opencode = find_opencode()
    if not opencode:
        return {"status": "no-opencode"}
    t0 = time.monotonic()
    try:
        proc = _sp.run(
            [
                opencode,
                "run",
                "--format",
                "json",
                "--auto",
                "--agent",
                "analyst",
                "-m",
                "opencode-go/deepseek-v4.1-flash",
                prompt,
            ],
            cwd=scratch,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        output = proc.stdout + "\n" + proc.stderr
    except _sp.TimeoutExpired:
        output = "(timeout)"
    wall = round(time.monotonic() - t0, 1)
    rc_file = scratch / "root_cause.md"
    text = output + "\n" + (rc_file.read_text() if rc_file.is_file() else "")
    hits = [k for k in T1_REQUIRED if k.lower() in text.lower()]
    usage = parse_session_usage(output)
    return {
        "status": "done",
        "accuracy": 1 if len(hits) == len(T1_REQUIRED) else 0,
        "hits": hits,
        "wall_s": wall,
        "cost_est": usage["cost_est"],
        "scratch": str(scratch),
    }


def run_suite(suite: str, run_t1: bool = False) -> dict:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    metrics: dict = {}
    if suite in ("ci", "t3"):
        metrics["t3"] = t3()
    if suite in ("ci", "t4"):
        metrics["t4"] = t4()
    if suite in ("ci", "t1"):
        if run_t1 or suite == "t1":
            metrics["t1"] = t1_run()
        else:
            metrics["t1"] = {"status": "queued", "note": "cần --run (LLM run)"}
    if suite in ("ci", "t2"):
        metrics["t2"] = {"status": "queued", "note": "agent diff review — dần ở v0"}

    # gate: so với lần chạy trước (T3 accuracy)
    con = db.ensure_db()
    prev = None
    try:
        row = con.execute(
            "SELECT metrics_json FROM bench_runs WHERE suite = ? ORDER BY id DESC LIMIT 1", (suite,)
        ).fetchone()
        if row:
            prev = json.loads(row["metrics_json"])
        with con:
            con.execute(
                "INSERT INTO bench_runs (suite, config_hash, metrics_json, started, finished) "
                "VALUES (?, ?, ?, ?, ?)",
                (suite, config_hash(), json.dumps(metrics, ensure_ascii=False), started, None),
            )
    finally:
        con.close()

    gate = {"pass": True, "delta": 0.0}
    if prev and "t3" in prev and "t3" in metrics:
        delta = metrics["t3"]["accuracy"] - prev["t3"]["accuracy"]
        gate["delta"] = delta
        gate["pass"] = delta >= -GATE_DROP
        gate["note"] = f"T3 accuracy delta {delta:+.1%} (gate ≥ -2%)"

    report = BENCH_DIR / "latest.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Bench {suite} — {started}", ""]
    for k, v in metrics.items():
        lines.append(f"- {k}: `{json.dumps(v, ensure_ascii=False)}`")
    lines.append(f"- gate: {json.dumps(gate, ensure_ascii=False)}")
    report.write_text("\n".join(lines) + "\n")
    return {"suite": suite, "metrics": metrics, "gate": gate, "report": str(report)}


def run_bench_cmd(args: argparse.Namespace) -> int:
    suite = getattr(args, "suite", "ci")
    res = run_suite(suite, run_t1=getattr(args, "run", False))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["gate"]["pass"] else 1
