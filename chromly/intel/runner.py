"""Agent intel runner — M2-02: review commit qua opencode agent `intel` (§5.3).

Mỗi commit pending: workdir store/intel/<sha>/ (commit.diff + meta.json) →
`opencode run --agent intel` (persona + skill patch-diff-review) → review.md + variants.json →
update DB (reviewed/failed, variant_flag). Run ghi vào bảng `runs` (wall, outcome, session).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from chromly.intel.watcher import intel_dir
from chromly.store import db

MODEL = "opencode-go/deepseek-v4.1-flash"

# Session opencode bám theo git root của cwd → phải chạy agent trong scratch NGOÀI repo,
# rồi copy artifacts về store/intel/<sha>/ (archive). Xem sự cố 2026-09-29 (agent lạc dir).
SCRATCH_ROOT = Path("/tmp/opencode/chromly-intel")

PROMPT = """\
Bạn là intel lane của chromly (PLAN §5.3). WORKDIR TUYỆT ĐỐI: {workdir}
Chỉ đọc/ghi trong workdir này bằng đường dẫn tuyệt đối. Không dạo các thư mục khác.

1. Đọc `{workdir}/meta.json` (commit + paths) và `{workdir}/commit.diff`.
2. Load skill `patch-diff-review` (skill tool, id: patch-diff-review) và làm theo.
3. Viết `{workdir}/review.md` (tiếng Việt) đúng 3 phần: **Fix gì** · **Bug gì** (suy ngược từ fix) ·
   **Variant còn sống** (3 câu hỏi: cùng hàm / sibling / cùng pattern) + độ tin từng variant.
4. Ghi `{workdir}/variants.json` — mảng JSON, mỗi phần tử:
   {{"title": "...", "confidence": "high|med|low",
    "test_idea": "mô tả ngắn", "test_js": "<JS chạy standalone trên d8>"}}
   - `test_js`: code JS tối thiểu để kiểm chứng hypothesis, chạy được bằng
     `d8 --allow-natives-syntax file.js` (để trống "" nếu chưa viết được).
   - Chỉ ghi variant có cơ sở từ diff. Không có variant thì ghi [].
5. Xong thì DỪNG. Không sửa file khác, không cài gì.
"""


def pending_commits(limit: int = 5, sha: str | None = None) -> list[dict]:
    con = db.ensure_db()
    try:
        if sha:
            rows = con.execute(
                'SELECT "commit", paths FROM intel WHERE "commit" = ?', (sha,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT \"commit\", paths FROM intel WHERE review_status = 'pending' "
                "ORDER BY created DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        con.close()
    return [{"sha": r["commit"], "paths": r["paths"]} for r in rows]


def run_review(sha: str) -> dict:
    archive = intel_dir() / sha
    if not (archive / "commit.diff").is_file():
        return {"sha": sha, "status": "no-diff"}

    opencode = shutil.which("opencode")
    if not opencode:
        return {"sha": sha, "status": "no-opencode"}

    # Scratch ngoài repo — session opencode không lạc về git root
    scratch = SCRATCH_ROOT / sha
    scratch.mkdir(parents=True, exist_ok=True)
    for name in ("commit.diff", "meta.json"):
        src = archive / name
        if src.is_file():
            shutil.copy2(src, scratch / name)
    prompt = PROMPT.format(workdir=scratch)

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [
                opencode,
                "run",
                "--format",
                "json",
                "--auto",
                "--agent",
                "intel",
                "-m",
                MODEL,
                prompt,
            ],
            cwd=scratch,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        output = "(timeout 1800s)"
    wall = round(time.monotonic() - t0, 1)
    (archive / "agent-output.log").write_text(output)

    # copy artifacts về archive
    for name in ("review.md", "variants.json"):
        src = scratch / name
        if src.is_file():
            shutil.copy2(src, archive / name)

    review = archive / "review.md"
    variants = archive / "variants.json"
    variant_count = 0
    if variants.is_file():
        try:
            variant_count = len(json.loads(variants.read_text()))
        except json.JSONDecodeError:
            variant_count = 0

    ok = review.is_file() and review.stat().st_size > 0
    status = "reviewed" if ok else "failed"
    session = ""
    for line in output.splitlines():
        if "ses_" in line:
            idx = line.find("ses_")
            session = line[idx : idx + 40].split('"')[0].split("\\")[0].strip()
            break

    con = db.ensure_db()
    try:
        with con:
            con.execute(
                'UPDATE intel SET review_status = ?, variant_flag = ? WHERE "commit" = ?',
                (status, 1 if variant_count else 0, sha),
            )
            from chromly.orchestrator.agents import parse_session_usage

            usage = parse_session_usage(output)
            con.execute(
                "INSERT INTO runs (session_id, model, cost_est, wall_s, outcome, "
                "tokens_in, tokens_out) VALUES (?,?,?,?,?,?,?)",
                (
                    session,
                    MODEL,
                    usage["cost_est"],
                    wall,
                    f"intel:{status}",
                    usage["tokens_in"],
                    usage["tokens_out"],
                ),
            )
    finally:
        con.close()

    return {
        "sha": sha[:12],
        "status": status,
        "wall_s": wall,
        "variants": variant_count,
        "session": session,
    }


def _review_batch(limit: int, sha: str | None) -> int:
    from chromly.orchestrator.budget import tier

    t = tier()
    if t in ("day-cap", "exhausted"):
        print(f"[{time.strftime('%H:%M:%S')}] budget {t} — skip review tick", flush=True)
        return 0
    targets = pending_commits(limit=limit, sha=sha)
    if not targets:
        print(f"[{time.strftime('%H:%M:%S')}] review: 0 pending", flush=True)
        return 0
    failed = 0
    for tgt in targets:
        res = run_review(tgt["sha"])
        print(json.dumps(res, ensure_ascii=False), flush=True)
        if res.get("status") not in ("reviewed",):
            failed += 1
    return 1 if failed else 0


def run_intel_review(
    limit: int = 5, sha: str | None = None, loop: bool = False, interval: float = 7200.0
) -> int:
    """Review commit pending. loop=True: chạy mãi mỗi `interval` giây (aux supervisor)."""
    while True:
        failed = _review_batch(limit=limit, sha=sha)
        if not loop or sha:
            return failed
        time.sleep(interval)


def add_review_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--sha", default=None, help="review đúng 1 commit")
