"""Lane rotator — xoay vòng toàn bộ per-target harness trên box nhỏ.

16 engine binary (M1-08) nhưng CPU chỉ đủ ~2 lane phụ ngoài `lfuzz-parser`/`lfuzz-wasm`
cố định. Rotator giữ `keep` lane phụ, mỗi lane chạy `slice_s` giây rồi đổi sang target kế
trong ROTATION. State bền: `store/fuzz/lane-rotation.json`.

Tương thích watchdog: `farm.down` xoá record trước khi kill → watchdog không respawn lane
đã xoay; lane chết tự nhiên (record còn) để watchdog lo. Engine binary thiếu → build lazy
(mất ~10-30s, một lần mỗi target).
"""

from __future__ import annotations

import contextlib
import json
import os
import pathlib
import signal
import sys
import time

from chromly.fuzz import engine, farm

ROTATION: list[str] = [
    "regexp",
    "json",
    "inspector",
    "wasm_streaming",
    "wasm_async",
    "wasm_code",
    "wasm_deopt",
    "wasm_init_expr",
    "multi_return",
    "wasm_compile",
    "wasm_compile_all",
    "wasm_compile_revec",
    "wasm_compile_simd",
    "wasm_compile_wasmgc",
]
DEFAULT_KEEP = 2
DEFAULT_SLICE_S = 7200.0
SWEEP_ENABLED = True  # tests monkeypatch False (sweep quét /proc thật)


def state_path():
    return farm.FUZZ_DIR / "lane-rotation.json"


def _load() -> dict:
    p = state_path()
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {"next": 0, "lanes": {}}


def _save(st: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        from pathlib import Path as _P

        cmd = _P(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return "lfuzz" in cmd


def lane_unit(target: str) -> farm.Unit:
    """Unit cho 1 target bất kỳ (như farm.engine_units nhưng theo tên engine.unit_for)."""
    name = engine.unit_for(target)
    base = farm.FUZZ_DIR / name
    (base / "corpus").mkdir(parents=True, exist_ok=True)
    (base / "artifacts").mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "chromly.cli.app", "fuzz", "lfuzz", "--unit", name]
    return farm.Unit(name, "libfuzzer", cmd, farm.LOGS_DIR / f"{name}.log")


def _sweep_orphans(st: dict) -> list[dict]:
    """Kill lane process không được track (bài học 08/10: record bị clobber lúc rotate-out
    → farm.down trả 'unknown' → process mồ côi chạy mãi).

    Chỉ quét khi rotation state tồn tại — tránh quét nhầm trong test/context lạ.
    """
    if not SWEEP_ENABLED or not state_path().is_file():
        return []
    tracked = set(st.get("lanes", {}))
    actions: list[dict] = []
    try:
        procs = os.listdir("/proc")
    except OSError:
        return actions
    for p in procs:
        if not p.isdigit():
            continue
        try:
            cmd = (
                pathlib.Path(f"/proc/{p}/cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
            )
        except OSError:
            continue
        if "chromly.cli.app" not in cmd or "fuzz lfuzz --unit lfuzz-" not in cmd:
            continue
        unit = cmd.split("--unit ")[-1].split()[0]
        if unit in tracked or unit in ("lfuzz-parser", "lfuzz-wasm"):
            continue
        if unit.removeprefix("lfuzz-") not in ROTATION:
            continue
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(int(p), signal.SIGTERM)
        actions.append({"unit": unit, "action": "sweep-orphan"})
    return actions


def tick(
    now: float | None = None, keep: int = DEFAULT_KEEP, slice_s: float = DEFAULT_SLICE_S
) -> list[dict]:
    """Một nhịp xoay lane. Trả danh sách action đã làm (cho log/aux)."""
    now = now if now is not None else time.time()
    st = _load()
    actions: list[dict] = _sweep_orphans(st)
    units = farm._load_state().get("units", {})

    # 1) lane hết slice → xoay ra; lane chết không record → rời vòng (record còn → watchdog lo)
    for unit, info in list(st["lanes"].items()):
        rec = units.get(unit)
        if rec is None:
            # record bị clobber (race) nhưng process còn sống → re-assert record
            pid = int(info.get("pid") or 0)
            if _pid_alive(pid):
                unit_obj = lane_unit(str(info.get("target")))
                farm.upsert_unit_record(
                    unit,
                    {
                        "pid": pid,
                        "started": info.get("started"),
                        "cmd": unit_obj.cmd,
                        "log": str(unit_obj.log),
                        "type": "libfuzzer",
                    },
                )
                actions.append({"unit": unit, "action": "reassert"})
                continue
            st["lanes"].pop(unit)
            actions.append({"unit": unit, "action": "gone"})
            continue
        if not farm._alive(rec):
            continue  # để watchdog restart
        if now - float(info.get("started", now)) >= slice_s:
            farm.down([unit])
            st["lanes"].pop(unit)
            actions.append({"unit": unit, "action": "rotate-out", "target": info.get("target")})

    # 2) bật thêm cho đủ `keep`
    active_targets = {v.get("target") for v in st["lanes"].values()}
    tries = 0
    while len(st["lanes"]) < keep and tries < len(ROTATION):
        tries += 1
        target = ROTATION[st.get("next", 0) % len(ROTATION)]
        st["next"] = (st.get("next", 0) + 1) % len(ROTATION)
        if target in active_targets:
            continue
        unit = engine.unit_for(target)
        if unit in st["lanes"] or unit in farm._load_state().get("units", {}):
            continue
        binp = engine.engine_bin(target)
        if not binp.is_file():
            try:
                res = engine.build_engine(target)
            except Exception as exc:  # noqa: BLE001 — skip target lỗi, thử target kế
                actions.append({"unit": unit, "action": "build-fail", "error": str(exc)})
                continue
            if not res.get("ok"):
                actions.append({"unit": unit, "action": "build-fail"})
                continue
            actions.append({"unit": unit, "action": "built", "wall_s": res.get("wall_s")})
        res = farm.up([lane_unit(target)])
        if res.get(unit, {}).get("status") in ("started", "already-running"):
            st["lanes"][unit] = {"target": target, "started": now, "pid": res[unit].get("pid")}
            actions.append({"unit": unit, "action": "rotate-in", "target": target})
        else:
            actions.append({"unit": unit, "action": "up-fail", "detail": res.get(unit)})

    _save(st)
    return actions


def run_lanes_cmd(args) -> int:
    keep = getattr(args, "keep", DEFAULT_KEEP)
    slice_s = getattr(args, "slice", DEFAULT_SLICE_S)

    def once() -> int:
        try:
            acts = tick(keep=keep, slice_s=slice_s)
        except Exception as exc:  # noqa: BLE001 — loop dài hạn
            print(f"[lanes] lỗi: {type(exc).__name__}: {exc}", flush=True)
            return 1
        for a in acts:
            print(
                f"[lanes] {a['action']} {a['unit']}"
                + (f" ({a.get('target')})" if a.get("target") else ""),
                flush=True,
            )
        if not acts:
            print("[lanes] ổn định — không đổi", flush=True)
        return 0

    if getattr(args, "loop", False):
        interval = getattr(args, "interval", 600.0)
        while True:
            once()
            time.sleep(interval)
    return once()
