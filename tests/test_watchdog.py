import json
import os
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm, watchdog


def test_cpu_ticks_tree_current_process() -> None:
    ticks = watchdog.cpu_ticks_tree(os.getpid())
    assert ticks is not None and ticks >= 0


def test_cpu_ticks_tree_missing() -> None:
    assert watchdog.cpu_ticks_tree(999999999) is None


def test_append_event(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(watchdog, "EVENTS_PATH", tmp_path / "events.jsonl")
    watchdog.append_event("test", "u1", {"x": 1})
    line = json.loads((tmp_path / "events.jsonl").read_text().strip())
    assert line["event"] == "test"
    assert line["unit"] == "u1"
    assert line["x"] == 1


def _fake_state(monkeypatch, tmp_path: Path, rec: dict) -> None:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(farm, "STATE_PATH", tmp_path / "fuzz" / "state.json")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "fuzz" / "logs")
    monkeypatch.setattr(watchdog, "EVENTS_PATH", tmp_path / "fuzz" / "events.jsonl")
    farm._save_state({"units": {"fake": rec}})


def test_tick_restarts_dead_unit(monkeypatch, tmp_path: Path) -> None:
    _fake_state(
        monkeypatch,
        tmp_path,
        {
            "pid": 999999999,
            "started": 0,
            "cmd": ["/usr/bin/sleep", "300"],
            "log": str(tmp_path / "f.log"),
            "type": "fuzzilli",
        },
    )
    actions = watchdog.tick(now=1000.0, hang_s=5)
    assert actions and actions[0]["action"] == "restarted"
    st = farm._load_state()
    assert farm._alive(st["units"]["fake"])
    farm.down(["fake"])


def test_tick_degrades_after_crash_loop(monkeypatch, tmp_path: Path) -> None:
    _fake_state(
        monkeypatch,
        tmp_path,
        {
            "pid": 999999999,
            "started": 0,
            "cmd": ["/usr/bin/sleep", "300"],
            "log": str(tmp_path / "f.log"),
            "type": "fuzzilli",
            "restarts": [990.0, 995.0, 998.0],
        },
    )
    actions = watchdog.tick(now=1000.0, hang_s=5)
    assert actions and actions[0]["action"] == "degraded"
    assert farm._load_state()["units"]["fake"]["degraded"] is True


def test_restart_empty_record_no_keyerror(monkeypatch, tmp_path: Path) -> None:
    _fake_state(monkeypatch, tmp_path, {"pid": None, "restarts": []})
    monkeypatch.setattr(farm, "default_units", lambda: [])
    monkeypatch.setattr(farm, "up", lambda units: None)
    state = farm._load_state()
    rec = state["units"]["fake"]
    res = watchdog._restart(state, "fake", rec, "dead", 1000.0)
    assert res["action"] == "skip"


def test_case_stale_check_marks_timeout(monkeypatch, tmp_path: Path) -> None:
    _fake_state(monkeypatch, tmp_path, {"pid": None, "restarts": []})
    monkeypatch.setattr(paths, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    d = tmp_path / "cases" / "CASE-0001"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"id": "CASE-0001", "state": "RUNNING"}))
    old = 1000.0
    os.utime(d / "meta.json", (old, old))
    now = old + watchdog.CASE_STALE_S + 60
    actions = watchdog._case_stale_check(now)
    assert actions and actions[0]["action"] == "case-timeout"
    assert json.loads((d / "meta.json").read_text())["state"] == "TIMEOUT"


def test_case_stale_check_skips_fresh(monkeypatch, tmp_path: Path) -> None:
    _fake_state(monkeypatch, tmp_path, {"pid": None, "restarts": []})
    monkeypatch.setattr(paths, "CASES_DIR", tmp_path / "cases")
    d = tmp_path / "cases" / "CASE-0002"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"id": "CASE-0002", "state": "RUNNING"}))
    now = time.time()
    assert watchdog._case_stale_check(now) == []


def test_aux_check_skips_unknown_name(monkeypatch) -> None:
    """Record aux lạ (không có trong AUX_SPECS) → bỏ qua, không crash (bài học 11/10)."""
    from chromly.fuzz import watchdog
    from chromly.orchestrator import supervisor

    state = {"aux": {"ghost-aux": {"pid": 999999}, "watchdog": {"pid": 1}}}
    called: list[str] = []
    monkeypatch.setattr(supervisor, "_spawn_aux", lambda name: called.append(name) or {"pid": 1})
    actions = watchdog._aux_check(state)
    assert called == []
    assert actions == []
