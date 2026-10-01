"""ToT verify — resolve/classify/state (không cần d8 thật)."""

import json
from pathlib import Path

from chromly import paths
from chromly.builds import tot


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    (tmp_path / "store").mkdir(parents=True, exist_ok=True)


def test_classify() -> None:
    assert tot.classify(0, "ok") == "CLEAN"
    assert tot.classify(-11, "") == "STILL-CRASHES"
    assert tot.classify(139, "") == "STILL-CRASHES"
    assert tot.classify(1, "==1==ERROR: AddressSanitizer: heap-buffer-overflow") == "STILL-CRASHES"
    assert tot.classify(1, "Check failed: x.") == "STILL-CRASHES"
    assert tot.classify(1, "just an error\nTypeError: x") == "CLEAN"


def test_resolve_target_path(tmp_path: Path, monkeypatch) -> None:
    _setup(monkeypatch, tmp_path)
    f = tmp_path / "repro.js"
    f.write_text("print(1)")
    assert tot.resolve_target(str(f)) == f


def test_resolve_target_crash_hash(tmp_path: Path, monkeypatch) -> None:
    _setup(monkeypatch, tmp_path)
    d = tmp_path / "store" / "crashes" / ("a" * 64)
    d.mkdir(parents=True)
    (d / "program_test.js").write_text("print(2)")
    assert tot.resolve_target("aaaaaaaaaaaa").name == "program_test.js"


def test_resolve_target_missing(tmp_path: Path, monkeypatch) -> None:
    _setup(monkeypatch, tmp_path)
    try:
        tot.resolve_target("khong-co-gi")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("phải raise FileNotFoundError")


def test_state_roundtrip(tmp_path: Path, monkeypatch) -> None:
    _setup(monkeypatch, tmp_path)
    assert tot.load_state() == {}
    tot.save_state({"status": "ok", "sha": "x" * 40})
    assert tot.load_state()["sha"] == "x" * 40


def test_d8_ready_false_when_no_state(tmp_path: Path, monkeypatch) -> None:
    _setup(monkeypatch, tmp_path)
    assert tot.d8_ready() is False


def test_verify_needs_tot_build(tmp_path: Path, monkeypatch) -> None:
    _setup(monkeypatch, tmp_path)
    try:
        tot.verify("whatever")
    except RuntimeError as exc:
        assert "tot build" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("phải raise RuntimeError khi chưa build ToT")


def test_cmd_status_without_state(tmp_path: Path, monkeypatch, capsys) -> None:
    _setup(monkeypatch, tmp_path)
    rc = tot.run_tot_cmd(type("A", (), {"tot_cmd": "status"})())
    assert rc == 1
    assert "chưa build" in capsys.readouterr().out


def test_verifications_jsonl_written(tmp_path: Path, monkeypatch) -> None:
    """verify với d8 giả: script echo + exit 0 → CLEAN, ghi jsonl."""
    _setup(monkeypatch, tmp_path)
    d8 = tmp_path / "v8" / "out" / "tot" / "d8"
    d8.parent.mkdir(parents=True, exist_ok=True)
    d8.write_text("#!/bin/bash\necho fine\nexit 0\n")
    d8.chmod(0o755)
    tot.save_state({"status": "ok", "sha": "y" * 40, "d8": str(d8), "built_at": 1.0})
    f = tmp_path / "repro.js"
    f.write_text("print(1)")
    rec = tot.verify(str(f))
    assert rec["verdict"] == "CLEAN"
    lines = (tmp_path / "store" / "tot" / "verifications.jsonl").read_text().strip().splitlines()
    assert json.loads(lines[-1])["verdict"] == "CLEAN"
