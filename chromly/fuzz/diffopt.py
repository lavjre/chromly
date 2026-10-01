"""Differential lane — M2-10 nâng cấp: bắt miscompile KHÔNG-crash (gap 0day).

Chạy corpus fuzzilli (.js lift sẵn, chạy được standalone) trên 2 cấu hình d8 CÙNG build:
  A) mặc định (JIT đầy đủ)
  B) một axis JIT: --no-opt | --jitless | --no-maglev | --deopt-every-n-times
Chỉ báo DIFF khi A/B khác nhau (rc hoặc stdout) VÀ cả hai bên TÁI LẬP được (2 lần khớp)
— lọc nondeterminism (Date/random/địa chỉ). Diff = ứng viên miscompile (lớp bug mà
crash-detector bỏ lỡ: calib-567177599/be64fd6d thuộc lớp này).

Khác v0 sampler (1000 mẫu/ngày, kết quả nằm im):
- cursor quét corpus có trạng thái → không bỏ sót, phủ hết corpus theo thời gian;
- budget thời gian mỗi cycle (`--seconds`) + chạy loop ngắn → lane liên tục;
- dedup cross-sweep (`found.json`) — không báo lại cùng (program, axis);
- finding ghi vào crash store (source='diffopt') + triage context → pipeline thấy.

Artifact: store/fuzz/diffopt/<ts>/<n>_<name>/{program.js,a1..b2.txt,meta.json}
+ state.json (cursor) + found.json (dedup) + last.json (summary).
"""

from __future__ import annotations

import bisect
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.fuzz import farm
from chromly.store import db

MAX_OUT = 4000
DEFAULT_BUILD = "release"
DEFAULT_SECONDS = 900.0
_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")
_CARET_RE = re.compile(r"^\s*\^+\s*$")
_FRAME_RE = re.compile(r"^\s+at .*$")
_ERR_HEAD_RE = re.compile(r"^(\S+):(\d+): (\w*Error(?: \[[^\]]+\])?): ")
OOM_MARKERS = (
    "Fatal JavaScript out of memory",
    "CALL_AND_RETRY_LAST",
    "Fatal process out of memory",
)
CRASH_RCS = {132, 133, 134, 136, 137, 138, 139}  # SIGILL..SIGSEGV qua shell
AXES: list[tuple[str, list[str]]] = [
    ("no-opt", ["--no-opt"]),
    ("no-sparkplug", ["--no-sparkplug"]),
    ("no-maglev", ["--no-maglev"]),
    ("deopt-100", ["--deopt-every-n-times=100"]),
]


def diffopt_dir() -> Path:
    return paths.STORE_DIR / "fuzz" / "diffopt"


def _state_path() -> Path:
    return diffopt_dir() / "state.json"


def _load_state() -> dict:
    p = _state_path()
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"cursor": "", "sweeps": 0}


def _save_state(state: dict) -> None:
    diffopt_dir().mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _load_found() -> dict:
    p = diffopt_dir() / "found.json"
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_found(found: dict) -> None:
    diffopt_dir().mkdir(parents=True, exist_ok=True)
    (diffopt_dir() / "found.json").write_text(json.dumps(found, ensure_ascii=False, indent=2))


def pick_programs(cursor: str, limit: int) -> list[Path]:
    """Program kế tiếp sau `cursor` theo thứ tự tên; hết thì quẩy vòng lại từ đầu."""
    corpus = farm.FUZZ_DIR / "fuzzilli" / "corpus"
    files = sorted(corpus.glob("*.js"))
    if not files:
        return []
    start = bisect.bisect_right([f.name for f in files], cursor) if cursor else 0
    window = files[start:] + files[:start]
    return window[:limit]


def _normalize(out: str) -> str:
    """Chuẩn hoá output nhiễu-config (không phải khác biệt hành vi):

    - địa chỉ heap (mỗi lần chạy khác nhau);
    - block uncaught-error: vị trí `file:line[:col]`, dòng snippet + caret, các frame
      `at ...` — stack-overflow/attribution khác nhau theo tier JIT (sparkplug/maglev…)
      nhưng cùng một lỗi (FP lớp thật gặp 2026-10-02, program f6 đệ quy: A báo ở
      unnamed:3:20, B báo ở unnamed:4:13 — cùng RangeError).
    """
    out = _ADDR_RE.sub("0xADDR", out)
    keep: list[str] = []
    for line in out.splitlines():
        if _CARET_RE.match(line):
            if keep:
                keep.pop()  # dòng snippet ngay trước caret
            continue
        if _FRAME_RE.match(line):
            continue
        keep.append(_ERR_HEAD_RE.sub(r"\1:N: \3: ", line))
    return "\n".join(keep)


