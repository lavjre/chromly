"""S1 — System One decision layer (Jev-style) cho chromly (gap 0day: chọn việc đáng làm).

Kiến trúc: **server local giữ model thường trú** (laya `laya-serve`, CPU) + client HTTP.
Vì sao server: load model ~1-2 phút, 1 quyết định ~6-15s trên CPU — load per-call là vô dụng;
server chạy 1 lần như aux loop (watchdog giữ sống), client chỉ POST `/v1/systemone`.

- `chromly s1 serve` — chạy server (dùng trong AUX_SPECS; env LAYA_PORT=7391, LAYA_MODELS=english)
- `chromly s1 check` — smoke 1 quyết định qua server
- `chromly s1 triage <hash>` — chấm 1 crash: exploitable / ladder / impact / next

Backend có thể thay bằng TypeSafe Jev API sau (cùng shape /v1/systemone) — chỉ đổi S1_URL.
Fallback in-process khi server chết (chậm: load model mỗi tiến trình — chỉ dùng khi bí).
Lưu kết quả: store/s1/<hash>.json.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from chromly import paths

S1_URL = os.environ.get("CHROMLY_S1_URL", "http://127.0.0.1:7391")
S1_PORT = os.environ.get("CHROMLY_S1_PORT", "7391")
_ROUTER = None


def s1_dir() -> Path:
    return paths.STORE_DIR / "s1"


def available() -> bool:
    try:
        import laya  # noqa: F401
    except ImportError:
        return False
    return True


def _router():
    global _ROUTER
    if _ROUTER is None:
        from laya import Router

        _ROUTER = Router()
    return _ROUTER


def server_up(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{S1_URL}/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def ask(state: str | dict, questions: dict) -> dict:
    """Một lượt S1 — HTTP trước (server thường trú), fallback in-process."""
    payload = json.dumps({"state": state, "questions": questions}).encode()
    try:
        req = urllib.request.Request(
            f"{S1_URL}/v1/systemone", payload, {"content-type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
            res["elapsed_ms"] = round(float(r.headers.get("X-Inference-Time-Ms") or 0))
            return res
    except (urllib.error.URLError, OSError) as exc:
        if not available():
            raise RuntimeError(
                f"S1 server không sống ({exc}) — chạy `chromly s1 serve` (hoặc cài laya)"
            ) from exc
    router = _router()  # fallback: load trong tiến trình (chậm)
    t0 = time.monotonic()
    res = router.predict(state, questions)
    res["elapsed_ms"] = round((time.monotonic() - t0) * 1000)
    return res


# ── crash triage ─────────────────────────────────────────────────────────────

CRASH_QUESTIONS = {
    "kind": {
        "type": "choice",
        "instructions": "What kind of failure does this crash output show?",
        "criteria": {
            "check-abort": "a debug check or assertion aborted the process (DCHECK/CHECK/FATAL)",
            "oob-read": "out-of-bounds memory read",
            "oob-write": "out-of-bounds memory write",
            "use-after-free": "use of freed or stale memory",
            "type-confusion": "an object treated as another type",
            "miscompile": "the engine computed wrong code or wrong results",
            "stack-overflow": "call stack exhausted",
            "out-of-memory": "memory limit hit",
            "test-api-misuse": "test-only intrinsics or unsafe developer flags misused",
            "false-positive": "not a real engine bug (harness artifact, flag conflict)",
            "other": "none of the above",
        },
    },
    "exploitable": {
        "type": "noul",
        "instructions": (
            "Does this crash provide a controllable memory primitive — out-of-bounds access "
            "with an attacker-controlled index/offset, use-after-free with reclaim, or type "
            "confusion — that could be developed into engine memory corruption? Debug-check "
            "aborts, assertion failures that only crash, and test-API-only issues do NOT count."
        ),
    },
    "impact": {
        "type": "choice",
        "instructions": "Worst-case impact class if a skilled researcher weaponized this crash",
        "criteria": {
            "none": "not a security issue (test artifact, false positive, unreachable)",
            "dos": "denial of service only (abort/check/hang), no memory control",
            "info-leak": "leaks memory contents but no write primitive",
            "memory-corruption": "use-after-free / OOB write / type confusion with some control",
            "sandbox-rce": "full control flow or sandbox escape potential",
        },
    },
    "ladder": {
        "type": "noul",
        "instructions": (
            "Is there enough attacker control here to attempt an exploit ladder "
            "(addrof/fakeobj, then arbitrary read/write)? This requires a value or index "
            "the attacker influences, not just a crash."
        ),
    },
    "next": {
        "type": "choice",
        "instructions": "What should the pipeline do with this crash next?",
        "criteria": {
            "close": "not a bug / false positive — close it",
            "analyze-more": "unclear potential — needs deeper manual analysis",
            "attempt-ladder": "promising primitive — attempt the exploit ladder",
            "report": "submittable security bug — draft a report",
        },
    },
}

_STACK_MAX_LINES = 14
_REPRO_MAX_LINES = 22
_STATE_MAX_CHARS = 1800
_PATH_RE = re.compile(r"/[\w./+-]*/out/(\w+)/d8")
_ADDR_RE = re.compile(r"(pc: |\[|\[pc=)0x[0-9a-f]{6,}\]?|\[0x[0-9a-f]+\]")
_BARE_ADDR_RE = re.compile(r"0x[0-9a-f]{6,}")


def _sanitize(txt: str) -> str:
    """Bỏ path build + địa chỉ trong stack — giảm token, giảm nhiễu cho model."""
    txt = _PATH_RE.sub(r"d8<out/\1>", txt)
    txt = _ADDR_RE.sub("", txt)
    txt = _BARE_ADDR_RE.sub("0xADDR", txt)
    return re.sub(r" +", " ", txt)


def _head(path: Path, n: int) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    out = []
    for line in lines:
        if line.strip():
            out.append(_sanitize(line))
        if len(out) >= n:
            break
    return "\n".join(out)


def build_crash_state(hash_or_prefix: str, include_pipeline_label: bool = True) -> tuple[str, Path]:
    """Text state cho S1 từ crash store (không cần model). Trả (state, crash_dir).

    `include_pipeline_label=False`: bỏ fault_label (rò nhãn khi train — heuristic chính là
    thứ S1 cần vượt qua, không phải để copy).
    """
    crashes = paths.STORE_DIR / "crashes"
    d = next((p for p in sorted(crashes.iterdir()) if p.name.startswith(hash_or_prefix)), None)
    if d is None or not d.is_dir():
        raise FileNotFoundError(f"không thấy crash {hash_or_prefix}")
    meta = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        meta = json.loads((d / "meta.json").read_text())
    fault = meta.get("fault_type")
    severity = ""
    if not fault:
        with contextlib.suppress(Exception):
            from chromly.store import db

            con = db.ensure_db()
            try:
                row = con.execute(
                    "SELECT fault_type, severity FROM crashes WHERE hash LIKE ?",
                    (f"{d.name[:12]}%",),
                ).fetchone()
            finally:
                con.close()
            if row:
                fault = row["fault_type"] or "?"
                severity = f" (score {row['severity']})"
    tri = paths.STORE_DIR / "triage" / d.name
    repro = next(iter(sorted(d.glob("*.js"))), None) or (tri / "repro.js")
    flags = ""
    fl = tri / "repro.flags.txt"
    if fl.is_file():
        flags = fl.read_text().strip().replace("\n", " ")

    parts = [
        "# V8 crash under triage (d8, snapshot build)",
    ]
    if include_pipeline_label:
        parts.append(f"fault_label_from_pipeline: {(fault or 'unknown')}{severity}")
    parts.append(f"source: {meta.get('unit') or meta.get('source') or 'unknown'}")
    if flags:
        parts.append(f"repro_flags: {flags}")
    crash_txt = _head(tri / "asan.txt", _STACK_MAX_LINES)
    if crash_txt:
        parts.append("## crash output (head)\n" + crash_txt)
    repro_txt = _head(repro, _REPRO_MAX_LINES) if repro else ""
    if repro_txt:
        parts.append("## repro.js (head)\n" + repro_txt)
    case_verdict = ""
    if paths.CASES_DIR.is_dir():
        for cd in sorted(paths.CASES_DIR.glob("CASE-*")):
            with contextlib.suppress(OSError, json.JSONDecodeError):
                if json.loads((cd / "meta.json").read_text()).get("crash_hash") == d.name:
                    v = cd / "VERDICT.md"
                    if v.is_file():
                        case_verdict = _head(v, 12)
    if case_verdict:
        parts.append("## agent case verdict (head)\n" + case_verdict)
    state = "\n\n".join(parts)
    if len(state) > _STATE_MAX_CHARS:
        state = state[:_STATE_MAX_CHARS] + "\n…(trimmed)"
    return state, d


def triage_crash(hash_or_prefix: str) -> dict:
    """Chạy S1 trên 1 crash, lưu store/s1/<hash>.json, trả kết quả."""
    state, d = build_crash_state(hash_or_prefix)
    res = ask(state, CRASH_QUESTIONS)
    answers = res.get("answers", {})
    out = {
        "hash": d.name,
        "ts": time.time(),
        "elapsed_ms": res.get("elapsed_ms"),
        "model": res.get("model"),
        "routing": res.get("routing"),
        "exploitable": answers.get("exploitable", {}).get("noul"),
        "ladder": answers.get("ladder", {}).get("noul"),
        "impact": answers.get("impact", {}).get("choice"),
        "next": answers.get("next", {}).get("choice"),
        "answers": answers,
    }
    s1_dir().mkdir(parents=True, exist_ok=True)
    (s1_dir() / f"{d.name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def load_result(hash_or_prefix: str) -> dict | None:
    if not s1_dir().is_dir():
        return None
    hit = next(iter(sorted(s1_dir().glob(f"{hash_or_prefix}*.json"))), None)
    if hit is None:
        return None
    try:
        return json.loads(hit.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ── CLI ──────────────────────────────────────────────────────────────────────


def run_s1_cmd(args) -> int:
    sub = getattr(args, "s1_cmd", None)
    if sub == "serve":
        binp = Path(sys.executable).parent / "laya-serve"
        if not binp.is_file():
            print(
                "s1 serve: thiếu laya-serve — cài: "
                "uv pip install --python .venv/bin/python 'laya[serve]'"
            )
            return 1
        env = dict(os.environ)
        env.setdefault("LAYA_PORT", S1_PORT)
        env.setdefault("LAYA_MODELS", "english")
        import subprocess

        return subprocess.call([str(binp)], env=env)
    if sub == "check":
        if not available():
            print("s1: thiếu laya — cài: uv pip install --python .venv/bin/python laya")
            return 1
        if not server_up():
            print(f"s1: server {S1_URL} không sống — chạy `chromly s1 serve` (hoặc `chromly up`)")
            return 1
        res = ask(
            "d8 crashed with a CHECK failure in a debug assertion; no memory access involved.",
            {"exploitable": CRASH_QUESTIONS["exploitable"]},
        )
        p = res.get("answers", {}).get("exploitable", {}).get("noul")
        print(f"s1 check: OK — P(exploitable)={p} ({res.get('elapsed_ms')}ms, {S1_URL})")
        return 0
    if sub == "triage":
        target = getattr(args, "target", None)
        if not target:
            print("usage: chromly s1 triage <hash|prefix>")
            return 2
        if not available():
            print("s1: thiếu laya — cài: uv pip install --python .venv/bin/python laya")
            return 1
        try:
            out = triage_crash(target)
        except FileNotFoundError as exc:
            print(f"s1: {exc}")
            return 1
        print(
            f"s1 {out['hash'][:12]}: exploitable={out['exploitable']:.2f} "
            f"ladder={out['ladder']:.2f} impact={out['impact']} next={out['next']} "
            f"({out['elapsed_ms']}ms)"
        )
        return 0
    if sub == "dataset":
        from chromly.s1.dataset import run_dataset_cmd

        return run_dataset_cmd(args)
    if sub == "finetune":
        from chromly.s1.finetune import run_finetune_cmd

        return run_finetune_cmd(args)
    if sub == "eval-ft":
        from chromly.s1.eval import run_eval_cmd

        return run_eval_cmd(args)
    print("usage: chromly s1 {serve|check|triage <hash>|dataset|finetune|eval-ft}")
    return 2
