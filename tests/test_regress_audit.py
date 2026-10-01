from pathlib import Path

from chromly import paths
from chromly.intel import regress_audit


def _fake_d8(tmp_path: Path) -> Path:
    d8 = tmp_path / "v8" / "out" / "calib" / "d8"
    d8.parent.mkdir(parents=True)
    d8.write_text(
        "#!/bin/bash\n"
        'T="${@: -1}"\n'
        'if grep -q FLAGERR "$T"; then\n'
        '  echo "Flag processing error: Contradictory value for readonly flag;"\n'
        "  exit 134\n"
        "fi\n"
        'if grep -q CRASHME "$T"; then echo "# Fatal error in x.cc, line 1"; exit 134; fi\n'
        'if grep -q FAILME "$T"; then echo "MjsUnitAssertionError"; exit 1; fi\n'
        "echo ok\n"
        "exit 0\n"
    )
    d8.chmod(0o755)
    return d8


def test_parse_flags() -> None:
    src = "// Flags: --expose-gc --allow-natives-syntax\n// Flags: --no-turbolev\nprint(1);\n"
    assert regress_audit.parse_flags(src) == ["--expose-gc", "--no-turbolev"]


def test_outcomes(monkeypatch, tmp_path: Path) -> None:
    _fake_d8(tmp_path)
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")

    cases = {
        "ok.js": ("print(1);", "ok"),
        "crash.js": ("// CRASHME\nprint(1);", "crash"),
        "fail.js": ("// FAILME\nprint(1);", "fail"),
        "flag.js": ("// FLAGERR\nprint(1);", "flag-conflict"),
    }
    for name, (source, want) in cases.items():
        f = tmp_path / name
        f.write_text(source)
        res = regress_audit.run_test(f, source)
        assert res["outcome"] == want, (name, res)


def test_file_crash_store(monkeypatch, tmp_path: Path) -> None:
    _fake_d8(tmp_path)
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")

    src = "// CRASHME\nprint(1);"
    f = tmp_path / "regress-test.js"
    f.write_text(src)
    res = {"rc": 134, "outcome": "crash", "output_tail": "# Fatal error\n", "flags": []}
    h = regress_audit._file_crash(f, src, "f" * 40, res)
    assert (tmp_path / "store" / "crashes" / h / "meta.json").is_file()
    assert (tmp_path / "store" / "triage" / h / "asan.txt").is_file()

    from chromly.store import db

    con = db.ensure_db()
    row = con.execute("SELECT source, state FROM crashes WHERE hash = ?", (h,)).fetchone()
    assert row["source"] == "upstream-regress"
    assert row["state"] == "triaged"
    con.close()


def test_audit_dir_under_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    assert regress_audit.audit_dir() == tmp_path / "store" / "regress-audit"
