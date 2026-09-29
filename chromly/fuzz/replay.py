"""Replay runner cho V8 simple-fuzzer binaries — M1-03 v0.

Lưu ý: V8 standalone KHÔNG link engine libFuzzer (thiếu //testing/libfuzzer như chromium);
`v8_simple_*_fuzzer` là one-shot runner (nhận danh sách file). v0: wrapper replay corpus
theo batch + bắt crash; engine thật = follow-up (task M1-08/cần ADR wiring engine).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm

BATCH = 100
MAX_FILES = 2000


def unit_paths(unit: str) -> tuple[Path, Path, Path]:
    binary = paths.V8_ROOT / "out" / "libfuzzer" / farm.LIBFUZZER_TARGETS[unit]
    base = farm.FUZZ_DIR / unit
    return binary, base / "corpus", base / "artifacts"


def seed_corpus(unit: str) -> int:
    """Parser: seed từ mjsunit (JS). Wasm: để trống (follow-up)."""
    _, corpus, _ = unit_paths(unit)
    corpus.mkdir(parents=True, exist_ok=True)
    if any(corpus.iterdir()):
        return 0
    if unit != "libfuzzer-parser":
        return 0
    src_dir = paths.V8_ROOT / "test" / "mjsunit"
    n = 0
    for f in sorted(src_dir.glob("*.js"))[:200]:
        shutil.copy2(f, corpus / f.name)
        n += 1
    return n


def _save_crash(unit: str, chunk: list[str], output: str) -> None:
    _, _, artifacts = unit_paths(unit)
    artifacts.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    d = artifacts / f"replay-{ts}"
    d.mkdir(exist_ok=True)
    for f in chunk[:20]:
        shutil.copy2(f, d / Path(f).name)
    (d / "output.log").write_text(output[-20000:])


def lfreplay_once(unit: str) -> dict:
    binary, corpus, _ = unit_paths(unit)
    if unit not in farm.LIBFUZZER_TARGETS:
        raise ValueError(f"unit không hợp lệ: {unit}")
    if not Path(binary).is_file():
        raise FileNotFoundError(f"thiếu binary {binary}")
    seeded = seed_corpus(unit)
    files = sorted(p for p in corpus.iterdir() if p.is_file())[:MAX_FILES]
    if not files:
        print("Execs / Second: 0.0  (files=0)", flush=True)
        return {"files": 0, "crashes": 0, "rate": 0.0, "seeded": seeded}
    t0 = time.monotonic()
    crashes = 0
    for i in range(0, len(files), BATCH):
        chunk = [str(f) for f in files[i : i + BATCH]]
        try:
            proc = subprocess.run(
                [str(binary), *chunk], capture_output=True, text=True, timeout=600
            )
            out = proc.stdout + proc.stderr
            if proc.returncode != 0 or "ERROR: AddressSanitizer" in out:
                crashes += 1
                _save_crash(unit, chunk, out)
        except subprocess.TimeoutExpired as exc:
            crashes += 1
            _save_crash(unit, chunk, f"(timeout) {exc}")
    dt = time.monotonic() - t0
    rate = len(files) / dt if dt > 0 else 0.0
    print(
        f"Execs / Second: {rate:.1f}  (files={len(files)} crashes={crashes} seeded={seeded})",
        flush=True,
    )
    return {"files": len(files), "crashes": crashes, "rate": rate, "seeded": seeded}


def run_lfreplay(unit: str, interval: float = 60.0, once: bool = False) -> int:
    while True:
        try:
            lfreplay_once(unit)
        except Exception as exc:  # noqa: BLE001 — loop dài hạn
            print(f"lfreplay lỗi: {type(exc).__name__}: {exc}", flush=True)
        if once:
            return 0
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="chromly-lfreplay")
    p.add_argument("--unit", required=True, choices=sorted(farm.LIBFUZZER_TARGETS))
    p.add_argument("--interval", type=float, default=60.0)
    p.add_argument("--once", action="store_true")
    args = p.parse_args(argv)
    return run_lfreplay(args.unit, interval=args.interval, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
