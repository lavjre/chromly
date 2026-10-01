"""Case runner — opencode persona trong scratch NGOÀI repo (bài học M2-02), §5.6.

Resume ≤8 · wall ≤8h (mặc định) · budget governor (M4-03) chọn model.
VERDICT.md trong scratch → copy về cases/<id>/ → state VERDICT|TIMEOUT.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
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
MAX_WALL_DEFAULT = 6 * 3600.0  # plan §10.2: case process >6h coi là leak
HIGH_SCORE_MIN = 5  # thang severity thực: variant=5, validate bump=7
VERDICT_RE = re.compile(r"verdict:\s*(validated-crash|no-bug|needs-human|report-draft)")
RUNNER_FILE = "runner.json"  # {pid, started} — phát hiện runner chết giữa case
RUNNER_STALE_S = 600.0  # không có runner.json + meta cũ hơn ngưỡng → reclaim


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
    count_resume: bool = False,
) -> dict:
    from chromly.case.pipeline import set_state

    # budget — high_score lấy thật từ severity của crash gắn case (không hardcode)
    high = _case_high_score(case_id)
    decision = budget.check_case(est_cost=budget.CAPS["case"], high_score=high)
    if not decision.get("allow"):
        return {"case": case_id, "status": "budget-deny", "detail": decision}
    model = model or decision.get("model") or budget.FLASH_MODEL

    from chromly.orchestrator.agents import find_opencode

    opencode = find_opencode()
    if not opencode:
        return {"case": case_id, "status": "no-opencode"}  # chưa RUNNING — không kẹt

    if resume_session or count_resume:
        meta = pipeline.load_case(case_id)
        if int(meta.get("resumes", 0)) >= MAX_RESUME:
            return {"case": case_id, "status": "resume-cap", "resumes": meta.get("resumes", 0)}

    s = _prepare_scratch(case_id)
    set_state(case_id, "RUNNING")
    # dấu runner sống — reclaim nhanh nếu process này chết giữa case (xem stale_running_case)
    rf = pipeline.case_dir(case_id) / RUNNER_FILE
    rf.write_text(json.dumps({"pid": os.getpid(), "started": time.time(), "case": case_id}))
    try:
        return _run_case_inner(case_id, s, opencode, model, max_wall, resume_session, count_resume)
    except Exception as exc:  # noqa: BLE001 — không bao giờ để case kẹt RUNNING
        with contextlib.suppress(Exception):
            set_state(case_id, "ERROR")
        return {"case": case_id, "status": "error", "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        with contextlib.suppress(OSError):
            rf.unlink()


def _runner_alive(pid: int) -> bool:
    """pid còn sống VÀ vẫn thuộc chromly (chống pid reuse)."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        cmdline = (
            Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        )
    except OSError:
        return False
    return "chromly" in cmdline


def stale_running_case(now: float | None = None) -> str | None:
    """Case RUNNING nhưng runner không còn sống → trả id để reclaim (TIMEOUT rồi resume).

    Vì sao cần: 2026-10-01 CASE-0004 — aux loop `case auto` chết giữa case, state kẹt
    RUNNING; `_case_running()` chặn mọi auto-case mới tới tận hạn reap 6.5h của watchdog.
    """
    now = now if now is not None else time.time()
    con = db.ensure_db()
    try:
        rows = con.execute("SELECT id FROM cases WHERE state = 'RUNNING'").fetchall()
    finally:
        con.close()
    for r in rows:
        cid = r["id"]
        try:
            d = pipeline.case_dir(cid)
            rf = d / RUNNER_FILE
            if rf.is_file():
                try:
                    rec = json.loads(rf.read_text())
                except json.JSONDecodeError:
                    rec = {}
                if _runner_alive(int(rec.get("pid") or 0)):
                    continue
                return cid
            # legacy (runner chưa kịp ghi file): chỉ reclaim khi meta đã cũ
            mp = d / "meta.json"
            if mp.is_file() and now - mp.stat().st_mtime > RUNNER_STALE_S:
                return cid
        except OSError:
            continue
    return None


def reclaim_stale_running() -> str | None:
    """Đánh TIMEOUT cho case RUNNING có runner đã chết (để vòng sau resume)."""
    cid = stale_running_case()
    if cid is None:
        return None
    pipeline.set_state(cid, "TIMEOUT")
    with contextlib.suppress(Exception):
        from chromly.fuzz import watchdog

        watchdog.append_event("case-reclaim", cid, {"reason": "runner-dead"})
    print(f"[auto] reclaim {cid}: runner chết → TIMEOUT (sẽ resume lượt sau)", flush=True)
    return cid


