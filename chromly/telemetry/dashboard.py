"""Dashboard v1 — M3-05: `chromly status` (§7.2). Text, đọc từ store + farm + intel."""

from __future__ import annotations

import shutil

from chromly import paths
from chromly.fuzz import farm
from chromly.intel.status import status as intel_stats
from chromly.store import db
from chromly.telemetry import alerts as alerts_mod


def render_status() -> str:
    lines = [f"== chromly status  ({paths.REPO_ROOT}) =="]

    st = farm.status()
    if st:
        for name, info in st.items():
            if info.get("alive"):
                execs = info.get("execs_per_sec")
                execs_s = f"{execs:.0f}/s" if isinstance(execs, (int, float)) else "—"
                lines.append(
                    f"farm   {name:<12} alive  pid={info['pid']:<8} up={info['uptime_s']}s  "
                    f"rss={info['rss_mb']}MB  execs={execs_s}"
                )
            else:
                lines.append(f"farm   {name:<12} DEAD   pid={info.get('pid')}")
    else:
        lines.append("farm   (trống — `chromly fuzz up`)")

    i = intel_stats()
    lines.append(
        f"intel  pending={i['pending']} reviewed={i['reviewed']} failed={i['failed']} "
        f"variants={i['with_variants']} kg={i['kg_nodes']}n/{i['kg_edges']}e "
        f"lag={i['lag_hours']}h"
    )

    con = db.ensure_db()
    try:
        total = con.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()["n"]
        raw = con.execute("SELECT COUNT(*) AS n FROM crashes WHERE state = 'raw'").fetchone()["n"]
        triaged = con.execute(
            "SELECT COUNT(*) AS n FROM crashes WHERE state = 'triaged'"
        ).fetchone()["n"]
        unacked = con.execute("SELECT COUNT(*) AS n FROM alerts WHERE ack = 0").fetchone()["n"]
    finally:
        con.close()
    lines.append(f"crash  total={total} raw={raw} triaged={triaged}")
    lines.append(f"alerts unacked={unacked}")
    for a in alerts_mod.list_alerts(only_unacked=True, limit=5):
        lines.append(f"       [{a['severity']}] {a['rule']} {a['payload']}")

    free = shutil.disk_usage(paths.REPO_ROOT).free / 1024**3
    lines.append(f"disk   {free:.0f}G free")
    return "\n".join(lines)
