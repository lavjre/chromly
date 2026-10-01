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


def _fake_lf_binary(tmp_path: Path, mode: str) -> Path:
    b = tmp_path / "v8" / "out" / "libfuzzer" / "v8_simple_parser_fuzzer"
    b.parent.mkdir(parents=True)
    if mode == "content":
        b.write_text(
            '#!/bin/bash\nfound=0\nfor f in "$@"; do grep -q BAD "$f" && found=1; done\n'
            'if [ "$found" -eq 1 ]; then\n'
            '  echo "ERROR: AddressSanitizer: heap-buffer-overflow"; exit 1\n'
            "fi\nexit 0\n"
        )
    else:  # batch-only: chỉ nổ khi chạy nhiều file
        b.write_text(
            '#!/bin/bash\nif [ "$#" -gt 1 ]; then echo "collective boom"; exit 1; fi\nexit 0\n'
        )
    b.chmod(0o755)
    return b


def test_replay_bisect_saves_flat_crash(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _fake_lf_binary(tmp_path, "content")
    corpus = tmp_path / "fuzz" / "libfuzzer-parser" / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "a.js").write_text("print(1);\n")
    (corpus / "b.js").write_text("this is BAD\n")

    res = replay.lfreplay_once("libfuzzer-parser")
    assert res["crashes"] >= 1
    artifacts = tmp_path / "fuzz" / "libfuzzer-parser" / "artifacts"
    flat = [p for p in artifacts.iterdir() if p.name.startswith("crash-") and p.suffix == ".js"]
    assert len(flat) == 1 and flat[0].name.endswith("-b.js")
    logs = [p for p in artifacts.iterdir() if p.name.endswith(".js.log")]
    assert logs
    assert not [p for p in artifacts.iterdir() if p.is_dir() and p.name.startswith("replay-")]


def test_replay_bisect_fallback_dir_for_collective(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _fake_lf_binary(tmp_path, "batch")
    corpus = tmp_path / "fuzz" / "libfuzzer-parser" / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "a.js").write_text("print(1);\n")
    (corpus / "b.js").write_text("print(2);\n")

    res = replay.lfreplay_once("libfuzzer-parser")
    assert res["crashes"] >= 1
    artifacts = tmp_path / "fuzz" / "libfuzzer-parser" / "artifacts"
    dirs = [p for p in artifacts.iterdir() if p.is_dir() and p.name.startswith("replay-")]
    assert dirs, "fallback phải lưu nguyên chunk khi không tìm ra thủ phạm đơn lẻ"
