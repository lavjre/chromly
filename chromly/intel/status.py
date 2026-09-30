"""Intel status — M2-05: số liệu pending/reviewed/variants + lag."""

from __future__ import annotations

import json

from chromly.intel.watcher import _load_state
from chromly.store import db


def status() -> dict:
    con = db.ensure_db()
    try:

        def count(q: str, *params) -> int:
            return int(con.execute(q, params).fetchone()["n"])

        pending = count("SELECT COUNT(*) AS n FROM intel WHERE review_status = 'pending'")
        reviewed = count("SELECT COUNT(*) AS n FROM intel WHERE review_status = 'reviewed'")
        failed = count("SELECT COUNT(*) AS n FROM intel WHERE review_status = 'failed'")
        with_variants = count("SELECT COUNT(*) AS n FROM intel WHERE variant_flag = 1")
        nodes = count("SELECT COUNT(*) AS n FROM kg_nodes")
        edges = count("SELECT COUNT(*) AS n FROM kg_edges")
        last = con.execute(
            'SELECT "commit", created FROM intel ORDER BY created DESC LIMIT 1'
        ).fetchone()
    finally:
        con.close()
    state = _load_state()
    from chromly.intel.watcher import max_lag_hours

    last_polls = [
        v.get("last_poll")
        for v in state.values()
        if isinstance(v, dict) and isinstance(v.get("last_poll"), (int, float))
    ]
    return {
        "pending": pending,
        "reviewed": reviewed,
        "failed": failed,
        "with_variants": with_variants,
        "kg_nodes": nodes,
        "kg_edges": edges,
        "last_commit": (last["commit"][:12] if last else None),
        "lag_hours": max_lag_hours(state),
        "last_poll": max(last_polls) if last_polls else None,
    }


def run_status() -> int:
    st = status()
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0
