"""Report generator — M8: weekly digest file (§7.2)."""

from __future__ import annotations

import time
from pathlib import Path

from chromly import paths
from chromly.store import db
from chromly.telemetry.dashboard import render_status


def reports_dir() -> Path:
    return paths.STORE_DIR / "reports"


def weekly_report() -> Path:
    year, week, _ = time.localtime().tm_year, time.strftime("%V"), time.localtime().tm_wday
    path = reports_dir() / f"weekly-{year}-W{week}.md"

    lines = [f"# chromly weekly digest — {year}-W{week}", ""]
    lines += ["## Status", "```", render_status(), "```"]

    from chromly.telemetry.alerts import digest as alert_digest

    lines += ["", "## Alerts (7d)", alert_digest()]

    con = db.ensure_db()
    try:
        runs = con.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(cost_est),0) AS c FROM runs "
            "WHERE created >= datetime('now', '-7 days')"
        ).fetchone()
        lines += [
            "",
            "## 7 ngày",
            f"- runs: {runs['n']} · cost_est: ${runs['c']:.3f}",
        ]
        rows = con.execute(
            "SELECT verdict, COUNT(*) AS n FROM cases WHERE state = 'VERDICT' GROUP BY verdict"
        ).fetchall()
        if rows:
            lines.append("- cases verdict: " + ", ".join(f"{r['verdict']}×{r['n']}" for r in rows))
        calib = con.execute("SELECT COUNT(*) AS n FROM calibration").fetchone()["n"]
        lines.append(f"- calibration runs: {calib}")
    finally:
        con.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def run_report_cmd(args) -> int:
    sub = getattr(args, "report_cmd", None)
    if sub == "weekly":
        print(weekly_report())
        return 0
    print("usage: chromly report weekly")
    return 2
