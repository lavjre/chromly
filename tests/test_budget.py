from pathlib import Path

from chromly import paths
from chromly.orchestrator import budget
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")


def _add_run(cost: float, age_hours: int = 0) -> None:
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO runs (cost_est, created, outcome) VALUES (?, datetime('now', ?), 'test')",
            (cost, f"-{age_hours} hours"),
        )
    con.close()


def test_tier_flash(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _add_run(0.5)
    assert budget.tier() == "flash"
    assert budget.pick_model()["model"] == budget.FLASH_MODEL


def test_tier_window_cap(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _add_run(12.5)  # > window5h 12
    assert budget.tier() == "window-cap"
    assert "free" in budget.pick_model()["model"]


def test_tier_day_cap(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _add_run(3.0)
    assert budget.tier() == "day-cap"
    assert budget.pick_model(high_score=False)["note"].startswith("chạm cap ngày")


def test_tier_exhausted(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _add_run(60.0)
    assert budget.tier() == "exhausted"
    assert budget.pick_model()["model"] == budget.PLAN_B_CHAIN[0]


def test_check_case(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    assert budget.check_case(est_cost=1.5)["allow"] is True
    assert budget.check_case(est_cost=3.0)["allow"] is False
