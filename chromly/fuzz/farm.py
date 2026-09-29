"""Fuzz farm — quản worker theo unit (§5.2).

M1: unit `fuzzilli` (--jobs=4 thread workers, corpus sync full) + (M1-03) unit libFuzzer ×2.
Chạy nice 5, kill theo process group, state ở store/fuzz/state.json.
Format log fuzzilli (`Execs/second`) verify ở smoke M1-01 — parser tolerant.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from chromly import paths

FUZZILLI_DIR = Path.home() / "tools" / "fuzzilli"
FUZZILLI_BIN = FUZZILLI_DIR / ".build" / "release" / "FuzzilliCli"
SWIFT_BIN = Path.home() / ".local" / "share" / "swiftly" / "bin"

FUZZ_DIR = paths.STORE_DIR / "fuzz"
STATE_PATH = FUZZ_DIR / "state.json"
LOGS_DIR = FUZZ_DIR / "logs"

JOBS = 4
NICE = 5

_EXECS_RE = re.compile(r"(?:Execs\s*/\s*Second:|exec/s:)\s*([\d.]+)")
LIBFUZZER_TARGETS = {
    "libfuzzer-parser": "v8_simple_parser_fuzzer",
    "libfuzzer-wasm": "v8_simple_wasm_module_fuzzer",
}


@dataclass
class Unit:
    name: str
    type: str  # fuzzilli | libfuzzer
    cmd: list[str]
    log: Path


def d8_path() -> Path:
    return paths.V8_ROOT / "out" / "fuzzilli" / "d8"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{SWIFT_BIN}:{env.get('PATH', '')}"
    return env


def fuzzilli_unit() -> Unit:
    storage = FUZZ_DIR / "fuzzilli"
    storage.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(FUZZILLI_BIN),
        "--profile=v8",
        f"--jobs={JOBS}",
        f"--storagePath={storage}",
        "--exportStatistics",
        "--statisticsExportInterval=1",
        "--logLevel=info",
    ]
    if any(storage.iterdir()):
        # fuzzilli từ chối storagePath non-empty nếu thiếu --resume/--overwrite
        cmd.append("--resume")
    cmd.append(str(d8_path()))
    return Unit("fuzzilli", "fuzzilli", cmd, LOGS_DIR / "fuzzilli.log")


def libfuzzer_units() -> list[Unit]:
    """2 unit libFuzzer (parser · wasm) — v0 replay wrapper (V8 standalone thiếu engine).
    Xem chromly/fuzz/replay.py + task M1-08 (engine thật)."""
    units = []
    for name, binname in LIBFUZZER_TARGETS.items():
        if not (paths.V8_ROOT / "out" / "libfuzzer" / binname).is_file():
            continue
        base = FUZZ_DIR / name
        (base / "corpus").mkdir(parents=True, exist_ok=True)
        (base / "artifacts").mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "chromly.cli.app", "fuzz", "lfreplay", "--unit", name]
        units.append(Unit(name, "libfuzzer", cmd, LOGS_DIR / f"{name}.log"))
    return units


def default_units() -> list[Unit]:
    return [fuzzilli_unit(), *libfuzzer_units()]


def _v8_rev() -> str:
    root = paths.V8_ROOT
    if not (root / ".git").is_dir():
        return "?"
    out = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip() or "?"


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"units": {}}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _alive(rec: dict) -> bool:
    pid = rec.get("pid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        cmdline = cmdline_path.read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return Path(rec["cmd"][0]).name in cmdline


def _rss_mb(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def latest_stats_execs(storage: Path) -> float | None:
    """execs/s từ stats JSON của fuzzilli (storagePath/stats/<date>.json, --exportStatistics)."""
    stats_dir = storage / "stats"
    if not stats_dir.is_dir():
        return None
    jsons = sorted(stats_dir.glob("*.json"))
    if not jsons:
        return None
    try:
        data = json.loads(jsons[-1].read_text())
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("execsPerSecond")
    return float(value) if isinstance(value, (int, float)) else None


def parse_execs(log: Path) -> float | None:
    """Execs/s cuối cùng trong log — fuzzilli (`Execs/second:`) hoặc libFuzzer (`exec/s:`)."""
    try:
        text = log.read_text(errors="replace")
    except OSError:
        return None
    last = None
    for m in _EXECS_RE.finditer(text):
        last = float(m.group(1))
    return last


def up(units: list[Unit] | None = None) -> dict:
    FUZZ_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    rev = _v8_rev()
    started: dict = {}
    for unit in units or default_units():
        rec = state["units"].get(unit.name)
        if rec and _alive(rec):
            started[unit.name] = {"status": "already-running", "pid": rec["pid"]}
            continue
        binary = Path(unit.cmd[0])
        if not binary.is_file() and not shutil.which(unit.cmd[0]):
            started[unit.name] = {"status": "missing-binary", "bin": unit.cmd[0]}
            continue
        log = unit.log.open("a")
        proc = subprocess.Popen(
            ["nice", "-n", str(NICE), *unit.cmd],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=_env(),
            cwd=str(paths.REPO_ROOT),
        )
        state["units"][unit.name] = {
            "pid": proc.pid,
            "started": time.time(),
            "cmd": unit.cmd,
            "log": str(unit.log),
            "type": unit.type,
            "v8_rev": rev,
        }
        started[unit.name] = {"status": "started", "pid": proc.pid}
    _save_state(state)
    return started


def down(names: list[str] | None = None, grace: float = 30.0) -> dict:
    state = _load_state()
    targets = names or list(state["units"].keys())
    stopped: dict = {}
    for name in targets:
        rec = state["units"].get(name)
        if not rec:
            stopped[name] = "unknown"
            continue
        pid = rec["pid"]
        if not _alive(rec):
            stopped[name] = "not-running"
            state["units"].pop(name, None)
            continue
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and _alive(rec):
            time.sleep(0.5)
        if _alive(rec):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pid, signal.SIGKILL)
            stopped[name] = "killed"
        else:
            stopped[name] = "stopped"
        state["units"].pop(name, None)
    _save_state(state)
    return stopped


def status() -> dict:
    state = _load_state()
    out: dict = {}
    for name, rec in state["units"].items():
        alive = _alive(rec)
        info = {
            "alive": alive,
            "pid": rec.get("pid"),
            "type": rec.get("type"),
            "v8_rev": rec.get("v8_rev"),
        }
        if alive:
            info["uptime_s"] = round(time.time() - rec.get("started", time.time()))
            info["rss_mb"] = _rss_mb(rec["pid"])
            execs = None
            if rec.get("type") == "fuzzilli":
                execs = latest_stats_execs(FUZZ_DIR / "fuzzilli")
            if execs is None:
                execs = parse_execs(Path(rec["log"]))
            info["execs_per_sec"] = execs
        out[name] = info
    return out


def run_fuzz_cmd(args) -> int:
    cmd = getattr(args, "fuzz_cmd", None)
    if cmd == "up":
        result = up()
        for name, info in result.items():
            print(f"{name}: {info['status']}" + (f" pid={info['pid']}" if "pid" in info else ""))
        missing = [n for n, i in result.items() if i["status"] == "missing-binary"]
        return 1 if missing else 0
    if cmd == "down":
        result = down()
        for name, what in result.items():
            print(f"{name}: {what}")
        return 0
    if cmd == "status":
        st = status()
        if not st:
            print("farm trống — `chromly fuzz up` để chạy")
            return 0
        for name, info in st.items():
            if info["alive"]:
                execs = info.get("execs_per_sec")
                execs_s = f"{execs:.1f}/s" if isinstance(execs, float) else "—"
                print(
                    f"{name:<10} alive  pid={info['pid']}  up={info['uptime_s']}s  "
                    f"rss={info['rss_mb']}MB  execs={execs_s}"
                )
            else:
                print(f"{name:<10} DEAD   pid={info['pid']} (watchdog sẽ restart ở M1-04)")
        return 0
    if cmd == "watchdog":
        from chromly.fuzz.watchdog import run_watchdog

        return run_watchdog(
            once=getattr(args, "once", False), interval=getattr(args, "interval", 60.0)
        )
    if cmd == "ingest":
        from chromly.fuzz.crashes import run_ingest

        return run_ingest(
            once=getattr(args, "once", False), interval=getattr(args, "interval", 15.0)
        )
    if cmd == "metrics":
        from chromly.fuzz.metrics import run_sampler

        return run_sampler(
            once=getattr(args, "once", False), interval=getattr(args, "interval", 60.0)
        )
    if cmd == "corpus":
        from chromly.fuzz import corpus

        sub = getattr(args, "corpus_cmd", None)
        if sub == "sync":
            stats = corpus.sync(limit=getattr(args, "limit", 120))
            print(f"corpus sync: {stats}")
            return 0 if stats["ok"] > 0 or stats["skip"] > 0 else 1
        if sub == "import":
            rc = corpus.import_to_storage()
            print(f"corpus import rc={rc} (log: store/fuzz/logs/corpus-import.log)")
            return 0 if rc == 0 else 1
        if sub == "trim":
            cands = corpus.trim(days=getattr(args, "days", 30), apply=getattr(args, "apply", False))
            mode = "đã xoá" if getattr(args, "apply", False) else "dry-run"
            print(f"corpus trim: {len(cands)} ứng viên ({mode})")
            return 0
        print("usage: chromly fuzz corpus {sync|import|trim}")
        return 2
    if cmd == "lfreplay":
        from chromly.fuzz.replay import run_lfreplay

        return run_lfreplay(
            args.unit,
            interval=getattr(args, "interval", 60.0),
            once=getattr(args, "once", False),
        )
    print("usage: chromly fuzz {up|down|status|watchdog|ingest|metrics|corpus|lfreplay}")
    return 2
