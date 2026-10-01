from pathlib import Path

from chromly import paths
from chromly.fuzz import diffopt
from chromly.store import db


def _r(rc, out):
    return {"rc": rc, "out": out}


def test_compare_truth_table() -> None:
    # ổn định + khác nhau → báo
    assert diffopt.compare(_r(0, "x"), _r(0, "x"), _r(1, "x"), _r(1, "x")) is True
    assert diffopt.compare(_r(0, "a"), _r(0, "a"), _r(0, "b"), _r(0, "b")) is True
    # không ổn định → không báo
    assert diffopt.compare(_r(0, "a"), _r(0, "c"), _r(0, "b"), _r(0, "b")) is False
    assert diffopt.compare(_r(0, "a"), _r(0, "a"), _r(0, "b"), _r(0, "z")) is False
    # giống nhau → không báo
    assert diffopt.compare(_r(0, "x"), _r(0, "x"), _r(0, "x"), _r(0, "x")) is False


def _fake_d8(tmp_path: Path, script: str) -> Path:
    d8 = tmp_path / "v8" / "out" / "release" / "d8"
    d8.parent.mkdir(parents=True, exist_ok=True)
    d8.write_text(script)
    d8.chmod(0o755)
    return d8


def _diff_noopt(tmp_path: Path) -> Path:
    return _fake_d8(
        tmp_path,
        "#!/bin/bash\n"
        'if [[ "$*" == *"--no-opt"* ]]; then echo "NOOPT"; else echo "OPT"; fi\n'
        "exit 0\n",
    )


def _fake_corpus(monkeypatch, tmp_path: Path, n: int = 2) -> None:
    monkeypatch.setattr(diffopt.farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    corpus = tmp_path / "fuzz" / "fuzzilli" / "corpus"
    corpus.mkdir(parents=True)
    for i in range(n):
        (corpus / f"program_{i}.js").write_text(f"print({i});\n")


def test_diffopt_detects_and_saves(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path)
    _diff_noopt(tmp_path)
    s = diffopt.run_diffopt(limit=2, axes=[("no-opt", ["--no-opt"])])
    assert s["sampled"] == 2
    assert s["diffs"] == 2
    art = Path(s["artifact_dir"])
    assert art.is_dir()
    one = next(art.iterdir())
    assert (one / "program.js").is_file()
    assert "NOOPT" in (one / "b1.txt").read_text()
    # finding vào crash store + DB (source diffopt)
    con = db.ensure_db()
    n = con.execute("SELECT COUNT(*) AS n FROM crashes WHERE source = 'diffopt'").fetchone()["n"]
    con.close()
    assert n == 2


def test_diffopt_stable_same_no_diff(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path)
    _fake_d8(tmp_path, '#!/bin/bash\necho "SAME"\nexit 0\n')
    s = diffopt.run_diffopt(limit=2)
    assert s["diffs"] == 0


def test_diffopt_axis_rotation(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path, n=2)
    _fake_d8(
        tmp_path,
        "#!/bin/bash\n"
        'if [[ "$*" == *"--no-sparkplug"* ]]; then echo "NOSPARK"; else echo "OPT"; fi\n'
        "exit 0\n",
    )
    # program 0 → no-opt (không đổi gì), program 1 → no-sparkplug (diff)
    s = diffopt.run_diffopt(limit=2, axes=diffopt.AXES)
    assert s["diffs"] == 1


def test_diffopt_cursor_and_dedup(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path, n=3)
    _diff_noopt(tmp_path)
    s1 = diffopt.run_diffopt(limit=2, axes=[("no-opt", ["--no-opt"])])
    assert s1["sampled"] == 2 and s1["diffs"] == 2
    assert diffopt._load_state()["cursor"].startswith("program_1")
    # lượt 2: tiếp tục từ cursor → program_2 (mới, diff) + wrap program_0 (dedup)
    s2 = diffopt.run_diffopt(limit=2, axes=[("no-opt", ["--no-opt"])])
    assert s2["sampled"] == 2
    assert s2["diffs"] == 1
    # lượt 3: program_1 + program_2 đều đã có trong found.json → không báo lại
    s3 = diffopt.run_diffopt(limit=2, axes=[("no-opt", ["--no-opt"])])
    assert s3["diffs"] == 0


def test_diffopt_timeout_not_a_diff(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path, n=1)
    _fake_d8(
        tmp_path,
        '#!/bin/bash\nif [[ "$*" == *"--no-opt"* ]]; then sleep 30; fi\nexit 0\n',
    )
    s = diffopt.run_diffopt(limit=1, axes=[("no-opt", ["--no-opt"])], timeout=1)
    assert s["diffs"] == 0


def test_diffopt_release_crash_filed(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path, n=1)
    _fake_d8(tmp_path, "#!/bin/bash\necho boom\nexit 139\n")
    s = diffopt.run_diffopt(limit=1)
    assert s["crashes"] == 1
    con = db.ensure_db()
    row = con.execute("SELECT fault_type, source FROM crashes WHERE source = 'diffopt'").fetchone()
    con.close()
    assert row is not None and row["fault_type"] == "release-crash"


def test_run_once_normalizes_addresses(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path, n=1)
    _fake_d8(tmp_path, '#!/bin/bash\necho "ptr=0xdeadbeef1a2b"\nexit 0\n')
    d8 = tmp_path / "v8" / "out" / "release" / "d8"
    prog = tmp_path / "fuzz" / "fuzzilli" / "corpus" / "program_0.js"
    a = diffopt.run_once(d8, prog, [])
    assert "0xADDR" in a["out"] and "0xdeadbeef1a2b" not in a["out"]


def test_normalize_error_blocks() -> None:
    """Stack-overflow/attribution khác tier phải collapse; khác message thật vẫn giữ."""
    a = (
        "unnamed:3: RangeError: Maximum call stack size exceeded\n"
        "        function f6() {\n"
        "                   ^\n"
        "RangeError: Maximum call stack size exceeded\n"
        "    at f6 (unnamed:3:20)\n"
        "    at f6 (unnamed:4:20)\n"
    )
    b = a.replace("unnamed:3:", "unnamed:4:").replace("(unnamed:3:20)", "(unnamed:4:13)")
    b = b.replace("        function f6() {", "            return f6();")
    assert diffopt._normalize(a) == diffopt._normalize(b)
    c = a.replace("RangeError: Maximum call stack size exceeded", "TypeError: x is not a function")
    assert diffopt._normalize(a) != diffopt._normalize(c)


def test_normalize_dedupes_repeated_blocks() -> None:
    a = "TypeError: x\n\nTypeError: x\n\nTypeError: x\n"
    b = "TypeError: x\n"
    assert diffopt._normalize(a) == diffopt._normalize(b)


def test_diffopt_flaky_output_filtered(monkeypatch, tmp_path: Path) -> None:
    """Bên nào output đổi giữa các lần chạy → không bao giờ báo (lọc async race)."""
    _fake_corpus(monkeypatch, tmp_path, n=1)
    _fake_d8(
        tmp_path,
        "#!/bin/bash\n"
        'CNT="$0.cnt"\n'
        'n=$(cat "$CNT" 2>/dev/null || echo 0)\n'
        'echo $((n+1)) > "$CNT"\n'
        'if [ $((n % 2)) -eq 0 ]; then echo "OUT-A"; else echo "OUT-B"; fi\n'
        "exit 0\n",
    )
    s = diffopt.run_diffopt(limit=1, axes=[("no-opt", ["--no-opt"])])
    assert s["diffs"] == 0
