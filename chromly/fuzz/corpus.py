"""Corpus pipeline — M1-06: mjsunit → FuzzIL seeds → import vào storage (§5.2).

- `sync`: subset mjsunit → `FuzzILTool --compile` (node parser) → `store/fuzz/corpus/fzil/*.fzil`
- `import`: one-shot `FuzzilliCli --importCorpus --shutdownAfterImport` → persist vào storage;
  farm chạy tiếp bằng `--resume`
- `trim`: cull seed theo tuổi (dry-run mặc định; `--apply` mới xoá)
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm

FUZZIL_TOOL = farm.FUZZILLI_DIR / ".build" / "release" / "FuzzILTool"
SEEDS_DIR = farm.FUZZ_DIR / "corpus" / "fzil"
SRC_DIR = farm.FUZZ_DIR / "corpus" / "mjsunit-src"


def mjsunit_dir() -> Path:
    return paths.V8_ROOT / "test" / "mjsunit"


def sync(limit: int = 120) -> dict:
    """Biên dịch subset mjsunit → seeds .fzil. Idempotent: seed đã có thì bỏ qua."""
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    if not FUZZIL_TOOL.is_file():
        raise FileNotFoundError(f"FuzzILTool chưa build: {FUZZIL_TOOL}")
    files = sorted(mjsunit_dir().glob("*.js"))[:limit]
    stats = {"ok": 0, "fail": 0, "skip": 0, "total": len(files)}
    for src in files:
        seed = SEEDS_DIR / (src.stem + ".fzil")
        if seed.exists():
            stats["skip"] += 1
            continue
        work = SRC_DIR / src.name
        shutil.copy2(src, work)
        try:
            proc = subprocess.run(
                [str(FUZZIL_TOOL), "--compile", str(work)],
                capture_output=True,
                text=True,
                timeout=120,
                env=farm._env(),
            )
        except subprocess.TimeoutExpired:
            stats["fail"] += 1
            work.unlink(missing_ok=True)
            continue
        produced = work.with_suffix(".fzil")
        if proc.returncode == 0 and produced.is_file():
            shutil.move(str(produced), seed)
            stats["ok"] += 1
        else:
            stats["fail"] += 1
        work.unlink(missing_ok=True)
    return stats


def import_to_storage() -> int:
    """One-shot import seeds vào storagePath — lần chạy farm sau dùng --resume."""
    if not farm.FUZZILLI_BIN.is_file() or not farm.d8_path().is_file():
        raise FileNotFoundError("FuzzilliCli hoặc d8 fuzzilli chưa build")
    storage = farm.FUZZ_DIR / "fuzzilli"
    storage.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(farm.FUZZILLI_BIN),
        "--profile=v8",
        f"--storagePath={storage}",
        f"--importCorpus={SEEDS_DIR}",
        "--shutdownAfterImport",
        "--logLevel=info",
        str(farm.d8_path()),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=farm._env())
    log = farm.LOGS_DIR / "corpus-import.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(proc.stdout + "\n" + proc.stderr)
    return proc.returncode


def trim(days: int = 30, apply: bool = False) -> list[Path]:
    """Seed cũ hơn `days` ngày. Dry-run mặc định."""
    cutoff = time.time() - days * 86400
    candidates = [p for p in sorted(SEEDS_DIR.glob("*.fzil")) if p.stat().st_mtime < cutoff]
    if apply:
        for p in candidates:
            p.unlink()
    return candidates
