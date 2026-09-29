from pathlib import Path

from chromly import paths
from chromly.case import pipeline, runner
from chromly.orchestrator import budget
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(paths, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(runner, "CASE_SCRATCH", tmp_path / "scratch")


def test_new_case_layout(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, ?, ?, 'triaged')",
            ("a" * 64, "heap-buffer-overflow", 5),
        )
    con.close()
    tri = paths.STORE_DIR / "triage" / ("a" * 64)
    tri.mkdir(parents=True)
    (tri / "repro.js").write_text("print(1)")
    (tri / "asan.txt").write_text("asan report")

    meta = pipeline.new_case("a" * 12)
    assert meta["id"] == "CASE-0001"
    assert meta["state"] == "BUNDLED"
    d = pipeline.case_dir("CASE-0001")
    for f in ("meta.json", "brief.md", "triage.md", "notes.md", "repro.js", "asan.txt"):
        assert (d / f).is_file(), f
    assert str(paths.V8_ROOT) in (d / "brief.md").read_text()


def test_parse_verdict() -> None:
    assert runner.parse_verdict("verdict: needs-human\nrest") == "needs-human"
    assert runner.parse_verdict("verdict: validated-crash") == "validated-crash"
    assert runner.parse_verdict("không có gì") is None


def test_run_case_budget_deny(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    monkeypatch.setattr(
        budget,
        "check_case",
        lambda est_cost=2.0, high_score=True: {"allow": False, "reason": "test"},
    )
    res = runner.run_case(meta["id"], max_wall=1)
    assert res["status"] == "budget-deny"


def test_set_state_and_list(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    got = pipeline.load_case(meta["id"])
    assert got["state"] == "RUNNING"
    assert [c["id"] for c in pipeline.list_cases()] == [meta["id"]]
