"""SQLite store — schema v2: subset vận hành của §7.1 + metrics (M1-07).

Telemetry đầy đủ · knowledge · benchmark thêm ở M3/M4 (migration tăng SCHEMA_VERSION).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from chromly import paths

SCHEMA_VERSION = 5

_DDL = """
CREATE TABLE IF NOT EXISTS crashes (
    id          INTEGER PRIMARY KEY,
    hash        TEXT NOT NULL UNIQUE,
    fault_type  TEXT,
    stack_norm  TEXT,
    severity    INTEGER,
    build_rev   TEXT,
    source      TEXT,
    created     TEXT DEFAULT (datetime('now')),
    state       TEXT DEFAULT 'new',
    dup_count   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cases (
    id          TEXT PRIMARY KEY,
    crash_id    INTEGER REFERENCES crashes(id),
    source      TEXT,
    state       TEXT DEFAULT 'NEW',
    verdict     TEXT,
    created     TEXT DEFAULT (datetime('now')),
    closed      TEXT,
    budget_used REAL DEFAULT 0,
    notes_path  TEXT
);

CREATE TABLE IF NOT EXISTS builds (
    id            TEXT PRIMARY KEY,
    config        TEXT NOT NULL,
    rev           TEXT,
    status        TEXT NOT NULL,
    artifact_path TEXT,
    duration_s    REAL,
    started       TEXT,
    finished      TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    case_id     TEXT REFERENCES cases(id),
    session_id  TEXT,
    model       TEXT,
    prompt_hash TEXT,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    cost_est    REAL,
    wall_s      REAL,
    outcome     TEXT,
    created     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS intel (
    "commit"      TEXT PRIMARY KEY,
    paths         TEXT,
    review_status TEXT,
    variant_flag  INTEGER DEFAULT 0,
    case_id       TEXT,
    created       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS budget (
    day         TEXT,
    model       TEXT,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    cost_est    REAL DEFAULT 0,
    tier_alerts TEXT,
    PRIMARY KEY (day, model)
);

CREATE TABLE IF NOT EXISTS metrics (
    ts    TEXT,
    scope TEXT,
    name  TEXT,
    value REAL,
    tags  TEXT
);

CREATE TABLE IF NOT EXISTS kg_nodes (
    id         INTEGER PRIMARY KEY,
    type       TEXT,
    ref        TEXT,
    attrs_json TEXT,
    case_id    TEXT,
    created    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kg_edges (
    src_id     INTEGER,
    dst_id     INTEGER,
    rel        TEXT,
    attrs_json TEXT,
    created    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id      INTEGER PRIMARY KEY,
    case_id TEXT,
    kind    TEXT,
    text    TEXT,
    created TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS metrics_rollup (
    day   TEXT,
    scope TEXT,
    name  TEXT,
    avg   REAL,
    p50   REAL,
    p95   REAL,
    max   REAL,
    n     INTEGER,
    PRIMARY KEY (day, scope, name)
);

CREATE TABLE IF NOT EXISTS alerts (
    id       INTEGER PRIMARY KEY,
    ts       TEXT DEFAULT (datetime('now')),
    rule     TEXT,
    severity TEXT,
    payload  TEXT,
    ack      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS overrides (
    id       INTEGER PRIMARY KEY,
    ts       TEXT DEFAULT (datetime('now')),
    operator TEXT,
    scope    TEXT,
    action   TEXT,
    reason   TEXT,
    expires  TEXT
);

CREATE TABLE IF NOT EXISTS prompt_registry (
    hash      TEXT,
    kind      TEXT,
    version   TEXT,
    created   TEXT DEFAULT (datetime('now')),
    diff_note TEXT,
    PRIMARY KEY (hash, kind)
);

CREATE TABLE IF NOT EXISTS calibration (
    id            INTEGER PRIMARY KEY,
    bug           TEXT,
    surface       TEXT,
    bug_class     TEXT,
    difficulty    INTEGER,
    coverage_note TEXT,
    last_fail     TEXT
);

CREATE TABLE IF NOT EXISTS scheduler_decisions (
    ts            TEXT,
    from_mode     TEXT,
    to_mode       TEXT,
    reason        TEXT,
    snapshot_json TEXT
);
"""

# Migration theo bước: {version đích: [câu SQL]}
_MIGRATIONS: dict[int, list[str]] = {
    2: [
        "ALTER TABLE crashes ADD COLUMN dup_count INTEGER DEFAULT 1",
        """CREATE TABLE IF NOT EXISTS metrics (
            ts    TEXT,
            scope TEXT,
            name  TEXT,
            value REAL,
            tags  TEXT
        )""",
    ],
    3: [
        """CREATE TABLE IF NOT EXISTS kg_nodes (
            id         INTEGER PRIMARY KEY,
            type       TEXT,
            ref        TEXT,
            attrs_json TEXT,
            case_id    TEXT,
            created    TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS kg_edges (
            src_id     INTEGER,
            dst_id     INTEGER,
            rel        TEXT,
            attrs_json TEXT,
            created    TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS lessons (
            id      INTEGER PRIMARY KEY,
            case_id TEXT,
            kind    TEXT,
            text    TEXT,
            created TEXT DEFAULT (datetime('now'))
        )""",
    ],
    4: [
        """CREATE TABLE IF NOT EXISTS metrics_rollup (
            day   TEXT,
            scope TEXT,
            name  TEXT,
            avg   REAL,
            p50   REAL,
            p95   REAL,
            max   REAL,
            n     INTEGER,
            PRIMARY KEY (day, scope, name)
        )""",
        """CREATE TABLE IF NOT EXISTS alerts (
            id       INTEGER PRIMARY KEY,
            ts       TEXT DEFAULT (datetime('now')),
            rule     TEXT,
            severity TEXT,
            payload  TEXT,
            ack      INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS overrides (
            id       INTEGER PRIMARY KEY,
            ts       TEXT DEFAULT (datetime('now')),
            operator TEXT,
            scope    TEXT,
            action   TEXT,
            reason   TEXT,
            expires  TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS prompt_registry (
            hash      TEXT,
            kind      TEXT,
            version   TEXT,
            created   TEXT DEFAULT (datetime('now')),
            diff_note TEXT,
            PRIMARY KEY (hash, kind)
        )""",
        """CREATE TABLE IF NOT EXISTS calibration (
            id            INTEGER PRIMARY KEY,
            bug           TEXT,
            surface       TEXT,
            bug_class     TEXT,
            difficulty    INTEGER,
            coverage_note TEXT,
            last_fail     TEXT
        )""",
    ],
    5: [
        """CREATE TABLE IF NOT EXISTS scheduler_decisions (
            ts            TEXT,
            from_mode     TEXT,
            to_mode       TEXT,
            reason        TEXT,
            snapshot_json TEXT
        )""",
    ],
}


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else paths.DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(_DDL)
    con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    con.commit()


def _migrate(con: sqlite3.Connection, from_version: int) -> None:
    for step in range(from_version + 1, SCHEMA_VERSION + 1):
        for stmt in _MIGRATIONS.get(step, []):
            con.execute(stmt)
        con.execute(f"PRAGMA user_version = {step}")
    con.commit()


def ensure_db(path: Path | str | None = None) -> sqlite3.Connection:
    con = connect(path)
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        init_schema(con)
    elif version < SCHEMA_VERSION:
        _migrate(con, version)
    return con
