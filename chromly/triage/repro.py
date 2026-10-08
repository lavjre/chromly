"""Triage repro — M3-01: repro ×N + symbolize + lift fzil (§5.4).

Crash artifact trong store/crashes/<hash>/ (M1-05). Chọn script để repro:
`.js` trực tiếp; chỉ có `.fzil` → lift bằng FuzzILTool --liftToJS.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm

CRASH_CODES = {134, 135, 136, 137, 138, 139}
SYMBOLIZE_HINT = re.compile(r"0x[0-9a-f]{8,}")


def symbolizer_path() -> Path | None:
    base = paths.V8_ROOT / "third_party" / "llvm-build" / "Release+Asserts" / "bin"
    for name in ("llvm-symbolizer", "llvm-symbolizer.exe"):
        p = base / name
        if p.is_file():
            return p
    return None


def artifact_dir(hash_prefix: str) -> Path:
    cr_dir = paths.STORE_DIR / "crashes"
    matches = [d for d in cr_dir.glob(f"{hash_prefix}*") if d.is_dir()]
    if not matches:
        raise FileNotFoundError(f"không thấy crash artifact {hash_prefix} trong {cr_dir}")
    return matches[0]


def pick_script(ad: Path) -> Path:
    js = sorted(ad.glob("program_*.js")) or sorted(ad.glob("*.js"))
    if js:
        return js[0]
    fzil = sorted(ad.glob("*.fzil"))
    if fzil:
        src = fzil[0]
        out = ad / "lifted.js"
        tool = farm.FUZZILLI_DIR / ".build" / "release" / "FuzzILTool"
        proc = subprocess.run(
            [str(tool), "--liftToJS", str(src)],
            capture_output=True,
            text=True,
            timeout=120,
            env=farm._env(),
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise RuntimeError(f"lift fzil lỗi: {proc.stderr[-300:]}")
        out.write_text(proc.stdout)
        return out
    raise FileNotFoundError(f"không có .js/.fzil trong {ad}")


def d8_asan() -> Path:
    return paths.V8_ROOT / "out" / "asan" / "d8"


def d8_fuzzilli() -> Path:
    return paths.V8_ROOT / "out" / "fuzzilli" / "d8"


def _crash_source(ad: Path) -> str:
    """unit/source từ meta.json của crash (vd 'fuzzilli')."""
    try:
        meta = json.loads((ad / "meta.json").read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    return str(meta.get("unit") or meta.get("source") or "")


def load_flags(d: Path) -> list[str]:
    """Flags thêm cho d8 từ repro.flags.txt (mỗi dòng/token; # = comment)."""
    f = d / "repro.flags.txt"
    if not f.is_file():
        return []
    flags = []
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            flags.extend(line.split())
    return flags


def repro_run(
    d8: Path, script: Path, runs: int = 5, timeout: int = 60, extra_flags: list[str] | None = None
) -> dict:
    env = os.environ.copy()
    sym = symbolizer_path()
    if sym:
        env["ASAN_SYMBOLIZER_PATH"] = str(sym)
    cmd = [str(d8), "--allow-natives-syntax", *(extra_flags or []), str(script)]
    crashed = 0
    outputs: list[str] = []
    last_rc = None
    for _ in range(runs):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            rc = proc.returncode
            out = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            rc = None
            out = "(timeout)"
        last_rc = rc
        if out not in outputs:
            outputs.append(out)
        asan_crash = "ERROR: AddressSanitizer" in out or "Fatal error" in out
        if (rc is not None and (rc in CRASH_CODES or rc < 0)) or asan_crash:
            crashed += 1
    return {
        "crashed": crashed,
        "of": runs,
        "stable": crashed == runs,
        "last_rc": last_rc,
        "output": outputs[0] if outputs else "",
    }


def triage_dir(hash_prefix: str) -> Path:
    return paths.STORE_DIR / "triage" / hash_prefix


def run_triage(hash_prefix: str, runs: int = 5) -> dict:
    """Repro + capture → store/triage/<hash>/ (asan.txt, symbols.txt, repro.js)."""
    ad = artifact_dir(hash_prefix)
    script = pick_script(ad)
    d8 = d8_asan()
    if not d8.is_file():
        raise FileNotFoundError(f"thiếu {d8} — build asan trước")
    flags = load_flags(ad)
    res = repro_run(d8, script, runs=runs, extra_flags=flags)
    engine = "asan"

    # Crash từ fuzzilli không repro trên asan (program giả định môi trường --fuzzing
    # của d8 fuzzilli build) → thử lại trên đúng build. Bài học 08/10: 3 crash raw
    # không tái hiện vì triage chỉ chạy asan.
    if res["crashed"] == 0 and _crash_source(ad) == "fuzzilli":
        d8f = d8_fuzzilli()
        if d8f.is_file():
            res2 = repro_run(d8f, script, runs=runs, extra_flags=[*flags, "--fuzzing"])
            if res2["crashed"] > 0:
                res = res2
                engine = "fuzzilli"

    td = triage_dir(ad.name)
    td.mkdir(parents=True, exist_ok=True)
    (td / "repro.js").write_text(script.read_text())
    (td / "asan.txt").write_text(res["output"])
    frames = [ln for ln in res["output"].splitlines() if SYMBOLIZE_HINT.search(ln)][:200]
    (td / "symbols.txt").write_text("\n".join(frames))
    return {
        "hash": ad.name,
        "crashed": f"{res['crashed']}/{res['of']}",
        "stable": res["stable"],
        "engine": engine,
        "repro": str(td / "repro.js"),
        "asan": str(td / "asan.txt"),
    }
