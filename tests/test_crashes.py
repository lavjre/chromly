from pathlib import Path

from chromly import paths
from chromly.fuzz import crashes, farm, metrics
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(farm, "STATE_PATH", tmp_path / "fuzz" / "state.json")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "fuzz" / "logs")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    src = tmp_path / "fuzz" / "fuzzilli" / "crashes"
    src.mkdir(parents=True)
    return src


def test_ingest_new_and_dup(monkeypatch, tmp_path: Path) -> None:
    src = _setup(monkeypatch, tmp_path)
    (src / "crash-1.fzil").write_bytes(b"PROGRAM-A")

    res1 = crashes.ingest_once()
    assert len(res1) == 1
    assert res1[0]["dup"] is False

    # cùng nội dung, tên khác → dedup
    (src / "crash-2.fzil").write_bytes(b"PROGRAM-A")
    res2 = crashes.ingest_once()
    assert res2 and res2[0]["dup"] is True

    # nội dung mới → row mới
    (src / "crash-3.fzil").write_bytes(b"PROGRAM-B")
    res3 = crashes.ingest_once()
    assert res3 and res3[0]["dup"] is False

    con = db.ensure_db()
    total = con.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()["n"]
    maxdup = con.execute("SELECT MAX(dup_count) AS d FROM crashes").fetchone()["d"]
    con.close()
    assert total == 2
    assert maxdup == 2


def test_ingest_skips_seen(monkeypatch, tmp_path: Path) -> None:
    src = _setup(monkeypatch, tmp_path)
    (src / "crash-1.fzil").write_bytes(b"X")
    assert len(crashes.ingest_once()) == 1
    assert crashes.ingest_once() == []


def test_metrics_sample_and_total(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    sample = metrics.sample_once()
    assert sample["units"] == {}
    assert (tmp_path / "fuzz" / "metrics.jsonl").is_file()
    assert metrics.total_execs({}) == 0.0
    assert (
        metrics.total_execs({"a": {"execs_per_sec": 100.5}, "b": {"execs_per_sec": None}}) == 100.5
    )


def test_ingest_orphan_js_and_fzil_sidecar(monkeypatch, tmp_path: Path) -> None:
    import hashlib

    src = _setup(monkeypatch, tmp_path)
    # .js mồ côi (fuzzilli ghi .js trước .fzil — thoát giữa chừng) → phải được nhập
    (src / "program_orphan.js").write_text("print(1);")
    res1 = crashes.ingest_once()
    assert sum(1 for r in res1 if not r["dup"]) == 1

    # có .fzil sidecar → chỉ .fzil canonical, .js bị skip
    (src / "program_A.fzil").write_bytes(b"PB-A")
    (src / "program_A.js").write_text("print(2);")
    res2 = crashes.ingest_once()
    new = [r for r in res2 if not r["dup"]]
    assert len(new) == 1
    h = hashlib.sha256(b"PB-A").hexdigest()
    dest = paths.STORE_DIR / "crashes" / h
    assert (dest / "program_A.fzil").is_file()
    assert (dest / "program_A.js").is_file()  # sidecar được kèm theo


def test_ingest_only_standard_artifacts(tmp_path, monkeypatch) -> None:
    from chromly import paths as P
    from chromly.fuzz import crashes, farm
    from chromly.store import db

    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(P, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(P, "DB_PATH", tmp_path / "store" / "chromly.db")
    art = tmp_path / "fuzz" / "lfuzz-parser" / "artifacts"
    art.mkdir(parents=True)
    (art / "slow-unit-abc123").write_bytes(b"slow")
    (art / "crash-deadbeef").write_bytes(b"boom")
    res = crashes.ingest_once()
    assert len(res) == 1 and res[0]["unit"] == "lfuzz-parser"
    con = db.ensure_db()
    n = con.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()["n"]
    con.close()
    assert n == 1
