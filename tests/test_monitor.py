import json
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm
from chromly.store import db
from chromly.telemetry import monitor


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(paths, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "store" / "fuzz")
    monkeypatch.setattr(farm, "STATE_PATH", tmp_path / "store" / "fuzz" / "state.json")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "store" / "fuzz" / "logs")


def test_collect_fuzz_and_plugin(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    store = tmp_path / "store"
    (store / "fuzz").mkdir(parents=True)
    (store / "logs").mkdir(parents=True)
    now = time.time()
    (store / "fuzz" / "events.jsonl").write_text(
        json.dumps({"ts": now - 10, "event": "restart", "unit": "fuzzilli"}) + "\n"
    )
    (store / "logs" / "plugin-events.jsonl").write_text(
        json.dumps({"ts": (now - 5) * 1000, "event": "deny", "scope": "agent", "cmd": "sudo true"})
        + "\n"
        + json.dumps({"ts": now * 1000, "event": "plugin-loaded", "directory": "/x"})
        + "\n"
    )
    ev = monitor.collect(now - 60, include_aux=False)
    sources = {e["source"] for e in ev}
    assert "watchdog" in sources
    assert "deny" in sources
    assert "plugin-loaded" not in sources  # bootstrap noise bị lọc
    deny = [e for e in ev if e["source"] == "deny"][0]
    assert "sudo" in deny["text"]
    # ts ms → giây
    assert abs(deny["ts"] - (now - 5)) < 1


def test_db_events(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, source, state) "
            "VALUES ('abcd', 'x', 5, 'v', 'triaged')"
        )
    con.close()
    ev = monitor.db_events(time.time() - 3600)
    assert any(e["source"] == "crash" and "abcd" in e["text"] for e in ev)


def test_source_filter(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    store = tmp_path / "store"
    (store / "fuzz").mkdir(parents=True)
    now = time.time()
    (store / "fuzz" / "events.jsonl").write_text(
        json.dumps({"ts": now - 5, "event": "restart", "unit": "u"}) + "\n"
    )
    ev = monitor.collect(now - 60, include_aux=False, sources={"crash"})
    assert ev == []


def test_render_event_format() -> None:
    e = {"ts": 1700000000, "source": "watchdog", "text": "restart fuzzilli"}
    s = monitor.render_event(e, color=False)
    assert "[watchdog" in s and "restart fuzzilli" in s


def test_render_info_smoke(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    out = monitor.render_info(color=False)
    assert "══ chromly info" in out
    lines = out.splitlines()
    assert any(ln.startswith("FARM") for ln in lines)
    assert any(ln.startswith("INTEL") for ln in lines)
    assert any(ln.startswith("CASES") for ln in lines)
    assert any(ln.startswith("CRASH") for ln in lines)


def test_corpus_counts(monkeypatch, tmp_path) -> None:
    from chromly.fuzz import farm
    from chromly.telemetry import monitor

    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    for sub in ("lfuzz-parser/corpus", "lfuzz-wasm/corpus"):
        d = tmp_path / "fuzz" / sub
        d.mkdir(parents=True)
        (d / "a").write_text("x")
        (d / "b").write_text("x")
    fz = tmp_path / "fuzz" / "fuzzilli" / "corpus"
    fz.mkdir(parents=True)
    (fz / "p1.js").write_text("x")
    (fz / "p1.fzil").write_text("x")  # không tính
    (fz / "p2.js").write_text("x")
    monkeypatch.setattr(monitor, "_CORPUS_CACHE", {})
    rows = dict(monitor._corpus_counts())
    assert rows == {"lfuzz-parser": 2, "lfuzz-wasm": 2, "fuzzilli": 2}
    # cache: thêm file nhưng gọi lại trong 60s vẫn số cũ
    (tmp_path / "fuzz" / "lfuzz-wasm" / "corpus" / "c").write_text("x")
    assert dict(monitor._corpus_counts())["lfuzz-wasm"] == 2


def test_fmt_count() -> None:
    from chromly.telemetry import monitor

    assert monitor._fmt_count(999) == "999"
    assert monitor._fmt_count(11_800) == "11.8k"
