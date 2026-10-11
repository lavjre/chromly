"""Tests cho source-review lane: hotspot mining + flow agent → variants → crash store."""

from __future__ import annotations

import json
import types
from pathlib import Path

from chromly import paths


def test_hotspots_ranks_by_fix_count(monkeypatch, tmp_path: Path) -> None:
    from chromly.intel import srcreview as SR

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    rec = tmp_path / "store" / "recon"
    rec.mkdir(parents=True)
    (rec / "archaeology-v8.json").write_text(
        json.dumps(
            {
                "records": [
                    {"surface": "jit", "paths": ["src/maglev/a.cc", "src/b.cc"]},
                    {"surface": "wasm", "paths": ["src/maglev/a.cc"]},
                    {"surface": "other", "paths": ["test/x.js", "src/maglev/a.cc"]},
                    {"surface": "other", "paths": ["src/gone.cc"]},
                ]
            }
        )
    )
    (tmp_path / "v8" / "src" / "maglev").mkdir(parents=True)
    (tmp_path / "v8" / "src" / "maglev" / "a.cc").write_text("// a")
    (tmp_path / "v8" / "src" / "b.cc").write_text("// b")
    rows = SR.hotspots(top=10)
    assert [r["path"] for r in rows] == ["src/maglev/a.cc", "src/b.cc"]
    assert rows[0]["count"] == 3
    assert rows[0]["surfaces"] == ["jit", "other", "wasm"]
    # file không tồn tại trong snapshot bị loại; test/ không phải src/
    assert all(r["path"] not in ("src/gone.cc", "test/x.js") for r in rows)


def test_srcreview_flow_files_crash(monkeypatch, tmp_path: Path) -> None:
    from chromly.intel import srcreview as SR
    from chromly.intel import variants as V
    from chromly.orchestrator import agents as agents_mod

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(SR, "SCRATCH_ROOT", tmp_path / "scratch")

    src = tmp_path / "v8" / "src" / "x.cc"
    src.parent.mkdir(parents=True)
    src.write_text("// x")

    monkeypatch.setattr(agents_mod, "find_opencode", lambda: "/usr/bin/true")
    monkeypatch.setattr(
        agents_mod,
        "parse_session_usage",
        lambda out: {"cost_est": 0.0, "tokens_in": 0, "tokens_out": 0},
    )

    def fake_run(cmd, cwd=None, **kw):
        cwd = Path(cwd)
        (cwd / "review.md").write_text("# review")
        (cwd / "variants.json").write_text("[]")

        class P:
            stdout = "ses_test\n"
            stderr = ""
            returncode = 0

        return P()

    monkeypatch.setattr(SR, "subprocess", types.SimpleNamespace(run=fake_run))

    monkeypatch.setattr(
        V, "generate_for", lambda slug: [{"file": "variant-1.js", "title": "t", "variant": {}}]
    )
    monkeypatch.setattr(V, "tests_dir_for", lambda slug: tmp_path / "tests")
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(
        V, "run_test", lambda d8, test: {"rc": 133, "outcome": "crash", "output_tail": "x"}
    )
    d8 = tmp_path / "v8" / "out" / "asan" / "d8"
    d8.parent.mkdir(parents=True)
    d8.write_bytes(b"")

    filed: list[tuple] = []
    monkeypatch.setattr(
        V,
        "_file_variant_crash",
        lambda slug, r, source="variant": filed.append((slug, r["variant"], source)),
    )

    res = SR.run_srcreview("src/x.cc", limit=2)
    assert res["status"] == "reviewed"
    assert res["generated"] == 1
    assert res["crashes"] == 1
    assert filed == [(SR.slug_for("src/x.cc"), "variant-1.js", "srcreview")]
    idx = SR.load_index()
    assert idx["src/x.cc"]["crashes"] == 1
    # scan lần sau bỏ qua file đã review
    assert SR.run_scan(top=5, limit=1) == []


def test_scan_retries_failed_once(monkeypatch, tmp_path: Path) -> None:
    """failed → retry 1 lần; reviewed/attempts≥2 → skip (bài học timeout 09/10)."""
    from chromly.intel import srcreview as SR

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(
        SR,
        "hotspots",
        lambda top=100: [{"path": "src/a.cc", "count": 3, "surfaces": ["jit"], "size_kb": 1}],
    )
    calls: list[str] = []

    def fake_review(path, limit=3):
        calls.append(path)
        return {"path": path, "status": "reviewed", "generated": 0, "crashes": 0}

    monkeypatch.setattr(SR, "run_srcreview", fake_review)

    # failed lần 1 (chưa có attempts) → retry
    SR.save_index({"src/a.cc": {"slug": "s", "status": "failed"}})
    SR.run_scan(top=1)
    assert calls == ["src/a.cc"]

    # failed lần 2 (attempts=2) → skip
    calls.clear()
    SR.save_index({"src/a.cc": {"slug": "s", "status": "failed", "attempts": 2}})
    SR.run_scan(top=1)
    assert calls == []

    # reviewed → skip
    SR.save_index({"src/a.cc": {"slug": "s", "status": "reviewed", "attempts": 1}})
    SR.run_scan(top=1)
    assert calls == []


def test_hotspots_excludes_arch_paths(monkeypatch, tmp_path: Path) -> None:
    """File arch-specific (arm64/riscv/s390...) không review — builds của ta là x64."""
    from chromly.intel import srcreview as SR

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    rec = tmp_path / "store" / "recon"
    rec.mkdir(parents=True)
    (rec / "archaeology-v8.json").write_text(
        json.dumps(
            {
                "records": [
                    {"surface": "jit", "paths": ["src/codegen/arm64/macro-assembler-arm64.cc"]},
                    {"surface": "jit", "paths": ["src/maglev/riscv/x.cc"]},
                    {
                        "surface": "jit",
                        "paths": ["src/compiler/backend/s390/code-generator-s390.cc"],
                    },
                    {"surface": "jit", "paths": ["src/maglev/good.cc"]},
                ]
            }
        )
    )
    for p in (
        "src/codegen/arm64/macro-assembler-arm64.cc",
        "src/maglev/riscv/x.cc",
        "src/compiler/backend/s390/code-generator-s390.cc",
        "src/maglev/good.cc",
    ):
        f = tmp_path / "v8" / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// x")
    rows = SR.hotspots(top=10)
    assert [r["path"] for r in rows] == ["src/maglev/good.cc"]
