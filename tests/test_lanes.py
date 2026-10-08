"""Lane rotator — logic xoay (mock farm/engine, không spawn process)."""

from pathlib import Path

from chromly.fuzz import lanes


def _fake_farm(monkeypatch, tmp_path: Path, alive_units: dict | None = None):
    state = {"units": dict(alive_units or {})}
    started: list[str] = []
    stopped: list[str] = []

    def fake_load():
        return state

    def fake_up(units):
        out = {}
        for u in units:
            state["units"][u.name] = {"pid": 1, "cmd": u.cmd, "log": str(u.log), "type": u.type}
            started.append(u.name)
            out[u.name] = {"status": "started", "pid": 1}
        return out

    def fake_down(names):
        out = {}
        for n in names:
            state["units"].pop(n, None)
            stopped.append(n)
            out[n] = "stopped"
        return out

    monkeypatch.setattr(lanes.farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(lanes.farm, "LOGS_DIR", tmp_path / "fuzz" / "logs")
    monkeypatch.setattr(lanes.farm, "_load_state", fake_load)
    monkeypatch.setattr(lanes.farm, "up", fake_up)
    monkeypatch.setattr(lanes.farm, "down", fake_down)
    monkeypatch.setattr(lanes.farm, "_alive", lambda rec: True)
    monkeypatch.setattr(lanes.engine, "engine_bin", lambda t: tmp_path / "engine.bin")
    (tmp_path / "engine.bin").write_bytes(b"")
    monkeypatch.setattr(lanes, "state_path", lambda: tmp_path / "fuzz" / "lane-rotation.json")
    monkeypatch.setattr(lanes, "SWEEP_ENABLED", False)
    return state, started, stopped


def test_tick_starts_keep_lanes(monkeypatch, tmp_path: Path) -> None:
    state, started, _ = _fake_farm(monkeypatch, tmp_path)
    acts = lanes.tick(now=1000.0, keep=2, slice_s=3600)
    assert len(started) == 2
    assert all(a["action"] == "rotate-in" for a in acts)
    st = lanes._load()
    assert len(st["lanes"]) == 2
    assert st["next"] == 2


def test_tick_rotates_on_slice_end(monkeypatch, tmp_path: Path) -> None:
    state, started, stopped = _fake_farm(monkeypatch, tmp_path)
    lanes.tick(now=1000.0, keep=2, slice_s=3600)
    first_units = list(lanes._load()["lanes"])
    acts = lanes.tick(now=1000.0 + 4000, keep=2, slice_s=3600)
    assert set(stopped) == set(first_units)
    assert any(a["action"] == "rotate-out" for a in acts)
    assert len(lanes._load()["lanes"]) == 2


def test_tick_lazy_build(monkeypatch, tmp_path: Path) -> None:
    _fake_farm(monkeypatch, tmp_path)
    built: list[str] = []
    monkeypatch.setattr(lanes.engine, "engine_bin", lambda t: tmp_path / "missing.bin")
    monkeypatch.setattr(
        lanes.engine,
        "build_engine",
        lambda t: built.append(t) or {"ok": True, "wall_s": 5},
    )
    acts = lanes.tick(now=1000.0, keep=1, slice_s=3600)
    assert built == ["regexp"]
    assert any(a["action"] == "built" for a in acts)
    assert any(a["action"] == "rotate-in" for a in acts)


def test_tick_skips_active_target(monkeypatch, tmp_path: Path) -> None:
    state, started, _ = _fake_farm(monkeypatch, tmp_path)
    lanes.tick(now=1000.0, keep=2, slice_s=3600)
    st = lanes._load()
    targets = {v["target"] for v in st["lanes"].values()}
    assert targets == {"regexp", "json"}
    # nhịp sau trong cùng thời điểm: không start thêm (đủ keep)
    acts = lanes.tick(now=1001.0, keep=2, slice_s=3600)
    assert acts == []
    assert len(started) == 2
