"""Replay runner cho V8 simple-fuzzer binaries — M1-03 v0.

Lưu ý: V8 standalone KHÔNG link engine libFuzzer (thiếu //testing/libfuzzer như chromium);
`v8_simple_*_fuzzer` là one-shot runner (nhận danh sách file). v0: wrapper replay corpus
theo batch + bắt crash; engine thật = follow-up (task M1-08/cần ADR wiring engine).
"""

from __future__ import annotations

import hashlib
import random
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
    """Parser: seed lần đầu từ mjsunit (JS) + top-up test delta (audit) mỗi lần chạy.
    Wasm: để trống (follow-up)."""
    _, corpus, _ = unit_paths(unit)
    corpus.mkdir(parents=True, exist_ok=True)
    if unit != "libfuzzer-parser":
        return 0
    n = 0
    # lần đầu: mjsunit root (nếu corpus trống)
    if not any(corpus.iterdir()):
        src_dir = paths.V8_ROOT / "test" / "mjsunit"
        for f in sorted(src_dir.glob("*.js"))[:200]:
            shutil.copy2(f, corpus / f.name)
            n += 1
    # top-up: test mới sau checkout (audit đã tải về) — biến tri thức upstream thành seed
    n += _seed_delta(unit)
    return n


def _seed_delta(unit: str, cap: int = 300) -> int:
    """Copy test mới sau checkout (store/regress-audit/tests) vào corpus, dedup sha256."""
    _, corpus, _ = unit_paths(unit)
    src = paths.STORE_DIR / "regress-audit" / "tests"
    if not src.is_dir():
        return 0
    added = 0
    for f in sorted(src.rglob("*.js")):
        if added >= cap:
            break
        data = f.read_bytes()
        dest = corpus / f"{hashlib.sha256(data).hexdigest()[:12]}-{f.name}"
        if dest.exists():
            continue
        dest.write_bytes(data)
        added += 1
    return added


def _bisect_crash(unit: str, chunk: list[str], batch_out: str) -> int:
    """Batch nổ → chạy từng file tìm thủ phạm → lưu FILE PHẲNG (ingest bắt được).
    Không tìm ra thủ phạm đơn lẻ (hiệu ứng tập thể) → fallback lưu nguyên chunk."""
    binary, _, artifacts = unit_paths(unit)
    artifacts.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    saved = 0
    for path in chunk:
        try:
            proc = subprocess.run([str(binary), path], capture_output=True, text=True, timeout=300)
            out = proc.stdout + proc.stderr
            bad = proc.returncode != 0 or "ERROR: AddressSanitizer" in out
        except subprocess.TimeoutExpired as exc:
            out = f"(timeout) {exc}"
            bad = True
        if bad:
            name = f"crash-{ts}-{Path(path).name}"
            shutil.copy2(path, artifacts / name)
            (artifacts / f"{name}.log").write_text(out[-20000:])
            saved += 1
    if saved == 0:
        _save_crash(unit, chunk, batch_out)
    return saved


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
    all_files = [p for p in corpus.iterdir() if p.is_file()]
    if len(all_files) > MAX_FILES:
        # xoay theo giờ: seed mới sớm được chạy (sorted()[:N] cố định sẽ chôn seed mới)
        files = random.Random(int(time.time() // 3600)).sample(all_files, MAX_FILES)
    else:
        files = sorted(all_files)
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
                _bisect_crash(unit, chunk, out)
        except subprocess.TimeoutExpired as exc:
            crashes += 1
            _bisect_crash(unit, chunk, f"(timeout) {exc}")
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