def run_once(d8: Path, program: Path, flags: list[str], timeout: int = 20) -> dict:
    # `--fuzzing`: corpus fuzzilli sinh cho môi trường này (bỏ check prepare-optimization,
    # đúng như fuzzilli chạy) — thiếu nó là warning-spam/FATAL giả (đã gặp 2026-10-01).
    try:
        proc = subprocess.run(
            [str(d8), "--allow-natives-syntax", "--expose-gc", "--fuzzing", *flags, str(program)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=farm._env(),
        )
        return {"rc": proc.returncode, "out": _normalize((proc.stdout + proc.stderr)[-MAX_OUT:])}
    except subprocess.TimeoutExpired:
        return {"rc": None, "out": "(timeout)"}


def compare(a1: dict, a2: dict, b1: dict, b2: dict) -> bool:
    """True nếu diff đáng báo: hai bên tái lập được và khác nhau (rc hoặc stdout)."""
    stable_a = (a1["rc"], a1["out"]) == (a2["rc"], a2["out"])
    stable_b = (b1["rc"], b1["out"]) == (b2["rc"], b2["out"])
    if not (stable_a and stable_b):
        return False
    return (a1["rc"] != b1["rc"]) or (a1["out"] != b1["out"])


def _comparable(res: dict) -> bool:
    """Bỏ kết quả không so sánh được: timeout (None) hoặc OOM (phụ thuộc bộ nhớ/lúc chạy)."""
    if res["rc"] is None:
        return False
    return not any(m in res["out"] for m in OOM_MARKERS)


def _crashy(res: dict) -> bool:
    if res["rc"] is None or any(m in res["out"] for m in OOM_MARKERS):
        return False
    return res["rc"] < 0 or res["rc"] in CRASH_RCS


def _save_diff(d: Path, program: Path, axis: str, a1, a2, b1, b2) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "program.js").write_text(program.read_text())
    for name, res in (("a1", a1), ("a2", a2), ("b1", b1), ("b2", b2)):
        (d / f"{name}.txt").write_text(f"rc={res['rc']}\n{res['out']}\n")
    (d / "meta.json").write_text(
        json.dumps(
            {
                "program": str(program),
                "axis": axis,
                "rc_a": a1["rc"],
                "rc_b": b1["rc"],
                "created": time.time(),
            },
            indent=2,
        )
    )


def _file_finding(program: Path, kind: str, axis: str, severity: int, evidence: str) -> str:
    """Ghi finding vào crash store + triage context (để case pipeline/pipeline nhìn thấy)."""
    data = program.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    dest = paths.STORE_DIR / "crashes" / h
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"program_diffopt_{axis}.js").write_bytes(data)
    (dest / "meta.json").write_text(
        json.dumps(
            {
                "hash": h,
                "unit": "diffopt",
                "axis": axis,
                "kind": kind,
                "orig_path": str(program),
                "created": time.time(),
            },
            indent=2,
        )
    )
    tri = paths.STORE_DIR / "triage" / h
    tri.mkdir(parents=True, exist_ok=True)
    (tri / "repro.js").write_bytes(data)
    axis_flags = " ".join(dict(AXES).get(axis, [])) or "(mặc định)"
    (tri / "triage.md").write_text(
        "# diffopt finding\n\n"
        f"- kind: {kind}\n- axis: {axis}\n- program: {program.name}\n\n"
        "## Cách verify\n\n"
        "Bug lớp miscompile (KHÔNG crash): chạy hai cấu hình trên cùng build d8 và so:\n\n"
        "```bash\n"
        "d8 --allow-natives-syntax --expose-gc repro.js            # A (mặc định)\n"
        f"d8 --allow-natives-syntax --expose-gc {axis_flags} repro.js  # B\n"
        "```\n\n"
        "Hai bên khác rc/stdout một cách tái lập = miscompile. Đối chiếu thêm trên ToT "
        "(`out/tot/d8`) để xác nhận còn sống.\n\n"
        f"## Evidence\n\n{evidence}\n"
    )
    con = db.ensure_db()
    try:
        rev = farm._v8_rev()
        row = con.execute("SELECT dup_count FROM crashes WHERE hash = ?", (h,)).fetchone()
        with con:
            if row is not None:
                con.execute("UPDATE crashes SET dup_count = dup_count + 1 WHERE hash = ?", (h,))
            else:
                con.execute(
                    "INSERT INTO crashes (hash, fault_type, severity, build_rev, source, "
                    "state, stack_norm) VALUES (?, ?, ?, ?, 'diffopt', 'triaged', ?)",
                    (h, kind, severity, rev, f"diffopt:{axis}"),
                )
    finally:
        con.close()
    return h


