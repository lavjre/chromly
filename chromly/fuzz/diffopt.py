"""Differential opt/no-opt — M2-10: bắt miscompile KHÔNG-crash bằng so hành vi.

Lấy mẫu program (.js sidecar của corpus fuzzilli — đã lift sẵn), chạy trên d8 2 cấu hình:
  A) mặc định (JIT đầy đủ)      B) --no-opt (không tối ưu)
Chỉ báo DIFF khi A/B khác nhau (rc hoặc stdout) VÀ mỗi bên TÁI LẬP được (chạy lại khớp)
— lọc bỏ nondeterminism (Date/random/địa chỉ crash...). Diff = ứng viên miscompile
(class bug mà fuzz crash-detector bỏ lỡ: calib-567177599/be64fd6d thuộc lớp này).
Artifact: store/fuzz/diffopt/<ts>/<n>_{program,js,a1,a2,b1,b2,meta}.
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm

MAX_OUT = 4000
DEFAULT_BUILD = "release"


def diffopt_dir() -> Path:
    return paths.STORE_DIR / "fuzz" / "diffopt"


def sample_programs(limit: int) -> list[Path]:
    corpus = farm.FUZZ_DIR / "fuzzilli" / "corpus"
    files = sorted(corpus.glob("*.js"))
    rng = random.Random(int(time.time() // 3600))
    return rng.sample(files, min(limit, len(files)))


def run_once(d8: Path, program: Path, flags: list[str], timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(
            [str(d8), "--allow-natives-syntax", *flags, str(program)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=farm._env(),
        )
        return {"rc": proc.returncode, "out": (proc.stdout + proc.stderr)[-MAX_OUT:]}
    except subprocess.TimeoutExpired:
        return {"rc": None, "out": "(timeout)"}


def compare(a1: dict, a2: dict, b1: dict, b2: dict) -> bool:
    """True nếu diff đáng báo: hai bên tái lập được và khác nhau (rc hoặc stdout)."""
    stable_a = (a1["rc"], a1["out"]) == (a2["rc"], a2["out"])
    stable_b = (b1["rc"], b1["out"]) == (b2["rc"], b2["out"])
    if not (stable_a and stable_b):
        return False
    return (a1["rc"] != b1["rc"]) or (a1["out"] != b1["out"])


def _save_diff(d: Path, program: Path, a1: dict, a2: dict, b1: dict, b2: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "program.js").write_text(program.read_text())
    for name, res in (("a1", a1), ("a2", a2), ("b1", b1), ("b2", b2)):
        (d / f"{name}.txt").write_text(f"rc={res['rc']}\n{res['out']}\n")
    (d / "meta.json").write_text(
        json.dumps(
            {
                "program": str(program),
                "rc_a": a1["rc"],
                "rc_b": b1["rc"],
                "created": time.time(),
            },
            indent=2,
        )
    )


def run_diffopt(limit: int = 100, build: str = DEFAULT_BUILD, timeout: int = 20) -> dict:
    d8 = paths.V8_ROOT / "out" / build / "d8"
    if not d8.is_file():
        raise FileNotFoundError(f"thiếu {d8}")
    programs = sample_programs(limit)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_base = diffopt_dir() / stamp
    diffs = 0
    for i, prog in enumerate(programs, 1):
        a1 = run_once(d8, prog, [], timeout)
        b1 = run_once(d8, prog, ["--no-opt"], timeout)
        if (a1["rc"], a1["out"]) == (b1["rc"], b1["out"]):
            continue
        a2 = run_once(d8, prog, [], timeout)
        b2 = run_once(d8, prog, ["--no-opt"], timeout)
        if not compare(a1, a2, b1, b2):
            continue
        diffs += 1
        _save_diff(out_base / f"{i:04d}_{prog.stem[:48]}", prog, a1, a2, b1, b2)
        print(
            f"[diffopt] DIFF {prog.name} rcA={a1['rc']} rcB={b1['rc']} (artifact {out_base.name})",
            flush=True,
        )
    summary = {
        "build": build,
        "sampled": len(programs),
        "diffs": diffs,
        "artifact_dir": str(out_base) if diffs else None,
        "ran": time.time(),
    }
    diffopt_dir().mkdir(parents=True, exist_ok=True)
    (diffopt_dir() / "last.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"diffopt: sampled={len(programs)} diffs={diffs}", flush=True)
    return summary


def run_diffopt_cmd(args) -> int:
    def once() -> int:
        try:
            s = run_diffopt(
                limit=getattr(args, "limit", 100),
                build=getattr(args, "build", DEFAULT_BUILD),
                timeout=getattr(args, "timeout", 20),
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"diffopt: {e}", flush=True)
            return 1
        if s["diffs"]:
            print(f"  → {s['diffs']} ứng viên miscompile tại {s['artifact_dir']}", flush=True)
        return 0

    if getattr(args, "loop", False):
        interval = getattr(args, "interval", 86400.0)
        while True:
            once()
            time.sleep(interval)
    return once()
