import json
from pathlib import Path

from chromly import paths
from chromly.orchestrator import scheduler
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(scheduler, "STATE_PATH", tmp_path / "store" / "scheduler_state.json")
    monkeypatch.setattr(scheduler, "PRESSURE_HOLD", {"since": None, "candidate": None})


def test_desired_mode_rules(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    snap = {
        "mem_available_gb": 0.5,
        "psi_cpu": 0,
        "psi_mem": 0,
        "disk_free_gb": 100,
        "case_running": False,
        "budget_tier": "flash",
    }
    assert scheduler.desired_mode(snap)[0] == "RED"

    snap["mem_available_gb"] = 4
    snap["case_running"] = True
    assert scheduler.desired_mode(snap)[0] == "CASE_PRIORITY"

    snap["case_running"] = False
    snap["budget_tier"] = "window-cap"
    assert scheduler.desired_mode(snap)[0] == "FUZZ_LEAN"


def test_tick_hold_and_dwell(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    scheduler._save_state({"mode": "NORMAL", "mode_since": 0.0})
    monkeypatch.setattr(
        scheduler,
        "snapshot",
        lambda: {
            "mem_available_gb": 4,
            "psi_cpu": 0,
            "psi_mem": 0,
            "disk_free_gb": 100,
            "case_running": True,
            "budget_tier": "flash",
        },
    )
    # tick 1: muốn CASE_PRIORITY — bắt đầu giữ
    r1 = scheduler.tick(now=0.0)
    assert r1["changed"] is False and r1["mode"] == "NORMAL"
    # sau 61s: chuyển (dwell: mode_since=0, now=100 > 600? không — cần dwell 10'
    r2 = scheduler.tick(now=61.0)
    assert r2["changed"] is False  # dwell chưa đủ
    r3 = scheduler.tick(now=700.0)
    assert r3["changed"] is True and r3["mode"] == "CASE_PRIORITY"
    con = db.ensure_db()
    n = con.execute("SELECT COUNT(*) AS n FROM scheduler_decisions").fetchone()["n"]
    con.close()
    assert n == 1


def test_override(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    res = scheduler.set_override("RED", 300, reason="test")
    assert res["override"] == "RED"
    r = scheduler.tick(now=1000.0)
    assert r["mode"] == "RED"
    con = db.ensure_db()
    row = con.execute("SELECT action, reason FROM overrides").fetchone()
    con.close()
    assert row["action"] == "RED" and row["reason"] == "test"
    assert json.loads(json.dumps(row["reason"])) == "test"