def run_diffopt(
    limit: int = 0,
    build: str = DEFAULT_BUILD,
    timeout: int = 20,
    axes: list[tuple[str, list[str]]] | None = None,
    seconds: float = DEFAULT_SECONDS,
) -> dict:
    """Một cycle: quét corpus từ cursor, mỗi program 1 axis (luân phiên), dừng theo
    limit hoặc budget `seconds`. Trả summary (giữ key `sampled`/`diffs` cho acceptance)."""
    d8 = paths.V8_ROOT / "out" / build / "d8"
    if not d8.is_file():
        raise FileNotFoundError(f"thiếu {d8}")
    axes = axes or AXES
    state = _load_state()
    found = _load_found()
    cap = limit if limit and limit > 0 else 10**9
    programs = pick_programs(state.get("cursor", ""), cap)

    t0 = time.monotonic()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_base = diffopt_dir() / stamp
    sampled = diffs = crashes = 0
    last_name = state.get("cursor", "")
    for i, prog in enumerate(programs):
        if seconds and time.monotonic() - t0 >= seconds:
            break
        axis_name, axis_flags = axes[i % len(axes)]
        sampled += 1
        last_name = prog.name
        a1 = run_once(d8, prog, [], timeout)
        b1 = run_once(d8, prog, axis_flags, timeout)
        if (a1["rc"], a1["out"]) == (b1["rc"], b1["out"]):
            # vẫn bắt crash release (A/B giống nhau nhưng cùng crash tái lập)
            if _crashy(a1):
                a2 = run_once(d8, prog, [], timeout)
                if (a1["rc"], a1["out"]) == (a2["rc"], a2["out"]):
                    crashes += 1
                    _file_finding(
                        prog,
                        "release-crash",
                        "default",
                        5,
                        f"rc={a1['rc']}\n{a1['out'][-800:]}",
                    )
                    print(f"[diffopt] CRASH {prog.name} rc={a1['rc']}", flush=True)
            continue
        if not (_comparable(a1) and _comparable(b1)):
            continue
        a2 = run_once(d8, prog, [], timeout)
        b2 = run_once(d8, prog, axis_flags, timeout)
        if not compare(a1, a2, b1, b2):
            continue
        # confirm lần 3: lọc race hiếm (vd Worker flush error bất định — gặp 2026-10-01)
        a3 = run_once(d8, prog, [], timeout)
        b3 = run_once(d8, prog, axis_flags, timeout)
        if (a1["rc"], a1["out"]) != (a3["rc"], a3["out"]):
            continue
        if (b1["rc"], b1["out"]) != (b3["rc"], b3["out"]):
            continue
        key = f"{hashlib.sha256(prog.read_bytes()).hexdigest()[:24]}:{axis_name}"
        if key in found:
            continue
        diffs += 1
        art = out_base / f"{i:05d}_{prog.stem[:48]}"
        _save_diff(art, prog, axis_name, a1, a2, b1, b2)
        h = _file_finding(
            prog,
            "miscompile-diff",
            axis_name,
            4,
            f"rcA={a1['rc']} rcB={b1['rc']}\n"
            f"--- A ---\n{a1['out'][-400:]}\n--- B ---\n{b1['out'][-400:]}",
        )
        found[key] = {"dir": str(art), "hash": h[:12], "ts": time.time()}
        print(
            f"[diffopt] DIFF {prog.name} axis={axis_name} rcA={a1['rc']} rcB={b1['rc']} "
            f"(artifact {art.name})",
            flush=True,
        )

    state["cursor"] = last_name
    sweep_done = bool(programs) and len(programs) < cap
    if sweep_done:
        state["sweeps"] = int(state.get("sweeps", 0)) + 1
    _save_state(state)
    _save_found(found)

    elapsed = round(time.monotonic() - t0, 1)
    summary = {
        "build": build,
        "axes": [n for n, _ in axes],
        "sampled": sampled,
        "diffs": diffs,
        "crashes": crashes,
        "seconds": elapsed,
        "budget_s": seconds,
        "sweeps": state.get("sweeps", 0),
        "cursor": state.get("cursor", ""),
        "artifact_dir": str(out_base) if diffs else None,
        "ran": time.time(),
    }
    diffopt_dir().mkdir(parents=True, exist_ok=True)
    (diffopt_dir() / "last.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"diffopt: sampled={sampled} diffs={diffs} crashes={crashes} ({elapsed}s)", flush=True)
    return summary


def run_diffopt_cmd(args) -> int:
    def once() -> int:
        try:
            s = run_diffopt(
                limit=getattr(args, "limit", 0),
                build=getattr(args, "build", DEFAULT_BUILD),
                timeout=getattr(args, "timeout", 20),
                seconds=getattr(args, "seconds", DEFAULT_SECONDS),
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"diffopt: {e}", flush=True)
            return 1
        if s["diffs"]:
            print(f"  → {s['diffs']} ứng viên miscompile tại {s['artifact_dir']}", flush=True)
        return 0

    if getattr(args, "loop", False):
        interval = getattr(args, "interval", 120.0)
        while True:
            once()
            time.sleep(interval)
    return once()
