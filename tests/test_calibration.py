import subprocess
from pathlib import Path

from chromly import paths
from chromly.triage import calibration


def test_load_bugs_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(calibration, "bugs_path", lambda: tmp_path / "nope.json")
    assert calibration.load_bugs() == []


def test_calibrate_no_mirror(monkeypatch, tmp_path: Path) -> None:
    v8 = tmp_path / "v8"
    v8.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=v8, check=True)
    monkeypatch.setattr(paths, "V8_ROOT", v8)
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setattr(calibration, "mirror_dir", lambda: tmp_path / "mirror")

    res = calibration.calibrate({"id": "t", "fix_sha": "0" * 40, "repro_js": ""})
    assert res["status"] == "no-mirror"


def test_calibrate_tree_dirty(monkeypatch, tmp_path: Path) -> None:
    v8 = tmp_path / "v8"
    v8.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=v8, check=True)
    (v8 / "dirty.txt").write_text("x")  # untracked → porcelain không trống
    monkeypatch.setattr(paths, "V8_ROOT", v8)
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path / "repo")

    res = calibration.calibrate({"id": "t", "fix_sha": "0" * 40, "repro_js": ""})
    assert res["status"] == "tree-dirty"