def _acquire_auto_lock():
    """flock không-blocking — chặn 2 instance `case auto` chạy song song (nguồn kẹt case)."""
    lock_path = paths.STORE_DIR / "fuzz" / "case-auto.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def _mark_crash_fp(case_id: str) -> None:
    """Verdict no-bug → đánh dấu crash gắn case = 'fp' (không re-case, báo cáo đúng)."""
    mp = pipeline.case_dir(case_id) / "meta.json"
    try:
        crash_hash = json.loads(mp.read_text()).get("crash_hash")
    except (OSError, json.JSONDecodeError):
        return
    if not crash_hash:
        return
    con = db.ensure_db()
    try:
        with con:
            con.execute("UPDATE crashes SET state = 'fp' WHERE hash = ?", (crash_hash,))
    finally:
        con.close()


def _case_high_score(case_id: str) -> bool:
    """True nếu case gắn crash severity >= HIGH_SCORE_MIN (điều kiện budget day-cap)."""
    mp = pipeline.case_dir(case_id) / "meta.json"
    if not mp.is_file():
        return False
    try:
        crash_hash = json.loads(mp.read_text()).get("crash_hash")
    except json.JSONDecodeError:
        return False
    if not crash_hash:
        return False
    con = db.ensure_db()
    try:
        row = con.execute(
            "SELECT severity FROM crashes WHERE hash LIKE ?", (f"{crash_hash[:12]}%",)
        ).fetchone()
    finally:
        con.close()
    return row is not None and (row["severity"] or 0) >= HIGH_SCORE_MIN


def _run_case_inner(
    case_id: str,
    s: Path,
    opencode: str,
    model: str,
    max_wall: float,
    resume_session: str | None,
    count_resume: bool = False,
) -> dict:
    from chromly.case.pipeline import set_state

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
    for f in ("VERDICT.md", "notes.md", "HELP.md"):
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
    elif (d / "HELP.md").is_file():
        state = "HELP"  # agent cần người — kể cả khi run chạm wall (HELP thắng TIMEOUT)
    elif timed_out:
        state = "TIMEOUT"
    else:
        state = "TIMEOUT"

    session = ""
    for line in output.splitlines():
        if "ses_" in line:
            idx = line.find("ses_")
            session = line[idx : idx + 40].split('"')[0].split("\\")[0].strip()
            break

    set_state(case_id, state, verdict=verdict, budget_used=wall)
    if verdict == "no-bug":
        _mark_crash_fp(case_id)
    if resume_session or count_resume:
        meta = pipeline.load_case(case_id)
        meta["resumes"] = int(meta.get("resumes", 0)) + 1
        (pipeline.case_dir(case_id) / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2)
        )
    from chromly.orchestrator.agents import parse_session_usage
    from chromly.telemetry import registry

    usage = parse_session_usage(output)
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT INTO runs (case_id, session_id, model, prompt_hash, wall_s, outcome, "
                "cost_est, tokens_in, tokens_out) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    case_id,
                    session,
                    model,
                    registry.persona_hash(),
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


AUTO_THRESHOLD = 4
AUTO_SKIP_SOURCES = ("fixture", "acceptance")


def _case_running() -> bool:
    con = db.ensure_db()
    try:
        n = con.execute("SELECT COUNT(*) AS n FROM cases WHERE state = 'RUNNING'").fetchone()["n"]
    finally:
        con.close()
    return n > 0


def _auto_candidate(threshold: int = AUTO_THRESHOLD) -> dict | None:
    """Crash triaged đủ điểm, chưa có case, và không trùng stack_norm với crash đã-có-case."""
    con = db.ensure_db()
    try:
        if _case_running():
            return None
        row = con.execute(
            "SELECT c.hash FROM crashes c LEFT JOIN cases k ON k.crash_id = c.id "
            "WHERE c.state = 'triaged' AND c.severity >= ? AND k.id IS NULL "
            "AND COALESCE(c.source, '') NOT IN (?, ?) "
            "AND (c.stack_norm IS NULL OR NOT EXISTS ("
            "  SELECT 1 FROM crashes c2 JOIN cases k2 ON k2.crash_id = c2.id "
            "  WHERE c2.stack_norm = c.stack_norm AND c2.id != c.id)) "
            "ORDER BY c.severity DESC, c.id DESC LIMIT 1",
            (threshold, *AUTO_SKIP_SOURCES),
        ).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def auto_case_tick(threshold: int = AUTO_THRESHOLD) -> str | None:
    """Tìm crash triaged score ≥ ngưỡng chưa có case → tạo + chạy (budget-gated trong run_case)."""
    row = _auto_candidate(threshold)
    if row is None:
        return None
    meta = pipeline.new_case(row["hash"][:12], source="auto")
    print(
        f"[auto] case {meta['id']} ← crash {row['hash'][:12]} (score ≥{threshold})",
        flush=True,
    )
    res = run_case(meta["id"])
    print(
        f"[auto] {meta['id']} → {res.get('status')} verdict={res.get('verdict')}",
        flush=True,
    )
    return meta["id"]


def pick_resume_case() -> tuple[str, str | None] | None:
    """(case_id, session_id|None) cho case TIMEOUT còn lượt resume (< MAX_RESUME).

    session None = chưa có runs row (runner chết trước khi đăng ký) → resume mới hoàn toàn.
    """
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT id FROM cases WHERE state = 'TIMEOUT' ORDER BY rowid DESC LIMIT 20"
        ).fetchall()
        for r in rows:
            try:
                meta = pipeline.load_case(r["id"])
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if int(meta.get("resumes", 0)) >= MAX_RESUME:
                continue
            sess = con.execute(
                "SELECT session_id FROM runs WHERE case_id = ? AND session_id != '' "
                "ORDER BY id DESC LIMIT 1",
                (r["id"],),
            ).fetchone()
            return r["id"], (sess["session_id"] if sess else None)
    finally:
        con.close()
    return None


