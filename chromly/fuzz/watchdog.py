"""Watchdog — M1-04: hang >HANG_S (mặc định 120s) → kill + restart + event; crash-loop → degraded.

Hang detection: tổng CPU ticks của process tree không tăng qua cửa sổ HANG_S (log-based chỉ là phụ).
Loop: `chromly fuzz watchdog [--interval 60]` — systemd timer gọi `--once` ở M4.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import time
from pathlib import Path

from chromly.fuzz import farm

EVENTS_PATH = farm.FUZZ_DIR / "events.jsonl"
# Tuning note 2026-10-01: plan §5.2 ghi 120s; chọn 180s mặc định vì replay bursty gây
# false-positive kill; fuzzilli riêng 300s (corpus import/GC pause dài). Override qua env.
HANG_S = float(os.environ.get("CHROMLY_WATCHDOG_HANG_S", "180"))
HANG_BY_UNIT = {"fuzzilli": 300.0}
CRASH_LOOP_N = 3
CRASH_LOOP_WINDOW = 600.0
DEGRADED_COOLDOWN = 1800.0
FRESH_LOG_S = 120.0
FRESH_STATS_S = 180.0
CASE_STALE_S = 6 * 3600.0 + 600.0  # case RUNNING quá hạn (plan §10.2) → reap


def _fresh_activity(rec: dict, now: float, window: float) -> bool:
    """Unit được coi là còn sống nếu log/stats mới ghi (tránh kill oan bursty/idle phase)."""
    log = Path(rec.get("log", ""))
    try:
        if log.is_file() and now - log.stat().st_mtime < window:
            return True
    except OSError:
        pass
    if rec.get("type") == "fuzzilli":
        stats = farm.FUZZ_DIR / "fuzzilli" / "stats"
        try:
            newest = max(stats.glob("*.json"), key=lambda p: p.stat().st_mtime, default=None)
            if newest is not None and now - newest.stat().st_mtime < max(window, FRESH_STATS_S):
                return True
        except OSError:
            pass
    return False


def append_event(event: str, unit: str, detail: dict | None = None) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a") as fh:
        line = {"ts": time.time(), "event": event, "unit": unit}
        line.update(detail or {})
        fh.write(json.dumps(line) + "\n")


def cpu_ticks_tree(pid: int) -> int | None:
    """Tổng utime+stime (clock ticks) của pid + toàn bộ descendants."""
    procs: dict[int, tuple[int, int]] = {}
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            stat = (p / "stat").read_text()
        except OSError:
            continue
        rp = stat.rfind(")")
        if rp < 0:
            continue
        fields = stat[rp + 2 :].split()
        try:
            ppid = int(fields[1])
            ticks = int(fields[11]) + int(fields[12])
        except (IndexError, ValueError):
            continue
        procs[int(p.name)] = (ppid, ticks)

    children: dict[int, list[int]] = {}
    for p, (ppid, _) in procs.items():
        children.setdefault(ppid, []).append(p)

    seen: set[int] = set()
    stack = [pid]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(children.get(cur, []))

    total = 0
    found = False
    for p in seen:
        if p in procs:
            found = True
            total += procs[p][1]
    return total if found else None


def _kill_tree(pid: int, grace: float = 10.0) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.5)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)


def _log_has(rec: dict, needle: str, tail_bytes: int = 30000) -> bool:
    try:
        with open(rec["log"], "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            return needle.encode() in fh.read()
    except OSError:
        return False


def _restart(state: dict, name: str, rec: dict, reason: str, now: float) -> dict:
    pid = rec.get("pid")
    if pid:
        _kill_tree(pid)
    append_event("kill", name, {"reason": reason, "pid": pid})

    hist = [t for t in rec.get("restarts", []) if now - t < CRASH_LOOP_WINDOW]
    hist.append(now)
    if len(hist) >= CRASH_LOOP_N:
        farm.merge_unit_fields(name, {"degraded": True, "degraded_at": now, "restarts": hist})
        append_event("degraded", name, {"restarts": len(hist)})
        return {"unit": name, "action": "degraded", "reason": reason}

    unit = None
    if rec.get("type") == "fuzzilli" and (
        reason == "cooldown-recovery" or _log_has(rec, "Corpus import aborted")
    ):
        # corpus hỏng làm import abort (signal 6) — cách ly để start sạch, giữ crashes/stats
        moved = farm.quarantine_fuzzilli_corpus()
        append_event("corpus-quarantine", name, {"reason": reason, "moved": moved})
        unit = farm.fuzzilli_unit()
    else:
        for u in farm.default_units():
            if u.name == name:
                unit = u
                break
    if unit is None:
        if not rec.get("type") or not rec.get("cmd"):
            # record rỗng/hỏng (vd farm.up fail lúc restart) — bỏ qua record, không chết
            append_event("unit-broken", name, {"reason": reason})
            return {"unit": name, "action": "skip", "reason": f"{reason}: record thiếu type/cmd"}
        unit = farm.Unit(name, rec["type"], rec["cmd"], Path(rec.get("log", "")))
    farm.up([unit])
    state2 = farm._load_state()
    rec2 = state2["units"].get(name)
    if not rec2 or "type" not in rec2:
        # farm.up không đăng ký được unit (missing-binary...) — không ghi record rỗng
        # (record rỗng làm tick sau KeyError chết watchdog)
        append_event("restart-failed", name, {"reason": reason})
        return {"unit": name, "action": "restart-failed", "reason": reason}
    farm.merge_unit_fields(name, {"restarts": hist, "degraded": False})
    append_event("restart", name, {"reason": reason})
    return {"unit": name, "action": "restarted", "reason": reason}


def _aux_check(state: dict) -> list[dict]:
    """Self-heal aux loops (trừ chính watchdog) — respawn khi chết."""
    from chromly.orchestrator import supervisor

    actions: list[dict] = []
    aux = state.setdefault("aux", {})
    for name, rec in list(aux.items()):
        if name == "watchdog":
            continue
        if not farm._alive(rec):
            new_rec = supervisor._spawn_aux(name)
            aux[name] = new_rec
            farm.merge_aux_record(name, new_rec)
            append_event("aux-restart", name, {"pid": new_rec["pid"]})
            actions.append({"unit": f"aux:{name}", "action": "restarted", "reason": "dead"})
    return actions


def _case_stale_check(now: float) -> list[dict]:
    """Case RUNNING quá CASE_STALE_S không chuyển trạng thái → đánh TIMEOUT (chống kẹt vĩnh viễn).

    Runner đã tự bọc try/except (không để kẹt), đây là lưới an toàn thứ hai cho trường hợp
    process runner bị giết giữa chừng (OOM, kill ngoài ý muốn).
    """
    from chromly.case import pipeline

    actions: list[dict] = []
    cd = pipeline.cases_dir()
    if not cd.is_dir():
        return actions
    for d in sorted(cd.glob("CASE-*")):
        mp = d / "meta.json"
        if not mp.is_file():
            continue
        try:
            meta = json.loads(mp.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("state") != "RUNNING":
            continue
        age = now - mp.stat().st_mtime
        if age < CASE_STALE_S:
            continue
        with contextlib.suppress(Exception):
            pipeline.set_state(d.name, "TIMEOUT")
        append_event("case-stale", d.name, {"age_s": int(age)})
        actions.append({"unit": d.name, "action": "case-timeout", "reason": "stale-running"})
    return actions


def tick(now: float | None = None, hang_s: float | None = None) -> list[dict]:
    now = now if now is not None else time.time()
    hang_s = hang_s if hang_s is not None else HANG_S
    state = farm._load_state()
    actions: list[dict] = []

    for name, rec in list(state["units"].items()):
        if rec.get("degraded"):
            # tự hồi sau cooldown
            if now - rec.get("degraded_at", 0) >= DEGRADED_COOLDOWN:
                rec["degraded"] = False
                rec["restarts"] = []
                state["units"][name] = rec
                farm._save_state(state)
                append_event("recover", name, {"cooldown_s": DEGRADED_COOLDOWN})
                actions.append(_restart(state, name, rec, "cooldown-recovery", now))
                state = farm._load_state()
            continue
        alive = farm._alive(rec)
        if not alive:
            actions.append(_restart(state, name, rec, "dead", now))
            state = farm._load_state()  # restart đã ghi state mới — không được ghi đè
            continue

        ticks = cpu_ticks_tree(rec["pid"])
        if ticks is None:
            continue
        prev = rec.get("watchdog") or {}
        unit_hang = HANG_BY_UNIT.get(name, hang_s)
        if _fresh_activity(rec, now, min(FRESH_LOG_S, unit_hang)):
            # còn hoạt động (log/stats mới) → reset baseline, không tính là hang
            farm.merge_unit_fields(name, {"watchdog": {"ticks": ticks, "ts": now}})
            continue
        if "ticks" in prev and ticks <= prev["ticks"] and now - prev["ts"] >= unit_hang:
            actions.append(_restart(state, name, rec, "hang", now))
            state = farm._load_state()
            continue
        if "ticks" not in prev or ticks > prev["ticks"]:
            farm.merge_unit_fields(name, {"watchdog": {"ticks": ticks, "ts": now}})

    actions.extend(_aux_check(state))
    actions.extend(_case_stale_check(now))
    return actions


def run_watchdog(once: bool = False, interval: float = 60.0) -> int:
    while True:
        actions = tick()
        for a in actions:
            print(f"watchdog: {a['unit']} {a['action']} ({a['reason']})", flush=True)
        if once:
            return 0
        time.sleep(interval)
