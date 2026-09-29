from pathlib import Path

from chromly.fuzz import farm


def test_fuzzilli_unit_cmd() -> None:
    unit = farm.fuzzilli_unit()
    assert unit.name == "fuzzilli"
    assert unit.type == "fuzzilli"
    assert "--profile=v8" in unit.cmd
    assert f"--jobs={farm.JOBS}" in unit.cmd
    assert any(str(c).startswith("--storagePath=") for c in unit.cmd)
    assert unit.cmd[-1].endswith("out/fuzzilli/d8")


def test_parse_execs(tmp_path: Path) -> None:
    log = tmp_path / "t.log"
    log.write_text("Execs/second: 12.5\nnoise\nExecs/second:    345.67\n")
    assert farm.parse_execs(log) == 345.67


def test_parse_execs_libfuzzer(tmp_path: Path) -> None:
    log = tmp_path / "t.log"
    log.write_text(
        "#65536\tpulse  exec/s: 32768 rss: 456Mb\n#68816\tpulse  exec/s: 34000 rss: 457Mb\n"
    )
    assert farm.parse_execs(log) == 34000.0


def test_latest_stats_execs(tmp_path: Path) -> None:
    storage = tmp_path / "fuzzilli"
    stats = storage / "stats"
    stats.mkdir(parents=True)
    (stats / "2026-09-29.json").write_text('{"execsPerSecond": 321.5, "totalExecs": 123456}')
    assert farm.latest_stats_execs(storage) == 321.5
    (stats / "2026-09-29.json").write_text("not json")
    assert farm.latest_stats_execs(storage) is None
    assert farm.latest_stats_execs(tmp_path / "nope") is None


def test_parse_execs_missing(tmp_path: Path) -> None:
    log = tmp_path / "t.log"
    log.write_text("no stats yet")
    assert farm.parse_execs(log) is None


def test_up_missing_binary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(farm, "STATE_PATH", tmp_path / "fuzz" / "state.json")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "fuzz" / "logs")
    unit = farm.Unit("fake", "fuzzilli", ["/nonexistent/FuzzilliCli"], tmp_path / "x.log")
    result = farm.up([unit])
    assert result["fake"]["status"] == "missing-binary"


def test_down_unknown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(farm, "STATE_PATH", tmp_path / "state.json")
    assert farm.down(["ghost"]) == {"ghost": "unknown"}
