from chromly.intel import recon


def test_classify_surface_v8() -> None:
    assert recon.classify_surface("v8", ["src/maglev/foo.cc"]) == "jit"
    assert recon.classify_surface("v8", ["src/regexp/regexp.cc"]) == "regexp"
    assert recon.classify_surface("v8", ["src/wasm/baseline/x.cc"]) == "wasm"
    assert recon.classify_surface("v8", ["docs/readme.md"]) == "other"


def test_classify_surface_chromium() -> None:
    assert recon.classify_surface("chromium", ["third_party/blink/renderer/x.cc"]) == "blink"
    assert recon.classify_surface("chromium", ["mojo/core/x.cc"]) == "mojo-ipc"
    assert recon.classify_surface("chromium", ["v8/src/maglev/y.cc"]) == "v8:jit"


def test_guess_bug_class() -> None:
    assert recon.guess_bug_class("Fix use-after-free in X") == "use-after-free"
    assert recon.guess_bug_class("Harden bounds check") == "oob"
    assert recon.guess_bug_class("Fix crash in parser") == "crash-other"
    assert recon.guess_bug_class("Update docs") == "other"


def test_surface_report_renders(monkeypatch, tmp_path) -> None:
    from chromly import paths

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    # archaeology fixture
    d = recon.recon_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "archaeology-v8.json").write_text(
        __import__("json").dumps(
            {
                "mirror": "v8",
                "days": 90,
                "counts": {"jit": 3, "wasm": 1},
                "records": [
                    {"surface": "jit", "bug_class": "oob"},
                    {"surface": "jit", "bug_class": "type-confusion"},
                    {"surface": "jit", "bug_class": "oob"},
                    {"surface": "wasm", "bug_class": "oob"},
                ],
            }
        )
    )
    from chromly.store import db

    con = db.ensure_db()
    with con:
        con.execute(
            'INSERT INTO intel ("commit", paths, review_status, variant_flag, source) '
            "VALUES ('x', '[\"src/maglev/a.cc\"]', 'pending', 0, 'v8')"
        )
    con.close()

    p = recon.surface_report()
    text = p.read_text()
    assert "SURFACE report".lower() in text.lower()
    assert "jit" in text
    assert "wasm" in text
