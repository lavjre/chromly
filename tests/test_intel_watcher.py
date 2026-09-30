import subprocess
from pathlib import Path

from chromly import paths
from chromly.intel import watcher
from chromly.store import db


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_origin(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    bare = tmp_path / "origin.git"
    work.mkdir()
    _git(["init", "-q", "-b", "main"], work)
    _git(["config", "user.email", "t@t"], work)
    _git(["config", "user.name", "t"], work)
    (work / "src" / "jit").mkdir(parents=True)
    (work / "docs").mkdir()
    (work / "src" / "jit" / "a.cc").write_text("int x;")
    _git(["add", "."], work)
    _git(["commit", "-q", "-m", "Fix bounds check in JIT"], work)
    (work / "docs" / "readme.md").write_text("hi")
    _git(["add", "."], work)
    _git(["commit", "-q", "-m", "Update docs"], work)
    _git(["init", "-q", "--bare", "-b", "main", str(bare)], tmp_path)
    _git(["push", "-q", str(bare), "main"], work)
    return bare


def test_match_commit() -> None:
    assert watcher.match_commit("whatever", ["src/jit/foo.cc"])
    assert watcher.match_commit("Fix crash in regexp", ["test/foo.js"])
    assert not watcher.match_commit("Update docs", ["docs/readme.md"])


def test_parse_lag() -> None:
    lag = watcher.parse_lag_hours("2020-01-01T00:00:00+00:00")
    assert lag is not None and lag > 0
    assert watcher.parse_lag_hours("not-a-date") is None


def test_poll_local(monkeypatch, tmp_path: Path) -> None:
    bare = _make_origin(tmp_path)
    monkeypatch.setattr(watcher, "mirror_dir_for", lambda name: tmp_path / f"mirror-{name}")
    monkeypatch.setitem(watcher.MIRRORS["v8"], "url", str(bare))
    monkeypatch.setattr(watcher, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(watcher, "intel_dir", lambda: tmp_path / "intel")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")

    res = watcher.poll_once()
    assert res["seen"] == 2
    assert res["matched"] >= 1
    assert res["new"] >= 1

    res2 = watcher.poll_once()
    assert res2["new"] == 0

    con = db.ensure_db()
    n = con.execute("SELECT COUNT(*) AS n FROM intel").fetchone()["n"]
    assert n == res["new"]
    con.close()
