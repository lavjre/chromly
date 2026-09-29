import json
from pathlib import Path

from chromly import paths
from chromly.knowledge import kg
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(kg, "intel_case_dir", lambda sha: tmp_path / "store" / "intel" / sha)


def test_ingest_and_query(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    sha = "f" * 40
    d = kg.intel_case_dir(sha)
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"subject": "Fix bounds check", "date": "2026-09-29"}))
    (d / "variants.json").write_text(json.dumps([{"title": "sibling path", "confidence": "med"}]))

    res = kg.ingest_review(sha)
    assert res["variants"] == 1

    # idempotent: không nhân đôi node/edge
    kg.ingest_review(sha)
    con = db.ensure_db()
    nodes = con.execute("SELECT COUNT(*) AS n FROM kg_nodes").fetchone()["n"]
    edges = con.execute("SELECT COUNT(*) AS n FROM kg_edges").fetchone()["n"]
    con.close()
    assert nodes == 2
    assert edges == 1

    rows = kg.query(type_="hypothesis")
    assert len(rows) == 1
    assert "sibling path" in rows[0]["ref"]
    assert kg.kg_log_path().is_file()


def test_neighbors(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    sha = "e" * 40
    d = kg.intel_case_dir(sha)
    d.mkdir(parents=True)
    (d / "meta.json").write_text("{}")
    (d / "variants.json").write_text(json.dumps([{"title": "v1"}, {"title": "v2"}]))
    kg.ingest_review(sha)

    con = db.ensure_db()
    hyp = con.execute("SELECT id FROM kg_nodes WHERE type = 'hypothesis' LIMIT 1").fetchone()
    edges = kg.neighbors(con, hyp["id"], rel="derived_from")
    con.close()
    assert len(edges) == 1
    assert edges[0]["type"] == "commit"
