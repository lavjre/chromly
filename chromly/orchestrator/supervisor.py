"""Supervisor umbrella — M4-07: `chromly up/down` (tạm trước systemd §10.1).

up  = farm workers + aux loops (watchdog · ingest · metrics · intel · sched)
down = dừng tất cả sạch sẽ.
Aux records sống chung store/fuzz/state.json mục "aux".
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time

from chromly import paths
from chromly.fuzz import farm

AUX_SPECS: dict[str, list[str]] = {
    "watchdog": ["fuzz", "watchdog", "--interval", "60"],
    "ingest": ["fuzz", "ingest", "--interval", "15"],
    "metrics": ["fuzz", "metrics", "--interval", "60"],
    "intel": ["intel", "watch"],
    "sched": ["sched", "loop", "--interval", "60"],
}


def _spawn_aux(name: str, rec: dict | None) -> dict:
    log = farm.LOGS_DIR / f"aux-{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "chromly.cli.app", *AUX_SPECS[name]]
    proc = subprocess.Popen(
        cmd,
        stdout=log.open("a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(paths.REPO_ROOT),
        env=os.environ.copy(),
    )
    return {"pid": proc.pid, "cmd": cmd, "log": str(log)}


def up_all() -> dict:
    res = {"farm": farm.up()}
    state = farm._load_state()
    aux = state.setdefault("aux", {})
    for name in AUX_SPECS:
        rec = aux.get(name)
        if rec and farm._alive(rec):
            res[name] = "already-running"
            continue
        aux[name] = _spawn_aux(name, rec)
        res[name] = f"started pid={aux[name]['pid']}"
    farm._save_state(state)
    return res


def _kill_rec(rec: dict, grace: float = 10.0) -> str:
    pid = rec.get("pid")
    if not pid:
        return "no-pid"
    if not farm._alive(rec):
        return "not-running"
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and farm._alive(rec):
        time.sleep(0.5)
    if farm._alive(rec):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGKILL)
        return "killed"
    return "stopped"


def down_all() -> dict:
    res = {"farm": farm.down()}
    state = farm._load_state()
    aux = state.get("aux", {})
    for name, rec in list(aux.items()):
        res[name] = _kill_rec(rec)
        aux.pop(name, None)
    state["aux"] = aux
    farm._save_state(state)
    return res


def run_supervisor_cmd(args) -> int:
    cmd = getattr(args, "cmd", None)
    if cmd == "up":
        for name, note in up_all().items():
            if isinstance(note, dict):
                for n2, v in note.items():
                    print(f"farm.{n2}: {v}")
            else:
                print(f"{name}: {note}")
        return 0
    if cmd == "down":
        for name, note in down_all().items():
            if isinstance(note, dict):
                for n2, v in note.items():
                    print(f"farm.{n2}: {v}")
            else:
                print(f"{name}: {note}")
        return 0
    return 2
