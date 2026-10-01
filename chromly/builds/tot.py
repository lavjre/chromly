"""ToT (tip-of-tree) — build mới nhất từ mirror + verify repro còn sống (unfixed).

`chromly tot build`: sync cây chính lên ToT sha (mirror FETCH_HEAD) → build out/tot
(asan+dcheck, config tot.gn) → revert về snapshot. State: store/tot.json.
`chromly tot verify <file.js|crash_hash>`: chạy repro trên out/tot/d8 →
STILL-CRASHES (0) / CLEAN (2) / lỗi (1); ghi log + store/tot/verifications.jsonl.

Vì sao: mọi find trên snapshot không thể gọi "0day" nếu không biết còn sống ở
ToT hay không — mọi crash của mình hiện chưa có bước này (gap 2026-10-01).
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.builds import v8 as build_v8
from chromly.intel.watcher import mirror_dir_for

CRASH_RCS = {132, 133, 134, 136, 137, 138, 139}
CRASH_MARKERS = ("AddressSanitizer", "Check failed:", "Fatal error in", "Received signal")
VERIFY_FLAGS = ["--allow-natives-syntax", "--expose-gc", "--fuzzing"]
VERIFY_TIMEOUT = 60


def tot_state_path() -> Path:
    return paths.STORE_DIR / "tot.json"


def load_state() -> dict:
    p = tot_state_path()
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state: dict) -> None:
    tot_state_path().parent.mkdir(parents=True, exist_ok=True)
    tot_state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2))


def d8_path() -> Path:
    return paths.V8_ROOT / "out" / "tot" / "d8"


def d8_ready() -> bool:
    st = load_state()
    return bool(st.get("status") == "ok" and d8_path().is_file())


def resolve_tot_sha() -> str:
    """ToT sha từ mirror (watcher fetch FETCH_HEAD mỗi lượt)."""
    m = mirror_dir_for("v8")
    out = subprocess.run(
        ["git", "-C", str(m), "rev-parse", "FETCH_HEAD"],
        capture_output=True,
        text=True,
    )
    sha = out.stdout.strip()
    if not sha:
        raise RuntimeError(f"không lấy được FETCH_HEAD từ mirror {m}")
    return sha


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return out.stdout.strip()


def build(sha: str | None = None) -> dict:
    """Sync lên ToT → build tot → revert snapshot. Trả state mới."""
    root = paths.V8_ROOT
    if _git(root, "status", "--porcelain"):
        raise RuntimeError("V8 tree đang bẩn — commit/stash trước khi build ToT")
    snapshot = _git(root, "rev-parse", "HEAD")
    tot = sha or resolve_tot_sha()
    state = {
        "sha": tot,
        "snapshot": snapshot,
        "started": time.time(),
        "status": "running",
        "d8": str(d8_path()),
    }
    save_state(state)
    rc = -1
    revert_rc = -1
    try:
        rc = build_v8.run_build("tot", rev=tot)
        revert_rc = build_v8.sync(snapshot)
    finally:
        state.update(
            {
                "build_rc": rc,
                "revert_rc": revert_rc,
                "built_at": time.time(),
                "d8_exists": d8_path().is_file(),
                "status": "ok" if (rc == 0 and d8_path().is_file()) else "error",
            }
        )
        save_state(state)
    return state


def resolve_target(target: str) -> Path:
    """Nhận path .js hoặc hash crash (prefix) → file repro."""
    p = Path(target)
    if p.is_file():
        return p
    crashes = paths.STORE_DIR / "crashes"
    if crashes.is_dir():
        for d in sorted(crashes.iterdir()):
            if not d.is_dir():
                continue
            if d.name.startswith(target):
                for cand in sorted(d.glob("*.js")):
                    return cand
                for cand in sorted(d.glob("program_*")):
                    return cand
    tri = paths.STORE_DIR / "triage" / target
    if tri.is_dir():
        rep = tri / "repro.js"
        if rep.is_file():
            return rep
    raise FileNotFoundError(f"không thấy repro cho {target!r}")


def classify(rc: int, out: str) -> str:
    if rc < 0 or rc in CRASH_RCS:
        return "STILL-CRASHES"
    if any(m in out for m in CRASH_MARKERS):
        return "STILL-CRASHES"
    return "CLEAN"


def verify(target: str, flags: list[str] | None = None, timeout: int = VERIFY_TIMEOUT) -> dict:
    """Chạy repro trên ToT d8. Trả {target, verdict, rc, sha, log}."""
    if not d8_ready():
        raise RuntimeError("ToT d8 chưa sẵn sàng — chạy `chromly tot build` trước")
    repro = resolve_target(target)
    d8 = d8_path()
    st = load_state()
    cmd = [str(d8), *VERIFY_FLAGS, *(flags or []), str(repro)]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc = proc.returncode
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        rc = None
        out = f"(timeout {timeout}s) {(exc.stdout or '')}{(exc.stderr or '')}"
    verdict = "ERROR" if rc is None else classify(rc, out)
    wall = round(time.monotonic() - t0, 1)
    log_dir = paths.STORE_DIR / "tot"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log = log_dir / f"verify-{repro.stem[:40]}-{stamp}.log"
    log.write_text(f"$ {' '.join(cmd)}\nrc={rc} verdict={verdict} wall={wall}s\n\n{out[-20000:]}")
    rec = {
        "ts": time.time(),
        "target": str(repro),
        "sha": st.get("sha"),
        "verdict": verdict,
        "rc": rc,
        "wall_s": wall,
        "log": str(log),
    }
    with (log_dir / "verifications.jsonl").open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ── CLI ──────────────────────────────────────────────────────────────────────


def run_tot_cmd(args) -> int:
    sub = getattr(args, "tot_cmd", None)
    if sub == "build":
        try:
            st = build(sha=getattr(args, "sha", None))
        except RuntimeError as exc:
            print(f"tot build: {exc}")
            return 1
        if st["status"] == "ok":
            print(f"tot: OK sha={st['sha'][:12]} d8={st['d8']}")
            return 0
        print(f"tot: FAIL build_rc={st.get('build_rc')} revert_rc={st.get('revert_rc')}")
        return 1
    if sub == "status":
        st = load_state()
        if not st:
            print("tot: chưa build (chạy `chromly tot build`)")
            return 1
        age_h = (time.time() - st.get("built_at", 0)) / 3600.0
        print(
            f"tot: {st.get('status')} sha={str(st.get('sha'))[:12]} "
            f"age={age_h:.1f}h d8_exists={d8_path().is_file()}"
        )
        return 0 if st.get("status") == "ok" else 1
    if sub == "verify":
        target = getattr(args, "target", None)
        if not target:
            print("usage: chromly tot verify <file.js|crash_hash>")
            return 1
        flags = []
        extra = getattr(args, "flags", None)
        if extra:
            flags = re.findall(r"--[\w-]+(?:=[\w.-]+)?", extra)
        try:
            rec = verify(target, flags=flags)
        except (RuntimeError, FileNotFoundError) as exc:
            print(f"tot verify: {exc}")
            return 1
        print(f"tot verify: {rec['verdict']} (rc={rec['rc']}, {rec['wall_s']}s) → {rec['log']}")
        return 0 if rec["verdict"] == "STILL-CRASHES" else 2
    print("usage: chromly tot {build [--sha X]|status|verify <target> [--flags '...']}")
    return 2