def auto_resume_tick() -> str | None:
    """Case TIMEOUT còn lượt → chạy tiếp (session cũ nếu có; cap MAX_RESUME trong run_case)."""
    if _case_running():
        return None
    pick = pick_resume_case()
    if pick is None:
        return None
    case_id, session = pick
    print(f"[auto] resume {case_id} (session {(session or 'new')[:16]})", flush=True)
    res = run_case(case_id, resume_session=session, count_resume=True)
    print(f"[auto] {case_id} → {res.get('status')} verdict={res.get('verdict')}", flush=True)
    return case_id


def run_case_auto(interval: float = 900.0) -> int:
    """Aux loop: reclaim case kẹt → quét candidate mới → resume (1/lúc, flock chống trùng)."""
    lock = None
    while True:
        if lock is None:
            lock = _acquire_auto_lock()
        if lock is None:
            print(
                f"[{time.strftime('%H:%M:%S')}] auto-case: instance khác giữ lock — idle",
                flush=True,
            )
            time.sleep(interval)
            continue
        try:
            reclaimed = reclaim_stale_running()
            cid = auto_case_tick()
            if cid is None:
                cid = auto_resume_tick()
            if cid is None and reclaimed is None:
                print(f"[{time.strftime('%H:%M:%S')}] auto-case: 0 candidate", flush=True)
        except Exception as exc:  # noqa: BLE001 — loop dài hạn
            print(
                f"[{time.strftime('%H:%M:%S')}] auto-case lỗi: {type(exc).__name__}: {exc}",
                flush=True,
            )
        time.sleep(interval)


def run_case_cmd(args: argparse.Namespace) -> int:
    sub = getattr(args, "case_cmd", None)
    if sub == "new":
        meta = pipeline.new_case(args.crash, source=args.source)
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    if sub == "run":
        wall_arg = getattr(args, "wall", None)
        res = run_case(
            args.case_id,
            max_wall=wall_arg * 60.0 if wall_arg else MAX_WALL_DEFAULT,
            resume_session=getattr(args, "resume", None),
        )
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res.get("status") in ("verdict", "timeout") else 1
    if sub == "archive":
        res = pipeline.archive_case(args.case_id)
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res.get("status") in ("archived", "already") else 1
    if sub == "list":
        for m in pipeline.list_cases():
            print(f"{m['id']}  {m['state']:<10} crash={(m.get('crash_hash') or '-')[:12]}")
        return 0
    if sub == "show":
        meta = pipeline.load_case(args.case_id)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    if sub == "auto":
        return run_case_auto(interval=getattr(args, "interval", 900.0))
    print("usage: chromly case {new|run|archive|list|show|auto}")
    return 2
