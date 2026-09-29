from pathlib import Path

from chromly import paths
from chromly.fuzz import farm as farm_mod
from chromly.store import db
from chromly.telemetry import alerts as alerts_mod
from chromly.telemetry import registry, rollup


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")


def test_rollup(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        for v in (10.0, 20.0, 30.0):
            con.execute(
                "INSERT INTO metrics (ts, scope, name, value, tags) "
                "VALUES (datetime('now'), 'fuzz', 'execs_per_sec', ?, '')",
                (v,),
            )
    con.close()
    res = rollup.rollup(days=1)
    assert res["groups"] >= 1
    rows = rollup.latest_rollups()
    row = [r for r in rows if r["name"] == "execs_per_sec"][0]
    assert row["n"] == 3
    assert row["max"] == 30.0
    assert row["avg"] == 20.0


def test_alerts_evaluate_dedup_ack(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(alerts_mod, "intel_state", lambda: {"last_lag_hours": 50})
    monkeypatch.setattr(farm_mod, "status", lambda: {})

    new = alerts_mod.evaluate()
    assert any(x["rule"] == "watcher_lag" for x in new)

    # dedup: rule chưa-ack không tạo thêm
    new2 = alerts_mod.evaluate()
    assert not any(x["rule"] == "watcher_lag" for x in new2)

    rows = alerts_mod.list_alerts()
    assert rows
    assert alerts_mod.ack(rows[0]["id"])
    assert not alerts_mod.ack(99999)
    assert "Telemetry digest" in alerts_mod.digest()


def test_registry_sync(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    runtime = tmp_path / "repo" / "runtime"
    (runtime / "skills" / "v8-triage").mkdir(parents=True)
    (runtime / "persona.txt").write_text("persona")
    (runtime / "opencode.json").write_text("{}")
    (runtime / "skills" / "v8-triage" / "SKILL.md").write_text("skill")
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path / "repo")

    new = registry.sync()
    assert len(new) == 3
    assert registry.sync() == []
    assert len(registry.list_registry()) == 3
