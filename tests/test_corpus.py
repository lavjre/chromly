import os
import time
from pathlib import Path

from chromly.fuzz import corpus


def test_sync_with_fake_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(corpus, "SEEDS_DIR", tmp_path / "fuzz" / "corpus" / "fzil")
    monkeypatch.setattr(corpus, "SRC_DIR", tmp_path / "fuzz" / "corpus" / "mjsunit-src")
    mjs = tmp_path / "mjsunit"
    mjs.mkdir()
    (mjs / "a.js").write_text("1+1")
    (mjs / "b.js").write_text("2+2")
    monkeypatch.setattr(corpus, "mjsunit_dir", lambda: mjs)

    tool = tmp_path / "FuzzILTool"
    tool.write_text('#!/bin/bash\ncp "$2" "${2%.js}.fzil"\n')
    tool.chmod(0o755)
    monkeypatch.setattr(corpus, "FUZZIL_TOOL", tool)

    stats = corpus.sync()
    assert stats["ok"] == 2
    assert (corpus.SEEDS_DIR / "a.fzil").is_file()

    stats2 = corpus.sync()
    assert stats2["ok"] == 0
    assert stats2["skip"] == 2


def test_trim(monkeypatch, tmp_path: Path) -> None:
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    monkeypatch.setattr(corpus, "SEEDS_DIR", seeds)
    old = seeds / "old.fzil"
    new = seeds / "new.fzil"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    past = time.time() - 40 * 86400
    os.utime(old, (past, past))

    cands = corpus.trim(days=30, apply=False)
    assert cands == [old]
    assert old.exists()  # dry-run không xoá

    cands = corpus.trim(days=30, apply=True)
    assert cands == [old]
    assert not old.exists()
    assert new.exists()
