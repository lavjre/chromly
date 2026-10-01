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


def _fake_d8_flag_retry(tmp_path: Path, flag: str) -> Path:
    d8 = tmp_path / "v8" / "out" / "asan" / "d8"
    d8.parent.mkdir(parents=True, exist_ok=True)
    d8.write_text(
        "#!/bin/bash\n"
        f'if [[ "$*" != *"{flag}"* ]]; then\n'
        f'  echo "WebAssembly.Module(): unknown type form: 101, enable with {flag}"\n'
        "  exit 0\n"
        "fi\n"
        "echo ok\n"
        "exit 0\n"
    )
    d8.chmod(0o755)
    return d8


def test_variant_missing_flag_retry(monkeypatch, tmp_path: Path) -> None:
    """'enable with --X' → tự chạy lại kèm flag; thành công thì outcome ok + flags_added."""
    d8 = _fake_d8_flag_retry(tmp_path, "--wasm-shared")
    test = tmp_path / "v.js"
    test.write_text("print(1);\n")
    res = variants.run_test(d8, test)
    assert res["outcome"] == "ok"
    assert res.get("flags_added") == ["--wasm-shared"]


def test_variant_missing_flag_still_skipped(monkeypatch, tmp_path: Path) -> None:
    """Flag không giúp được → outcome 'skipped' (không tính pass)."""
    d8 = tmp_path / "v8" / "out" / "asan" / "d8"
    d8.parent.mkdir(parents=True, exist_ok=True)
    d8.write_text('#!/bin/bash\necho "unknown type form: 101, enable with --other-flag"\nexit 0\n')
    d8.chmod(0o755)
    test = tmp_path / "v.js"
    test.write_text("print(1);\n")
    res = variants.run_test(d8, test)
    assert res["outcome"] == "skipped"


# ── manual-opt normalization + FP filter (bài học CASE-0005) ──


def test_normalize_inserts_prepare() -> None:
    js = "function hot(x){return x|0;}\nhot(1);\n%OptimizeFunctionOnNextCall(hot);\nhot(2);\n"
    out = variants._ensure_manual_opt_prepared(js)
    assert out.index("%PrepareFunctionForOptimization(hot)") < out.index(
        "%OptimizeFunctionOnNextCall(hot)"
    )


def test_normalize_keeps_existing_prepare() -> None:
    js = "%PrepareFunctionForOptimization(hot);\n%OptimizeFunctionOnNextCall(hot);\n"
    assert variants._ensure_manual_opt_prepared(js) == js


def test_normalize_multiple_calls() -> None:
    js = "%OptimizeFunctionOnNextCall(a);\n%OptimizeMaglevOnNextCall(b);\n"
    out = variants._ensure_manual_opt_prepared(js)
    assert "%PrepareFunctionForOptimization(a)" in out
    assert "%PrepareFunctionForOptimization(b)" in out


def test_normalize_skips_no_arg() -> None:
    js = "%OptimizeOsr();\n"
    assert variants._ensure_manual_opt_prepared(js) == js


def test_manual_opt_fp_filter(monkeypatch, tmp_path) -> None:
    from pathlib import Path as _P

    def fake_run(d8, test, extra):
        return 133, (
            "# Fatal error in ../../src/runtime/runtime-test.cc, line 357\n"
            "Check failed: CheckMarkedForManualOptimization(isolate, function).\n"
        )

    monkeypatch.setattr(variants, "_run_once", fake_run)
    res = variants.run_test(_P("/bin/true"), _P("/tmp/fake.js"))
    assert res["outcome"] == "fp-manual-opt"
