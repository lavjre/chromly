from pathlib import Path

from chromly import paths
from chromly.fuzz import diffopt


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


def _fake_d8(tmp_path: Path, diff: bool) -> Path:
    d8 = tmp_path / "v8" / "out" / "release" / "d8"
    d8.parent.mkdir(parents=True)
    if diff:
        d8.write_text(
            "#!/bin/bash\n"
            'if [[ "$*" == *"--no-opt"* ]]; then echo "NOOPT"; else echo "OPT"; fi\n'
            "exit 0\n"
        )
    else:
        d8.write_text('#!/bin/bash\necho "SAME"\nexit 0\n')
    d8.chmod(0o755)
    return d8


def _fake_corpus(monkeypatch, tmp_path: Path, n: int = 2) -> None:
    monkeypatch.setattr(diffopt.farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    corpus = tmp_path / "fuzz" / "fuzzilli" / "corpus"
    corpus.mkdir(parents=True)
    for i in range(n):
        (corpus / f"program_{i}.js").write_text(f"print({i});\n")


def test_diffopt_detects_and_saves(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path)
    _fake_d8(tmp_path, diff=True)
    s = diffopt.run_diffopt(limit=2)
    assert s["sampled"] == 2
    assert s["diffs"] == 2
    art = Path(s["artifact_dir"])
    assert art.is_dir()
    one = next(art.iterdir())
    assert (one / "program.js").is_file()
    assert "NOOPT" in (one / "b1.txt").read_text()


def test_diffopt_stable_same_no_diff(monkeypatch, tmp_path: Path) -> None:
    _fake_corpus(monkeypatch, tmp_path)
    _fake_d8(tmp_path, diff=False)
    s = diffopt.run_diffopt(limit=2)
    assert s["diffs"] == 0
