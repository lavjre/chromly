"""Telemetry rollup — M3-04: metrics → metrics_rollup theo ngày (§7.2)."""

from __future__ import annotations

from chromly.store import db


def _percentile(values: list[float], q: float) -> float:
    xs = sorted(values)
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def rollup(days: int = 7) -> dict:
    """Tổng hợp metrics N ngày gần nhất → metrics_rollup (avg/p50/p95/max/n)."""
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT ts, scope, name, value FROM metrics WHERE ts >= datetime('now', ?)",
            (f"-{days} days",),
        ).fetchall()
        groups: dict[tuple, list[float]] = {}
        for r in rows:
            key = (str(r["ts"])[:10], r["scope"] or "", r["name"] or "")
            groups.setdefault(key, []).append(float(r["value"]))
        with con:
            for (day, scope, name), vals in groups.items():
                con.execute(
                    "INSERT OR REPLACE INTO metrics_rollup "
                    "(day, scope, name, avg, p50, p95, max, n) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        day,
                        scope,
                        name,
                        sum(vals) / len(vals),
                        _percentile(vals, 0.5),
                        _percentile(vals, 0.95),
                        max(vals),
                        len(vals),
                    ),
                )
        return {"days": days, "groups": len(groups)}
    finally:
        con.close()


def latest_rollups(limit: int = 20) -> list[dict]:
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT * FROM metrics_rollup ORDER BY day DESC, scope LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
