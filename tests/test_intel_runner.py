from pathlib import Path

from chromly import paths
from chromly.intel import runner
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(runner, "intel_dir", lambda: tmp_path / "store" / "intel")


def test_pending_commits(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            'INSERT INTO intel ("commit", paths, review_status) VALUES (?, ?, ?)',
            ("a" * 40, "[]", "pending"),
        )
        con.execute(
            'INSERT INTO intel ("commit", paths, review_status) VALUES (?, ?, ?)',
            ("b" * 40, "[]", "reviewed"),
        )
    con.close()
    pend = runner.pending_commits()
    assert [p["sha"] for p in pend] == ["a" * 40]


def test_run_review_missing_diff(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    res = runner.run_review("c" * 40)
    assert res["status"] == "no-diff"
