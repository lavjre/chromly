from pathlib import Path

from chromly import paths


def test_repo_root_layout() -> None:
    assert (paths.REPO_ROOT / "PLAN.md").is_file()
    assert paths.PKG_DIR.name == "chromly"
    assert paths.PKG_DIR.parent == paths.REPO_ROOT


def test_env_path_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHROMLY_TEST_X", str(tmp_path))
    assert paths._env_path("CHROMLY_TEST_X", Path("/nonexistent")) == tmp_path


def test_env_path_default() -> None:
    assert paths._env_path("CHROMLY_TEST_UNSET_XYZ", Path("/tmp/x")) == Path("/tmp/x")
