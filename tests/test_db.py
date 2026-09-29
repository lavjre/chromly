import sqlite3
from pathlib import Path

from chromly.store import db


def _tables(con) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_ensure_db_creates_schema(tmp_path: Path) -> None:
    con = db.ensure_db(tmp_path / "t.db")
    assert {"crashes", "cases", "builds", "runs", "intel", "budget"} <= _tables(con)
    assert con.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    con.close()


def test_build_row_roundtrip(tmp_path: Path) -> None:
    con = db.ensure_db(tmp_path / "t.db")
    with con:
        con.execute(
            "INSERT INTO builds (id, config, status) VALUES (?, ?, ?)",
            ("asan-test", "asan", "ok"),
        )
    row = con.execute("SELECT config, status FROM builds WHERE id = 'asan-test'").fetchone()
    assert row["config"] == "asan"
    assert row["status"] == "ok"
    con.close()


def test_ensure_db_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "t.db"
    db.ensure_db(p).close()
    db.ensure_db(p).close()


def test_migration_v1_to_v2(tmp_path: Path) -> None:
    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.executescript(
        "CREATE TABLE crashes (id INTEGER PRIMARY KEY, hash TEXT UNIQUE, fault_type TEXT, "
        "stack_norm TEXT, severity INTEGER, build_rev TEXT, source TEXT, created TEXT, state TEXT);"
    )
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()

    con2 = db.ensure_db(old)
    assert con2.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    cols = {r[1] for r in con2.execute("PRAGMA table_info(crashes)")}
    assert "dup_count" in cols
    assert {"metrics", "kg_nodes", "kg_edges", "lessons"} <= _tables(con2)
    con2.close()
