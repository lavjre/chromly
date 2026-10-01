"""Case pipeline — M4-01 (§5.6): NEW → BUNDLED → RUNNING → VERDICT|HELP|TIMEOUT → ARCHIVED.

Case dir chuẩn: cases/CASE-xxxx/{triage.md, brief.md, repro.js, asan.txt, symbols.txt,
notes.md, poc/, lanes/, VERDICT.md, log.jsonl, meta.json} (gitignored — runtime data).
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from chromly import paths
from chromly.store import db

TRIAGE_FILES = ("repro.js", "asan.txt", "symbols.txt")


def cases_dir() -> Path:
    return paths.CASES_DIR


def case_dir(case_id: str) -> Path:
    return cases_dir() / case_id


def _next_id() -> str:
    """max(suffix) + 1 — không trùng khi có gap (xoá case giữa dãy)."""
    n = 0
    if cases_dir().is_dir():
        for d in cases_dir().iterdir():
            m = re.match(r"CASE-(\d+)$", d.name)
            if m and d.is_dir():
                n = max(n, int(m.group(1)))
    return f"CASE-{n + 1:04d}"


def log_event(case_id: str, event: str, detail: dict | None = None) -> None:
    d = case_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    with (d / "log.jsonl").open("a") as fh:
        fh.write(
            json.dumps({"ts": time.time(), "event": event, **(detail or {})}, ensure_ascii=False)
            + "\n"
        )


def new_case(crash_hash: str | None = None, source: str = "manual") -> dict:
    """Tạo case từ crash (hash prefix) hoặc rỗng. Trả case meta."""
    cid = _next_id()
    d = case_dir(cid)
    for sub in (d, d / "poc", d / "lanes"):
        sub.mkdir(parents=True, exist_ok=True)

    crash = None
    if crash_hash:
        con = db.ensure_db()
        try:
            row = con.execute(
                "SELECT * FROM crashes WHERE hash LIKE ? LIMIT 1", (f"{crash_hash}%",)
            ).fetchone()
        finally:
            con.close()
        if row is None:
            raise ValueError(f"không thấy crash {crash_hash}")
        crash = dict(row)
        src = paths.STORE_DIR / "triage" / crash["hash"]
        for f in TRIAGE_FILES:
            if (src / f).is_file():
                shutil.copy2(src / f, d / f)
        if not (d / "repro.js").is_file():
            art = paths.STORE_DIR / "crashes" / crash["hash"]
            if art.is_dir():
                for cand in sorted(art.glob("*.js")):
                    shutil.copy2(cand, d / "repro.js")
                    break

    meta = {
        "id": cid,
        "source": source,
        "crash_hash": crash["hash"] if crash else None,
        "fault_type": crash["fault_type"] if crash else None,
        "severity": crash["severity"] if crash else None,
        "build_rev": crash["build_rev"] if crash else None,
        "created": time.time(),
        "state": "BUNDLED",
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    (d / "notes.md").write_text("# notes\n\n(hypothesis | evidence | result)\n")
    (d / "triage.md").write_text(
        "# triage\n\n"
        + (
            f"- crash: {meta['crash_hash'][:12]}\n- class: {meta['fault_type']}\n"
            f"- score: {meta['severity']}\n- build_rev: {meta['build_rev']}\n"
            if crash
            else "- (chưa gắn crash)\n"
        )
    )
    (d / "brief.md").write_text(brief_text(meta))

    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT OR REPLACE INTO cases (id, crash_id, source, state) VALUES (?, ?, ?, ?)",
                (cid, crash["id"] if crash else None, source, "BUNDLED"),
            )
    finally:
        con.close()
    log_event(cid, "new", {"source": source, "crash": meta["crash_hash"]})
    return meta


def brief_text(meta: dict) -> str:
    v8 = paths.V8_ROOT
    scratch = Path("/tmp/opencode/chromly-case") / meta["id"]
    return f"""# Case {meta["id"]} — brief

## Crash
- hash: {meta.get("crash_hash")}
- class: {meta.get("fault_type")} · score: {meta.get("severity")}
- build rev: {meta.get("build_rev")}

## Tài nguyên (đường dẫn tuyệt đối)
- Workdir (đọc/ghi): {scratch}
- V8 source (chỉ đọc): {v8}
- d8 builds: {v8}/out/asan/d8 (ASAN+verify_heap) · {v8}/out/calib/d8 (ASAN+dcheck)
  · {v8}/out/fuzzilli/d8 (REPRL)
- Crash artifacts: repro.js · asan.txt · symbols.txt (trong workdir)

## Nhiệm vụ
1. Xác nhận repro: `out/asan/d8 --allow-natives-syntax repro.js` ×5 — ghi tỉ lệ thật.
2. Map root cause: frame trong asan.txt → Grep source V8 → file:line + giải thích cơ chế.
3. Viết `notes.md` theo `hypothesis | evidence | result` (từng bước).
4. Viết `VERDICT.md` dòng đầu đúng định dạng:
   `verdict: validated-crash|no-bug|needs-human|report-draft`
   rồi tóm tắt 5–10 dòng (root cause, evidence, bước tiếp).
5. Nếu cần skill: load `v8-triage` (skill tool). Xong thì DỪNG.
"""


def load_case(case_id: str) -> dict:
    d = case_dir(case_id)
    meta_p = d / "meta.json"
    if not meta_p.is_file():
        raise FileNotFoundError(f"không thấy case {case_id}")
    return json.loads(meta_p.read_text())


def set_state(case_id: str, state: str, **db_fields) -> None:
    d = case_dir(case_id)
    meta = load_case(case_id)
    meta["state"] = state
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    con = db.ensure_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in db_fields)
        with con:
            if sets:
                con.execute(
                    f"UPDATE cases SET state = ?, {sets} WHERE id = ?",
                    (state, *db_fields.values(), case_id),
                )
            else:
                con.execute("UPDATE cases SET state = ? WHERE id = ?", (state, case_id))
    finally:
        con.close()
    log_event(case_id, "state", {"state": state, **{k: str(v) for k, v in db_fields.items()}})


def list_cases() -> list[dict]:
    if not cases_dir().is_dir():
        return []
    out = []
    for d in sorted(cases_dir().iterdir()):
        if d.is_dir() and d.name.startswith("CASE-") and (d / "meta.json").is_file():
            out.append(json.loads((d / "meta.json").read_text()))
    return out
