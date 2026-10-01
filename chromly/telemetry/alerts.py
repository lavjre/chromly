"""Alert engine — M3-04: rules trên state/metrics → alerts + digest (§7.2).

Rules v0: watcher_lag · disk_low · farm_dead · refusal_recent · crash_stale · case_help.
Dedup: cùng rule chỉ có 1 alert chưa-ack; ack qua `chromly telemetry alerts --ack N`.
"""

from __future__ import annotations

import json
import shutil
import time

from chromly import paths
from chromly.fuzz import farm
from chromly.intel.watcher import _load_state as intel_state
from chromly.store import db


def _new_alert(con, rule: str, severity: str, payload: dict) -> bool:
    row = con.execute("SELECT id FROM alerts WHERE rule = ? AND ack = 0", (rule,)).fetchone()
    if row is not None:
        return False
    con.execute(
        "INSERT INTO alerts (rule, severity, payload) VALUES (?, ?, ?)",
        (rule, severity, json.dumps(payload, ensure_ascii=False)),
    )
    return True


def evaluate() -> list[dict]:
    """Chạy toàn bộ rules, trả các alert MỚI (đã ghi DB)."""
    new: list[dict] = []
    con = db.ensure_db()
    try:
        from chromly.intel.watcher import max_lag_hours

        lag = max_lag_hours(intel_state())
        if (
            lag is not None
            and lag > 24
            and _new_alert(con, "watcher_lag", "warn", {"lag_hours": lag})
        ):
            new.append({"rule": "watcher_lag", "severity": "warn", "payload": {"lag_hours": lag}})

        free_gb = shutil.disk_usage(paths.REPO_ROOT).free / 1024**3
        if free_gb < 60 and _new_alert(con, "disk_low", "crit", {"free_gb": round(free_gb, 1)}):
            new.append({"rule": "disk_low", "severity": "crit", "payload": {"free_gb": free_gb}})

        st = farm.status()
        for name, info in st.items():
            if not info.get("alive") and _new_alert(
                con, "farm_dead", "crit", {"unit": name, "pid": info.get("pid")}
            ):
                new.append({"rule": "farm_dead", "severity": "crit", "payload": {"unit": name}})

        refusals = con.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE outcome LIKE '%refusal%' "
            "AND created >= datetime('now', '-1 day')"
        ).fetchone()["n"]
        if refusals > 0 and _new_alert(con, "refusal_recent", "warn", {"count": refusals}):
            new.append(
                {"rule": "refusal_recent", "severity": "warn", "payload": {"count": refusals}}
            )

        crashes_7d = con.execute(
            "SELECT COUNT(*) AS n FROM crashes WHERE created >= datetime('now', '-7 days')"
        ).fetchone()["n"]
        units_up = any(i.get("alive") for i in st.values())
        started = min(
            (r.get("started", time.time()) for r in farm._load_state()["units"].values()),
            default=time.time(),
        )
        if (
            units_up
            and crashes_7d == 0
            and time.time() - started > 7 * 86400
            and _new_alert(con, "crash_stale", "warn", {"days": 7})
        ):
            new.append({"rule": "crash_stale", "severity": "warn", "payload": {"days": 7}})

        # case cần người (agent viết HELP.md) → alert, không đợi operator tự thấy
        for d in sorted(paths.CASES_DIR.glob("CASE-*")) if paths.CASES_DIR.is_dir() else []:
            try:
                meta = json.loads((d / "meta.json").read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("state") == "HELP" and _new_alert(
                con, "case_help", "warn", {"case": d.name}
            ):
                new.append({"rule": "case_help", "severity": "warn", "payload": {"case": d.name}})

        con.commit()
    finally:
        con.close()
    return new


def list_alerts(only_unacked: bool = True, limit: int = 20) -> list[dict]:
    con = db.ensure_db()
    try:
        q = "SELECT * FROM alerts"
        if only_unacked:
            q += " WHERE ack = 0"
        q += " ORDER BY id DESC LIMIT ?"
        return [dict(r) for r in con.execute(q, (limit,))]
    finally:
        con.close()


def ack(alert_id: int) -> bool:
    con = db.ensure_db()
    try:
        with con:
            cur = con.execute("UPDATE alerts SET ack = 1 WHERE id = ?", (alert_id,))
        return cur.rowcount > 0
    finally:
        con.close()


def digest() -> str:
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT rule, severity, COUNT(*) AS n FROM alerts "
            "WHERE ts >= datetime('now', '-7 days') GROUP BY rule, severity ORDER BY severity"
        ).fetchall()
    finally:
        con.close()
    lines = ["# Telemetry digest (7 ngày)"]
    if not rows:
        lines.append("- không có alert nào")
    for r in rows:
        lines.append(f"- [{r['severity']}] {r['rule']} × {r['n']}")
    return "\n".join(lines)
