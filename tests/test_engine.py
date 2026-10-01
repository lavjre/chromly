"""Engine mode M1-08 — parse ninja + cmd + seed/wiring (không cần process thật)."""

import shlex
from pathlib import Path

from chromly.fuzz import engine, farm

NINJA_SAMPLE = """\
defines = -D_GNU_SOURCE -DCR_CLANG_REVISION=\\"llvmorg-24\\"
ldflags = -pie -fPIC -Wl,-rpath=\\$$ORIGIN -fsanitize=address
libs = builtins.a -ldl -lpthread
solibs = ./libsanitizer_shared_hooks.so
rlibs = a.rlib b.rlib

build obj/v8_simple_parser_fuzzer/fuzzer.o obj/v8_simple_parser_fuzzer/fuzzer.dwo: cxx ../../test/fuzzer/fuzzer.cc || phony/x
build ./v8_simple_parser_fuzzer: link obj/v8_simple_parser_fuzzer/fuzzer.o obj/parser_fuzzer/parser.o obj/foo.a | ./hooks.so.TOC || phony/y
"""


def _fake_out(tmp_path: Path, monkeypatch) -> Path:
    out = tmp_path / "out"
    (out / "obj").mkdir(parents=True)
    (out / "obj" / "v8_simple_parser_fuzzer.ninja").write_text(NINJA_SAMPLE)
    monkeypatch.setattr(engine, "out_dir", lambda: out)
    return out


def test_unescape_ninja_dollar() -> None:
    assert engine._unescape("a$$b") == "a$b"
    assert engine._unescape("rpath=\\$$ORIGIN") == "rpath=\\$ORIGIN"
    assert engine._unescape("x$ y") == "x y"


def test_parse_ninja(tmp_path: Path, monkeypatch) -> None:
    _fake_out(tmp_path, monkeypatch)
    parsed = engine._parse_ninja("parser")
    # binding kiểu edge (thụt lề) đọc được
    assert parsed["libs"] == "builtins.a -ldl -lpthread"
    assert parsed["_explicit"] == [
        "obj/v8_simple_parser_fuzzer/fuzzer.o",
        "obj/parser_fuzzer/parser.o",
        "obj/foo.a",
    ]
    assert parsed["_implicit"] == ["./hooks.so.TOC"]
    # ninja `$$` → `$`; shlex ăn `\$` → token rpath đúng
    assert shlex.split(parsed["ldflags"]) == [
        "-pie",
        "-fPIC",
        "-Wl,-rpath=$ORIGIN",
        "-fsanitize=address",
    ]


def test_parse_ninja_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engine, "out_dir", lambda: tmp_path / "empty")
    try:
        engine._parse_ninja("parser")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("phải raise FileNotFoundError")


def test_parse_ninja_no_link_edge(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    (out / "obj").mkdir(parents=True)
    (out / "obj" / "v8_simple_parser_fuzzer.ninja").write_text("defines = -D_X\n")
    monkeypatch.setattr(engine, "out_dir", lambda: out)
    try:
        engine._parse_ninja("parser")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("phải raise ValueError")


def test_lfuzz_cmd(tmp_path: Path) -> None:
    cmd = engine._lfuzz_cmd(
        tmp_path / "bin",
        tmp_path / "corpus",
        tmp_path / "artifacts",
        seconds=120,
        timeout_s=7,
        rss_mb=1024,
    )
    assert cmd[0] == str(tmp_path / "bin")
    assert "-max_total_time=120" in cmd
    assert "-timeout=7" in cmd
    assert "-rss_limit_mb=1024" in cmd
    assert "-detect_leaks=0" in cmd
    assert f"-artifact_prefix={tmp_path / 'artifacts'}/" in cmd
    assert cmd[-1] == str(tmp_path / "corpus")


def test_units_mapping() -> None:
    assert engine.LFUZZ_UNITS == {"lfuzz-parser": "parser", "lfuzz-wasm": "wasm_module"}
    assert engine.engine_bin("parser").name == "v8_engine_parser_fuzzer"
    assert engine.engine_bin("wasm_module").name == "v8_engine_wasm_module_fuzzer"


def test_run_lfuzz_bad_unit() -> None:
    assert engine.run_lfuzz("không-tồn-tại", once=True) == 2


def test_seed_corpus_copies_replay(tmp_path: Path, monkeypatch) -> None:
    from chromly.fuzz import replay

    fuzz = tmp_path / "fuzz"
    src = fuzz / "libfuzzer-parser" / "corpus"
    src.mkdir(parents=True)
    (src / "a.js").write_text("var a = 1;")
    (src / "b.js").write_text("var b = 2;")
    monkeypatch.setattr(farm, "FUZZ_DIR", fuzz)
    monkeypatch.setattr(replay, "seed_corpus", lambda unit: 0)

    assert engine.seed_corpus("lfuzz-parser") == 2
    dest = fuzz / "lfuzz-parser" / "corpus"
    assert (dest / "a.js").is_file() and (dest / "b.js").is_file()
    # idempotent — lượt 2 không copy lại
    assert engine.seed_corpus("lfuzz-parser") == 0


def test_seed_corpus_wasm(tmp_path: Path, monkeypatch) -> None:
    from chromly.fuzz import replay

    fuzz = tmp_path / "fuzz"
    src = fuzz / "libfuzzer-wasm" / "corpus"
    src.mkdir(parents=True)
    (src / "m.wasm").write_bytes(b"\x00asm")
    monkeypatch.setattr(farm, "FUZZ_DIR", fuzz)
    monkeypatch.setattr(replay, "seed_corpus", lambda unit: 0)
    assert engine.seed_corpus("lfuzz-wasm") == 1


def test_engine_units_skip_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "fuzz" / "logs")
    monkeypatch.setattr(engine, "engine_bin", lambda fuzzer: tmp_path / "missing")
    assert farm.engine_units() == []


def test_engine_units_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "fuzz")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "fuzz" / "logs")
    fake = tmp_path / "engine-bin"
    fake.write_bytes(b"")
    monkeypatch.setattr(engine, "engine_bin", lambda fuzzer: fake)
    units = farm.engine_units()
    assert {u.name for u in units} == set(engine.LFUZZ_UNITS)
    for u in units:
        assert u.cmd[-1] == u.name
        assert "lfuzz" in u.cmd
        assert (tmp_path / "fuzz" / u.name / "corpus").is_dir()


def test_crashes_sources_include_lfuzz(tmp_path: Path, monkeypatch) -> None:
    from chromly.fuzz import crashes

    base = tmp_path / "fuzz"
    for name in ("lfuzz-parser", "lfuzz-wasm"):
        (base / name / "artifacts").mkdir(parents=True)
    monkeypatch.setattr(farm, "FUZZ_DIR", base)
    src = crashes._sources()
    assert "lfuzz-parser" in src and "lfuzz-wasm" in src


def test_execs_regex_matches_engine_pulse() -> None:
    line = "#1843\tNEW    cov: 14255 ft: 31250 corp: 299/281Kb lim: 2061 exec/s: 307 rss: 352Mb"
    m = farm._EXECS_RE.search(line)
    assert m is not None and float(m.group(1)) == 307.0
