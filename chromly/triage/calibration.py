"""Calibration harness — M3-03: revert-fix ground truth (§5.5).

Mỗi bug (calibration/bugs.json — versioned trong repo):
  {"id","surface","bug_class","difficulty","fix_sha","repro_js","repro_flags"?}

Flow `chromly calibrate --bug <id>`:
  1. guard: V8 tree sạch → sinh patch revert từ mirror (git show fix_sha) → áp ngược vào checkout
  2. build config `calib` (out/calib, asan profile) — dùng build rig
  3. chạy repro trên out/calib/d8 → phải crash (ground truth đứng vững)
  4. classify + score output; ghi store/calibration/<id>/result.json + bảng `calibration`
  5. restore tree (git checkout -- .)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.builds import v8 as buildrig
from chromly.intel.watcher import mirror_dir
from chromly.store import db
from chromly.triage import classify, repro, score


def bugs_path() -> Path:
    return paths.REPO_ROOT / "calibration" / "bugs.json"


def load_bugs() -> list[dict]:
    if not bugs_path().is_file():
        return []
    try:
        return json.loads(bugs_path().read_text())
    except json.JSONDecodeError:
        return []


def calib_dir(bug_id: str) -> Path:
    return paths.STORE_DIR / "calibration" / bug_id


def _git(args: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _tree_clean(root: Path) -> bool:
    rc, out = _git(["status", "--porcelain"], root)
    return rc == 0 and out == ""


def calibrate(bug: dict) -> dict:
    v8 = paths.V8_ROOT
    bug_id = bug["id"]
    out_dir = calib_dir(bug_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not _tree_clean(v8):
        return {"id": bug_id, "status": "tree-dirty"}

    # 1. revert patch từ mirror
    mirror = mirror_dir()
    if not (mirror / ".git").is_dir():
        return {"id": bug_id, "status": "no-mirror"}
    rc, patch = _git(["show", bug["fix_sha"]], mirror)
    if rc != 0:
        return {"id": bug_id, "status": "fix-sha-missing"}
    patch_file = out_dir / "revert.patch"
    patch_file.write_text(patch + "\n")  # _git strip()→ thiếu newline cuối = "corrupt patch"
    rc, out = _git(["apply", "-R", str(patch_file)], v8)
    if rc != 0:
        # Fix thường kèm test file mới (không tồn tại trong checkout) → hunk tạo file
        # không reverse-apply được. Thử lại chỉ revert phần src (bỏ test/status).
        rc2, out2 = _git(
            ["apply", "-R", "--exclude=test/*", "--exclude=*mjsunit.status", str(patch_file)], v8
        )
        if rc2 == 0:
            rc, out = rc2, out2
    revert_applied = rc == 0
    if not revert_applied:
        # Fix có thể MỚI hơn checkout (bug đang hiện diện trong cây) — tiếp tục không revert.
        (out_dir / "revert-note.txt").write_text(out[-1000:])
    try:
        # 2. build out/calib
        rc = buildrig.run_build("calib")
        if rc != 0:
            return {"id": bug_id, "status": "build-failed"}

        # 3. repro trên build calib
        d8 = v8 / "out" / "calib" / "d8"
        repro_js = out_dir / "repro.js"
        repro_js.write_text(bug["repro_js"])
        flags = bug.get("repro_flags", [])
        res = repro.repro_run(
            d8, repro_js, runs=5, extra_flags=flags, timeout=int(bug.get("repro_timeout", 60))
        )
        (out_dir / "repro.out").write_text(res["output"])

        fault = classify.classify_text(res["output"])
        sc = score.score(fault, res["output"])
        status = "ok" if res["crashed"] >= 1 else "no-crash"

        result = {
            "id": bug_id,
            "status": status,
            "crashed": f"{res['crashed']}/{res['of']}",
            "revert_applied": revert_applied,
            "class": fault["class"],
            "score": sc["score"],
            "surface": bug.get("surface"),
            "bug_class": bug.get("bug_class"),
            "fix_sha": bug["fix_sha"],
            "ts": time.time(),
        }
        (out_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

        con = db.ensure_db()
        try:
            with con:
                con.execute(
                    "INSERT INTO calibration (bug, surface, bug_class, difficulty, "
                    "coverage_note, last_fail) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        bug_id,
                        bug.get("surface"),
                        bug.get("bug_class"),
                        bug.get("difficulty"),
                        f"crashed={res['crashed']}/{res['of']} class={fault['class']}",
                        None if status == "ok" else str(time.time()),
                    ),
                )
        finally:
            con.close()
        return result
    finally:
        # 5. restore tree (chỉ khi đã revert)
        if revert_applied:
            _git(["checkout", "--", "."], v8)


def run_calibrate_cmd(args: argparse.Namespace) -> int:
    bugs = load_bugs()
    if getattr(args, "list", False) or not bugs:
        if not bugs:
            print("calibration: bugs.json trống — thêm bug đầu tiên vào calibration/bugs.json")
            return 0
        for b in bugs:
            b_id = b["id"]
            b_surface = b.get("surface", "?")
            b_class = b.get("bug_class", "?")
            print(f"{b_id:<12} {b_surface:<10} {b_class:<20} {b['fix_sha'][:12]}")
        return 0
    bug_id = getattr(args, "bug", None)
    target = [b for b in bugs if b["id"] == bug_id] if bug_id else bugs[:1]
    if not target:
        print(f"calibration: không thấy bug {bug_id}")
        return 1
    result = calibrate(target[0])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1
