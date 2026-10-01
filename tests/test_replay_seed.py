import hashlib
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm, replay


def _setup(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    delta = tmp_path / "store" / "regress-audit" / "tests" / "test" / "mjsunit"
    delta.mkdir(parents=True)
    (delta / "a.js").write_text("// a\n")
    (delta / "b.js").write_text("// b\n")
    return delta


def test_seed_delta_and_dedup(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    n1 = replay.seed_corpus("libfuzzer-parser")
    assert n1 == 2
    corpus = tmp_path / "fuzz" / "libfuzzer-parser" / "corpus"
    names = sorted(p.name for p in corpus.iterdir())
    assert all("-" in n and n.endswith(".js") for n in names)
    # lần 2: dedup → 0 thêm
    assert replay.seed_corpus("libfuzzer-parser") == 0
    # wasm: không seed
    assert replay.seed_corpus("libfuzzer-wasm") == 0


def test_seed_name_has_hash_prefix(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    replay.seed_corpus("libfuzzer-parser")
    data = b"// a\n"
    want = f"{hashlib.sha256(data).hexdigest()[:12]}-a.js"
    corpus = tmp_path / "fuzz" / "libfuzzer-parser" / "corpus"
    assert (corpus / want).is_file()


def test_seed_no_delta_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")  # không có regress-audit
    assert replay.seed_corpus("libfuzzer-parser") == 0
