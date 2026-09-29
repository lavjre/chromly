"""Case runner — opencode persona trong scratch NGOÀI repo (bài học M2-02), §5.6.

Resume ≤8 · wall ≤8h (mặc định) · budget governor (M4-03) chọn model.
VERDICT.md trong scratch → copy về cases/<id>/ → state VERDICT|TIMEOUT.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.case import pipeline
from chromly.orchestrator import budget
from chromly.store import db

CASE_SCRATCH = Path("/tmp/opencode/chromly-case")
MAX_RESUME = 8
MAX_WALL_DEFAULT = 8 * 3600.0
VERDICT_RE = re.compile(r"verdict:\s*(validated-crash|no-bug|needs-human|report-draft)")


def scratch_for(case_id: str) -> Path:
    return CASE_SCRATCH / case_id


def _prepare_scratch(case_id: str) -> Path:
    d = pipeline.case_dir(case_id)
    s = scratch_for(case_id)
    s.mkdir(parents=True, exist_ok=True)
    for f in (
        "repro.js",
        "asan.txt",
        "symbols.txt",
        "triage.md",
        "brief.md",
        "notes.md",
        "meta.json",
    ):
        src = d / f
        if src.is_file():
            shutil.copy2(src, s / f)
    (s / "poc").mkdir(exist_ok=True)
    (s / "lanes").mkdir(exist_ok=True)
    return s


def _mission(case_id: str) -> str:
    s = scratch_for(case_id)
    return f"""\
Bạn là case lead của chromly (persona Nini). Mission: case {case_id}.

Workdir TUYỆT ĐỐI (đọc/ghi mọi thứ ở đây): {s}
V8 source chỉ-đọc: {paths.V8_ROOT} — dùng đường dẫn tuyệt đối khi Grep/Read.
d8: {paths.V8_ROOT}/out/asan/d8 (chính) · {paths.V8_ROOT}/out/calib/d8 (nếu có).

Đọc `{s}/brief.md` và làm theo đúng các bước trong đó. Tóm tắt:
1. Repro ×5 trên asan d8, ghi tỉ lệ thật vào notes.md.
2. Root cause: map frame → source (file:line) → cơ chế.
3. `{s}/notes.md` theo hypothesis | evidence | result.
4. `{s}/VERDICT.md` — dòng đầu: `verdict: validated-crash|no-bug|needs-human|report-draft`.
5. Xong thì DỪNG. Không sửa file ngoài workdir.
"""


def parse_verdict(text: str) -> str | None:
    m = VERDICT_RE.search(text)
    return m.group(1) if m else None


def run_case(
    case_id: str,
    max_wall: float = MAX_WALL_DEFAULT,
    model: str | None = None,
    resume_session: str | None = None,
) -> dict:
    from chromly.case.pipeline import set_state

    # budget
    decision = budget.check_case(est_cost=budget.CAPS["case"], high_score=True)
    if not decision.get("allow"):
        return {"case": case_id, "status": "budget-deny", "detail": decision}
    model = model or decision.get("model") or budget.FLASH_MODEL

    s = _prepare_scratch(case_id)
    set_state(case_id, "RUNNING")
    opencode = shutil.which("opencode")
    if not opencode:
        return {"case": case_id, "status": "no-opencode"}

    cmd = [
        opencode,
        "run",
        "--format",
        "json",
        "--auto",
        "--agent",
        "persona",
        "-m",
        model,
    ]
    if resume_session:
        cmd += ["-s", resume_session]
    cmd += [_mission(case_id)]

    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(cmd, cwd=s, capture_output=True, text=True, timeout=max_wall)
        output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        output = ((exc.stdout or "") + (exc.stderr or "")) if isinstance(exc.stdout, str) else ""
    wall = round(time.monotonic() - t0, 1)

    d = pipeline.case_dir(case_id)
    (d / "agent-output.log").write_text(output)
    for f in ("VERDICT.md", "notes.md"):
        src = s / f
        if src.is_file():
            shutil.copy2(src, d / f)
    for sub in ("poc", "lanes"):
        src = s / sub
        if src.is_dir() and any(src.iterdir()):
            shutil.copytree(src, d / sub, dirs_exist_ok=True)

    verdict_file = d / "VERDICT.md"
    verdict = parse_verdict(verdict_file.read_text()) if verdict_file.is_file() else None
    if verdict:
        state = "VERDICT"
    elif timed_out:
        state = "TIMEOUT"
    elif (d / "HELP.md").is_file():
        state = "HELP"
    else:
        state = "TIMEOUT"

    session = ""
    for line in output.splitlines():
        if "ses_" in line:
            idx = line.find("ses_")
            session = line[idx : idx + 40].split('"')[0].split("\\")[0].strip()
            break

    set_state(case_id, state, verdict=verdict, budget_used=wall)
    from chromly.orchestrator.agents import parse_session_usage

    usage = parse_session_usage(output)
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT INTO runs (case_id, session_id, model, wall_s, outcome, "
                "cost_est, tokens_in, tokens_out) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    case_id,
                    session,
                    model,
                    wall,
                    f"case:{state}:{verdict or 'none'}",
                    usage["cost_est"],
                    usage["tokens_in"],
                    usage["tokens_out"],
                ),
            )
    finally:
        con.close()

    return {
        "case": case_id,
        "status": state.lower(),
        "verdict": verdict,
        "wall_s": wall,
        "session": session,
    }


def run_case_cmd(args: argparse.Namespace) -> int:
    sub = getattr(args, "case_cmd", None)
    if sub == "new":
        meta = pipeline.new_case(args.crash, source=args.source)
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    if sub == "run":
        res = run_case(
            args.case_id,
            max_wall=getattr(args, "wall", 8 * 60) * 60.0,
            resume_session=getattr(args, "resume", None),
        )
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res.get("status") in ("verdict", "timeout") else 1
    if sub == "list":
        for m in pipeline.list_cases():
            print(f"{m['id']}  {m['state']:<10} crash={(m.get('crash_hash') or '-')[:12]}")
        return 0
    if sub == "show":
        meta = pipeline.load_case(args.case_id)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    print("usage: chromly case {new|run|list|show}")
    return 2
