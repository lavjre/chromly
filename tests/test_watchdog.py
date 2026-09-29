import json
import os
from pathlib import Path

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
