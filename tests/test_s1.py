"""S1 decision layer — build state + HTTP flow (mock, không cần server/laya thật)."""

import json
from pathlib import Path

from chromly import paths
from chromly.s1 import decide

H = "a" * 64


class _FakeResp:
    def __init__(self, payload: dict, headers: dict | None = None, status: int = 200) -> None:
        self._body = json.dumps(payload).encode()
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _setup(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    crash = tmp_path / "store" / "crashes" / H
    crash.mkdir(parents=True)
    (crash / "program_x.js").write_text("print('boom')\n// pad\n// pad\n")
    (crash / "meta.json").write_text(json.dumps({"hash": H, "unit": "variant"}))
    tri = tmp_path / "store" / "triage" / H
    tri.mkdir(parents=True)
    (tri / "asan.txt").write_text(
        "# Fatal error in ../../src/maglev/x.cc, line 839\n"
        "    /home/lavjre/v8/v8/out/calib/d8(v8::internal::X+0x12) [0x584db4ce2b4a]\n"
    )
    (tri / "repro.flags.txt").write_text("--allow-natives-syntax\n")
    return tmp_path


def test_sanitize_paths_and_addrs() -> None:
    s = decide._sanitize(
        "    /home/lavjre/v8/v8/out/calib/d8(v8::internal::X+0x12) [0x584db4ce2b4a]"
    )
    assert "/home/lavjre" not in s
    assert "584db4ce2b4a" not in s
    assert "d8<out/calib>" in s


def test_build_crash_state(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    state, d = decide.build_crash_state(H[:12])
    assert d.name == H
    assert "fault_label_from_pipeline:" in state
    assert "--allow-natives-syntax" in state
    assert "Fatal error" in state
    assert "print('boom')" in state
    assert "/home/lavjre" not in state


def test_build_crash_state_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    (tmp_path / "store" / "crashes").mkdir(parents=True)
    try:
        decide.build_crash_state("nope")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("phải raise FileNotFoundError")


def test_ask_http(monkeypatch) -> None:
    calls = {}

    def fake_urlopen(req, timeout=0):
        calls["url"] = req.full_url
        return _FakeResp(
            {"model": "m", "answers": {"exploitable": {"noul": 0.5}}},
            {"X-Inference-Time-Ms": "123"},
        )

    monkeypatch.setattr(decide.urllib.request, "urlopen", fake_urlopen)
    res = decide.ask("state", {"q": {}})
    assert res["answers"]["exploitable"]["noul"] == 0.5
    assert res["elapsed_ms"] == 123
    assert calls["url"].endswith("/v1/systemone")


def test_triage_crash_mock(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        decide,
        "ask",
        lambda state, q: {
            "answers": {
                "exploitable": {"noul": 0.9},
                "ladder": {"noul": 0.7},
                "impact": {"choice": "memory-corruption"},
                "next": {"choice": "attempt-ladder"},
            },
            "elapsed_ms": 5,
            "model": "test",
            "routing": {"model": "test"},
        },
    )
    out = decide.triage_crash(H[:12])
    assert out["exploitable"] == 0.9 and out["next"] == "attempt-ladder"
    assert (decide.s1_dir() / f"{H}.json").is_file()
    assert decide.load_result(H[:12])["impact"] == "memory-corruption"


def test_load_result_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    assert decide.load_result("khong-co") is None


def test_run_s1_cmd_usage() -> None:
    args = type("A", (), {"s1_cmd": None})()
    assert decide.run_s1_cmd(args) == 2


def test_check_needs_server(monkeypatch, capsys) -> None:
    monkeypatch.setattr(decide, "available", lambda: True)
    monkeypatch.setattr(decide, "server_up", lambda timeout=2.0: False)
    args = type("A", (), {"s1_cmd": "check"})()
    assert decide.run_s1_cmd(args) == 1
    assert "không sống" in capsys.readouterr().out
