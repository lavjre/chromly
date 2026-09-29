"""Dynamic scheduler — M4-04 (§6.5): deterministic modes theo telemetry.

Modes: NORMAL · FUZZ_LEAN · BUILD_WINDOW · CASE_PRIORITY · RED
Inputs: MemAvailable, PSI cpu/mem (some), disk %, queue (case đang RUNNING), budget tier.
Điều kiện giữ ≥60s, dwell ≥10' giữa 2 lần chuyển; mọi chuyển ghi scheduler_decisions.
Override tay: bảng overrides (§10.4).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from chromly import paths
from chromly.orchestrator import budget
from chromly.store import db

MODES = ("NORMAL", "FUZZ_LEAN", "BUILD_WINDOW", "CASE_PRIORITY", "RED")
HOLD_S = 60.0
DWELL_S = 600.0
STATE_PATH = paths.STORE_DIR / "scheduler_state.json"
PRESSURE_HOLD = {"since": None, "candidate": None}


def _mem_available_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 / 1024
    return 0.0


def _psi_some(resource: str) -> float | None:
    p = Path(f"/proc/pressure/{resource}")
    if not p.is_file():
        return None
    for line in p.read_text().splitlines():
        if line.startswith("some"):
            for tok in line.split():
                if tok.startswith("avg10="):
                    return float(tok.split("=")[1])
    return None


def _disk_free_gb() -> float:
    import shutil

    return shutil.disk_usage(paths.REPO_ROOT).free / 1024**3


def _case_running() -> bool:
    con = db.ensure_db()
    try:
        row = con.execute("SELECT COUNT(*) AS n FROM cases WHERE state = 'RUNNING'").fetchone()
        return row["n"] > 0
    finally:
        con.close()


def _active_override() -> dict | None:
    con = db.ensure_db()
    try:
        row = con.execute(
            "SELECT * FROM overrides WHERE expires > datetime('now') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def snapshot() -> dict:
    return {
        "mem_available_gb": round(_mem_available_gb(), 2),
        "psi_cpu": _psi_some("cpu"),
        "psi_mem": _psi_some("memory"),
        "disk_free_gb": round(_disk_free_gb(), 1),
        "case_running": _case_running(),
        "budget_tier": budget.tier(),
    }


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"mode": "NORMAL", "mode_since": time.time()}


def _save_state(st: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, indent=2))


def desired_mode(snap: dict) -> tuple[str, str]:
    """Luật deterministic → (mode, reason)."""
    if snap["mem_available_gb"] < 0.8 or (snap["psi_mem"] or 0) > 60:
        return "RED", "mem pressure cao"
    if snap["disk_free_gb"] < 20:
        return "RED", "disk <20G"
    if (snap["psi_cpu"] or 0) > 45 and snap["mem_available_gb"] < 2.5:
        return "FUZZ_LEAN", "cpu+mem pressure"
    if snap["case_running"]:
        return "CASE_PRIORITY", "case đang chạy"
    if snap["budget_tier"] in ("window-cap", "exhausted"):
        return "FUZZ_LEAN", f"budget {snap['budget_tier']}"
    return "NORMAL", "default"


def record_decision(frm: str, to: str, reason: str, snap: dict) -> None:
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT INTO scheduler_decisions (ts, from_mode, to_mode, reason, snapshot_json) "
                "VALUES (datetime('now'), ?, ?, ?, ?)",
                (frm, to, reason, json.dumps(snap, ensure_ascii=False)),
            )
    finally:
        con.close()


def tick(now: float | None = None) -> dict:
    """Một lượt eval. Trả {mode, changed, reason}."""
    now = now if now is not None else time.time()
    ov = _active_override()
    if ov:
        st = _load_state()
        mode = str(ov["action"]).upper()
        if mode in MODES:
            if st.get("mode") != mode:
                record_decision(st.get("mode", "?"), mode, f"override: {ov['reason']}", snapshot())
                st["mode"] = mode
                st["mode_since"] = now
                _save_state(st)
            return {"mode": mode, "changed": False, "reason": "override"}

    snap = snapshot()
    want, reason = desired_mode(snap)
    st = _load_state()
    cur = st.get("mode", "NORMAL")

    if want == cur:
        PRESSURE_HOLD["candidate"] = None
        PRESSURE_HOLD["since"] = None
        return {"mode": cur, "changed": False, "reason": reason}

    # điều kiện giữ ≥60s trước khi chuyển
    if PRESSURE_HOLD["candidate"] != want:
        PRESSURE_HOLD["candidate"] = want
        PRESSURE_HOLD["since"] = now
        return {"mode": cur, "changed": False, "reason": f"giữ {want} (chờ 60s)"}

    held_since = PRESSURE_HOLD["since"]
    if held_since is None or now - held_since < HOLD_S:
        return {"mode": cur, "changed": False, "reason": f"giữ {want} (<60s)"}

    # dwell tối thiểu 10' giữa 2 chuyển (trừ RED — an toàn thì chuyển ngay)
    if want != "RED" and now - st.get("mode_since", 0) < DWELL_S:
        return {"mode": cur, "changed": False, "reason": f"dwell <10' (muốn {want})"}

    record_decision(cur, want, reason, snap)
    st["mode"] = want
    st["mode_since"] = now
    _save_state(st)
    PRESSURE_HOLD["candidate"] = None
    PRESSURE_HOLD["since"] = None
    return {"mode": want, "changed": True, "reason": reason}


def set_override(
    action: str, duration_s: float, operator: str = "lavjre", reason: str = "manual"
) -> dict:
    mode = action.upper()
    if mode not in MODES:
        raise ValueError(f"mode không hợp lệ: {action}")
    con = db.ensure_db()
    try:
        with con:
            con.execute(
                "INSERT INTO overrides (operator, scope, action, reason, expires) "
                "VALUES (?, 'sched', ?, ?, datetime('now', ?))",
                (operator, mode, reason, f"+{int(duration_s)} seconds"),
            )
        return {"override": mode, "seconds": duration_s}
    finally:
        con.close()


def run_sched_cmd(args) -> int:
    sub = getattr(args, "sched_cmd", None)
    if sub in (None, "status"):
        st = _load_state()
        ov = _active_override()
        out = {"mode": st.get("mode"), "since": st.get("mode_since")}
        if sub is None:
            out.update(snapshot())
        if ov:
            out["override"] = {
                "action": ov["action"],
                "expires": ov["expires"],
                "reason": ov["reason"],
            }
        print(json.dumps(out, indent=2))
        return 0
    if sub == "eval":
        res = tick()
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if sub == "override":
        res = set_override(args.mode, float(args.minutes) * 60, reason=args.reason or "manual")
        print(json.dumps(res))
        return 0
    print("usage: chromly sched {status|eval|override}")
    return 2
