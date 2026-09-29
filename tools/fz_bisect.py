#!/usr/bin/env python3
"""Bisect corpus fuzzilli gây crash khi import.

Dùng scratch storage riêng; import subset; thu hẹp dần file độc.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLI = Path.home() / "tools" / "fuzzilli" / ".build" / "release" / "FuzzilliCli"
D8 = Path.home() / "v8" / "v8" / "out" / "fuzzilli" / "d8"
SRC = Path.home() / "chromly" / "store" / "fuzz" / "fuzzilli" / "corpus"
SCRATCH = Path("/tmp/opencode/fz-bisect")


def try_import(files: list[Path]) -> bool:
    """True nếu import OK (không crash)."""
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    imp = SCRATCH / "corpus"
    imp.mkdir(parents=True)
    for f in files:
        shutil.copy2(f, imp / f.name)
    storage = SCRATCH / "storage"
    storage.mkdir()
    proc = subprocess.run(
        [
            str(CLI), "--profile=v8", f"--storagePath={storage}",
            f"--importCorpus={imp}", "--shutdownAfterImport", "--logLevel=warning",
            str(D8),
        ],
        capture_output=True, text=True, timeout=600,
    )
    return proc.returncode == 0


def main() -> int:
    files = sorted(SRC.glob("*.fzil"))
    print(f"corpus: {len(files)} file")
    if not try_import(files):
        print("reproduce: import full corpus CRASH")
    else:
        print("full import KHÔNG crash ở lần này — bỏ bisect")
        return 0

    poison = files
    while len(poison) > 1:
        mid = len(poison) // 2
        left, right = poison[:mid], poison[mid:]
        if not try_import(left):
            poison = left
        elif not try_import(right):
            poison = right
        else:
            print(f"cả hai nửa OK → độc cần ≥2 file (còn {len(poison)})")
            # giữ nguyên và thử từng file
            for f in poison:
                if not try_import([f]):
                    print(f"CULPRIT: {f}")
                    return 0
            print("không cô lập được từng file (tương tác)")
            return 1
        print(f"còn {len(poison)}")
    print(f"CULPRIT: {poison[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
