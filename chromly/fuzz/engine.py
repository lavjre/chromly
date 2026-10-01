"""Fuzz engine mode — M1-08 (ADR-010): libFuzzer thật cho V8 standalone.

V8 standalone build `v8_simple_*_fuzzer` với main one-shot (`test/fuzzer/fuzzer.cc`).
Engine mode = re-link CÙNG objects (đã có `-fsanitize=fuzzer-no-link` + coverage) nhưng:
- bỏ object main one-shot,
- thêm archive libFuzzer (compiler-rt của clang hệ thống),
- giữ nguyên flags/libs từ ninja file per-target (`out/libfuzzer/obj/v8_simple_<f>_fuzzer.ninja`)
→ binary `v8_engine_<f>_fuzzer` = libFuzzer mutation + coverage + artifact.

Không patch nguồn V8: chỉ đọc ninja file + re-link.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm

BUILD_DIR = "libfuzzer"
# unit name → tên fuzzer V8 (v8_simple_<name>_fuzzer)
LFUZZ_UNITS: dict[str, str] = {
    "lfuzz-parser": "parser",
    "lfuzz-wasm": "wasm_module",
}
# Source libFuzzer vendor (llvmorg-21.1.0, compiler-rt/lib/fuzzer).
FUZZER_SRC_DIR = paths.REPO_ROOT / "third_party" / "libfuzzer"
FUZZER_ARCHIVE_DIR = paths.REPO_ROOT / "build" / "libfuzzer"
# FuzzerInterceptors tách archive riêng upstream (đụng interceptor của ASAN) — loại.
FUZZER_EXCLUDE = {"FuzzerInterceptors.cpp"}
# Fallback: archive hệ thống (ABI libstdc++ — chỉ dùng khi chưa build vendor).
FUZZER_LIB_CANDIDATES = (
    "/usr/lib/llvm-21/lib/clang/21/lib/linux/libclang_rt.fuzzer-x86_64.a",
    "/usr/lib/llvm-20/lib/clang/20/lib/linux/libclang_rt.fuzzer-x86_64.a",
    "/usr/lib/llvm-19/lib/clang/19/lib/linux/libclang_rt.fuzzer-x86_64.a",
)
SYSTEM_CXX_RUNTIME = (Path("/usr/lib/x86_64-linux-gnu/libstdc++.so.6"),)
# Hệ thống .so (libstdc++) tham chiếu glibc mới hơn sysroot bullseye —
# bỏ qua kiểm tra shlib-undefined, runtime resolve theo host glibc.
_ALLOW_SHLIB_UNDEF = "-Wl,--allow-shlib-undefined"


def out_dir() -> Path:
    return paths.V8_ROOT / "out" / BUILD_DIR


def engine_bin(fuzzer: str) -> Path:
    return out_dir() / f"v8_engine_{fuzzer}_fuzzer"


def fuzzer_lib() -> Path:
    """Archive libFuzzer: ưu tiên bản vendor (ABI libc++, khớp toolchain V8)."""
    local = FUZZER_ARCHIVE_DIR / "libFuzzer.a"
    if local.is_file():
        return local
    for cand in FUZZER_LIB_CANDIDATES:
        p = Path(cand)
        if p.is_file():
            return p
    raise FileNotFoundError(
        "chưa có libFuzzer.a — chạy `chromly fuzz engine --build` (tự compile từ third_party/libfuzzer)"
    )


def ensure_fuzzer_archive(force: bool = False) -> Path:
    """Compile libFuzzer vendor bằng toolchain V8 (libc++, sysroot bullseye).

    Vì sao không dùng archive hệ thống: compiler-rt của Ubuntu build bằng
    libstdc++ + glibc mới (__cxx11, __isoc23_*) — không khớp binary V8.
    """
    archive = FUZZER_ARCHIVE_DIR / "libFuzzer.a"
    srcs = sorted(
        p for p in FUZZER_SRC_DIR.glob("Fuzzer*.cpp") if p.name not in FUZZER_EXCLUDE
    )
    if not srcs:
        raise FileNotFoundError(f"thiếu source libFuzzer trong {FUZZER_SRC_DIR}")
    if (
        archive.is_file()
        and not force
        and all(s.stat().st_mtime <= archive.stat().st_mtime for s in srcs)
    ):
        return archive

    clang = paths.V8_ROOT / "third_party" / "llvm-build" / "Release+Asserts" / "bin" / "clang++"
    ar = paths.V8_ROOT / "third_party" / "llvm-build" / "Release+Asserts" / "bin" / "llvm-ar"
    defines: list[str] = []
    try:
        defines = shlex.split(_parse_ninja("parser").get("defines", ""))
    except (FileNotFoundError, ValueError):
        pass
    flags = [
        "--target=x86_64-unknown-linux-gnu",
        "-fPIC",
        "-O2",
        "-g",
        "-fno-omit-frame-pointer",
        "-std=c++20",
        "-nostdinc++",
        "-I../../buildtools/third_party/libc++",
        "-isystem../../third_party/libc++abi/src/include",
        "-isystem../../third_party/libc++/src/include",
        "--sysroot=../../build/linux/debian_bullseye_amd64-sysroot",
        "-w",
        *defines,
    ]

    objdir = FUZZER_ARCHIVE_DIR / "obj"
    objdir.mkdir(parents=True, exist_ok=True)
    log_path = farm.LOGS_DIR / "engine-build-libfuzzer.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    objs: list[str] = []
    t0 = time.monotonic()
    with log_path.open("w") as fh:
        for s in srcs:
            o = objdir / (s.stem + ".o")
            cmd = [str(clang), *flags, "-c", str(s), "-o", str(o)]
            proc = subprocess.run(cmd, cwd=out_dir(), stdout=fh, stderr=subprocess.STDOUT)
            if proc.returncode != 0:
                tail = log_path.read_text(errors="replace").splitlines()[-8:]
                raise RuntimeError(
                    f"compile {s.name} fail rc={proc.returncode} — log {log_path}\n"
                    + "\n".join(tail)
                )
            objs.append(str(o))
        proc = subprocess.run(
            [str(ar), "rcs", str(archive), *objs], stdout=fh, stderr=subprocess.STDOUT
        )
        if proc.returncode != 0:
            raise RuntimeError(f"llvm-ar fail rc={proc.returncode} — log {log_path}")
    (FUZZER_ARCHIVE_DIR / "build-info.txt").write_text(
        f"src={FUZZER_SRC_DIR}\nobjects={len(objs)}\nwall_s={round(time.monotonic() - t0, 1)}\n"
    )
    return archive


def _unescape(s: str) -> str:
    """Ninja: `$$` → `$`; `$ ` → ` `; `$:` → `:`. Giữ lại `\\$` cho shlex."""
    res: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "$" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in ("$", " ", ":"):
                res.append(nxt)
                i += 2
                continue
        res.append(s[i])
        i += 1
    return "".join(res)


def _parse_ninja(target: str) -> dict:
    """Đọc per-target ninja file: link edge + ldflags/libs/rlibs bindings."""
    nf = out_dir() / "obj" / f"v8_simple_{target}_fuzzer.ninja"
    if not nf.is_file():
        raise FileNotFoundError(f"thiếu {nf} — build out/{BUILD_DIR} trước")
    text = nf.read_text()
    out: dict = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(\w+) = (.*)$", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = _unescape(m.group(2).strip())
    link_re = re.compile(
        rf"^build \./v8_simple_{re.escape(target)}_fuzzer: link (.*)$"
    )
    for line in text.splitlines():
        m = link_re.match(line)
        if m:
            spec = m.group(1).split(" || ")[0]
            explicit, _, implicit = spec.partition(" | ")
            out["_explicit"] = explicit.split()
            out["_implicit"] = implicit.split()
            break
    else:
        raise ValueError(f"không thấy link edge trong {nf}")
    return out


def build_engine(fuzzer: str = "parser") -> dict:
    """Re-link engine binary cho 1 fuzzer. Trả {fuzzer, bin, ok, rc, wall_s, log}."""
    ninja = _parse_ninja(fuzzer)
    ldflags = shlex.split(ninja.get("ldflags", ""))
    libs = shlex.split(ninja.get("libs", ""))
    rlibs = shlex.split(ninja.get("rlibs", ""))
    solibs = shlex.split(ninja.get("solibs", ""))

    inputs = ninja["_explicit"]
    cands = [t for t in inputs if t.endswith("/fuzzer.o")]
    if len(cands) != 1:
        raise ValueError(f"không xác định được main object (ứng viên: {cands[:5]})")
    link_inputs = [t for t in inputs if t != cands[0]]

    rsp = out_dir() / f"v8_engine_{fuzzer}.rsp"
    rsp.write_text(" ".join(link_inputs) + "\n")

    clang = paths.V8_ROOT / "third_party" / "llvm-build" / "Release+Asserts" / "bin" / "clang++"
    outp = engine_bin(fuzzer)
    archive = ensure_fuzzer_archive()
    cmd = [
        str(clang),
        *ldflags,
        f"-o{outp}",
        "-Wl,--start-group",
        f"@{rsp}",
        "-Wl,--end-group",
        *solibs,
        *libs,
        str(archive),
        *([str(p) for p in SYSTEM_CXX_RUNTIME] + [_ALLOW_SHLIB_UNDEF] if _needs_system_cxx(archive) else []),
        "-Wl,--start-group",
        *rlibs,
        "-Wl,--end-group",
    ]
    log_path = farm.LOGS_DIR / f"engine-build-{fuzzer}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with log_path.open("w") as fh:
        proc = subprocess.run(cmd, cwd=out_dir(), stdout=fh, stderr=subprocess.STDOUT)
    ok = proc.returncode == 0 and outp.is_file()
    result = {
        "fuzzer": fuzzer,
        "bin": str(outp),
        "ok": ok,
        "rc": proc.returncode,
        "n_objs": len(link_inputs),
        "wall_s": round(time.monotonic() - t0, 1),
        "log": str(log_path),
    }
    if not ok:
        tail = log_path.read_text(errors="replace").splitlines()[-8:]
        result["log_tail"] = tail
    return result


def _needs_system_cxx(archive: Path) -> bool:
    """libFuzzer hệ thống build bằng libstdc++ → cần runtime đó khi link."""
    try:
        out = subprocess.run(
            ["nm", "-u", str(archive)],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return True
    return "__cxx11" in out


# ── runtime loop ─────────────────────────────────────────────────────────────


def unit_dir(unit: str) -> Path:
    return farm.FUZZ_DIR / unit


def seed_corpus(unit: str, cap: int = 3000) -> int:
    """Seed corpus engine: kế thừa corpus replay (mjsunit + delta) nếu engine chưa có.

    Idempotent — chỉ copy file còn thiếu. Trả số file mới thêm.
    """
    from chromly.fuzz import replay

    fuzzer = LFUZZ_UNITS.get(unit)
    if fuzzer is None:
        return 0
    replay_unit = "libfuzzer-parser" if fuzzer == "parser" else "libfuzzer-wasm"
    replay.seed_corpus(replay_unit)  # top-up delta + mjsunit (idempotent)
    rsrc = farm.FUZZ_DIR / replay_unit / "corpus"
    dest = unit_dir(unit) / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    added = 0
    if rsrc.is_dir():
        for f in sorted(rsrc.iterdir()):
            if not f.is_file() or f.name.endswith(".log"):
                continue
            target = dest / f.name
            if target.exists():
                continue
            shutil.copy2(f, target)
            added += 1
            if added >= cap:
                break
    return added


def _lfuzz_cmd(
    binary: Path,
    corpus: Path,
    artifacts: Path,
    seconds: int = 600,
    timeout_s: int = 25,
    rss_mb: int = 2048,
) -> list[str]:
    """Cmd engine 1 cycle — tách riêng để test không cần process."""
    return [
        str(binary),
        f"-max_total_time={seconds}",
        f"-timeout={timeout_s}",
        f"-rss_limit_mb={rss_mb}",
        "-detect_leaks=0",
        f"-artifact_prefix={artifacts}/",
        "-print_final_stats=1",
        str(corpus),
    ]


def run_lfuzz(
    unit: str,
    seconds: int = 600,
    once: bool = False,
    interval: float = 2.0,
    timeout_s: int = 25,
) -> int:
    """Loop chạy engine (libFuzzer) — mutation trên corpus, artifact → artifacts/.

    Cycle = 1 tiến trình engine `-max_total_time=seconds`; stream pulse ra log
    (farm parse `exec/s:` + watchdog thấy hoạt động). rc=77 = crash (artifact).
    """
    fuzzer = LFUZZ_UNITS.get(unit)
    if fuzzer is None:
        print(f"unit không hợp lệ: {unit} (chọn: {', '.join(LFUZZ_UNITS)})", flush=True)
        return 2
    binary = engine_bin(fuzzer)
    if not binary.is_file():
        print(f"thiếu engine binary {binary} — chạy `chromly fuzz engine --build` trước", flush=True)
        return 1
    base = unit_dir(unit)
    corpus = base / "corpus"
    artifacts = base / "artifacts"
    corpus.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    seeded = seed_corpus(unit)
    print(f"[lfuzz] {unit}: seeds +{seeded}, corpus={len(list(corpus.iterdir()))}", flush=True)

    cmd = _lfuzz_cmd(binary, corpus, artifacts, seconds=seconds, timeout_s=timeout_s)
    env = farm._env()
    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            print(f"[lfuzz] spawn fail: {type(exc).__name__}: {exc}", flush=True)
            return 1
        assert proc.stdout is not None
        for line in proc.stdout:
            s = line.rstrip("\n")
            if (
                s.startswith(("#", "INFO: ", "stat::", "Done ", "MS: "))
                or "exec/s:" in s
                or "ERROR:" in s
                or "SUMMARY:" in s
                or "artifact_prefix" in s
                or s.startswith("crash-")
            ):
                print(s, flush=True)
        rc = proc.wait()
        if rc == 77:
            print(f"[lfuzz] CRASH trong cycle — artifact mới ở {artifacts}/", flush=True)
        elif rc != 0:
            print(f"[lfuzz] engine exit rc={rc}", flush=True)
        if once:
            return 0
        time.sleep(interval)



def run_engine_cmd(args) -> int:
    if getattr(args, "build", False):
        fuzzers = getattr(args, "fuzzer", None) or sorted(set(LFUZZ_UNITS.values()))
        rc = 0
        for f in fuzzers:
            res = build_engine(f)
            print(
                f"engine {f}: {'OK' if res['ok'] else 'FAIL'} ({res['wall_s']}s) → {res['bin']}",
                flush=True,
            )
            if not res["ok"]:
                print("  tail:", *res.get("log_tail", []), sep="\n    ", flush=True)
                rc = 1
        return rc
    print("usage: chromly fuzz engine --build [--fuzzer parser|wasm_module]")
    return 2


def run_lfuzz_cmd(args) -> int:
    unit = getattr(args, "unit", None)
    if not unit:
        print("usage: chromly fuzz lfuzz --unit lfuzz-parser|lfuzz-wasm")
        return 2
    return run_lfuzz(
        unit,
        seconds=getattr(args, "seconds", 600),
        once=getattr(args, "once", False),
        interval=getattr(args, "interval", 2.0),
    )


if __name__ == "__main__":
    sys.exit(run_engine_cmd(type("A", (), {"build": True, "fuzzer": None})()))
