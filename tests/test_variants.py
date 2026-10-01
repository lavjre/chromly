import json
from pathlib import Path

from chromly import paths
from chromly.intel import variants


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(variants, "intel_dir", lambda: tmp_path / "store" / "intel")


def _fake_d8(tmp_path: Path) -> Path:
    d8 = tmp_path / "v8" / "out" / "asan" / "d8"
    d8.parent.mkdir(parents=True)
    d8.write_text(
        "#!/bin/bash\n"
        'if grep -q FLAGERR "$2"; then\n'
        '  echo "Flag processing error: Contradictory value for readonly flag;"\n'
        "  exit 134\n"
        "fi\n"
        'if grep -q CRASH "$2"; then exit 134; fi\n'
        "echo ok\n"
        "exit 0\n"
    )
    d8.chmod(0o755)
    return d8


def test_generate_and_run(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _fake_d8(tmp_path)
    sha = "d" * 40
    d = variants.intel_dir() / sha
    d.mkdir(parents=True)
    (d / "variants.json").write_text(
        json.dumps(
            [
                {"title": "v-ok", "confidence": "high", "test_js": "print('hello');"},
                {"title": "v-crash", "confidence": "med", "test_js": "// CRASH\nprint(1);"},
                {"title": "v-empty", "confidence": "low", "test_js": ""},
            ]
        )
    )

    generated = variants.generate_for(sha)
    assert len(generated) == 2  # v-empty bị bỏ

    summary = variants.run_variants(sha)
    assert summary["generated"] == 2
    assert summary["builds"] == ["asan"]
    outcomes = {r["title"]: r["outcome"] for r in summary["results"]}
    assert outcomes["v-ok"] == "ok"
    assert outcomes["v-crash"] == "crash"
    assert (d / "variant-results.json").is_file()


def test_generate_no_variants(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    assert variants.generate_for("a" * 40) == []


def test_flag_conflict_not_crash(monkeypatch, tmp_path: Path) -> None:
    """Readonly-flag abort của d8 không được tính là crash / không vào crash store."""
    _setup(monkeypatch, tmp_path)
    _fake_d8(tmp_path)
    sha = "f" * 40
    d = variants.intel_dir() / sha
    d.mkdir(parents=True)
    (d / "variants.json").write_text(
        json.dumps([{"title": "v-flag", "confidence": "high", "test_js": "// FLAGERR\nprint(1);"}])
    )

    variants.generate_for(sha)
    summary = variants.run_variants(sha)
    assert summary["results"][0]["outcome"] == "flag-conflict"

    from chromly.store import db

    con = db.ensure_db()
    n = con.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()["n"]
    assert n == 0, "flag-conflict không được tạo crash row"
