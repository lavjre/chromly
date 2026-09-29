"""chromly doctor — kiểm tra môi trường VM theo §13 (M0). Chỉ đọc, không sửa gì."""

from __future__ import annotations

import grp
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from chromly import paths

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"
FIX_BOOTSTRAP = "sudo bash infra/bootstrap.sh"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def _rc(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _active(unit: str) -> str:
    _, out = _rc(["systemctl", "is-active", unit])
    return out.splitlines()[0] if out else "unknown"


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.status == FAIL for c in checks) else 0


# ---------------------------------------------------------------- checks


def check_swap() -> Check:
    total_kb = 0
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("SwapTotal:"):
            total_kb = int(line.split()[1])
    gb = total_kb / 1024 / 1024
    if gb >= 15.5:
        return Check("swap", OK, f"{gb:.1f}G")
    if gb >= 7.5:
        return Check("swap", WARN, f"{gb:.1f}G (<16G)", FIX_BOOTSTRAP)
    return Check("swap", FAIL, f"{gb:.1f}G (<16G)", FIX_BOOTSTRAP)


def check_slices() -> Check:
    missing = []
    for s in ("svc", "build", "fuzz", "case"):
        unit_file = Path(f"/etc/systemd/system/chromly-{s}.slice")
        if not unit_file.is_file():
            missing.append(s)
            continue
        rc, out = _rc(["systemctl", "show", "-p", "LoadState", f"chromly-{s}.slice"])
        if rc != 0 or "LoadState=loaded" not in out:
            missing.append(s)
    if missing:
        return Check("slices", FAIL, f"thiếu/không load: {', '.join(missing)}", FIX_BOOTSTRAP)
    return Check("slices", OK, "svc · build · fuzz · case — loaded")


def check_docker() -> Check:
    docker = shutil.which("docker")
    if not docker:
        return Check("docker", FAIL, "không có docker", FIX_BOOTSTRAP)
    _, out = _rc([docker, "--version"])
    ver = out.split(",")[0] if out else "?"
    try:
        in_group = grp.getgrnam("docker").gr_gid in os.getgroups()
    except KeyError:
        in_group = False
    if in_group:
        return Check("docker", OK, ver)
    return Check(
        "docker", WARN, f"{ver}; user chưa trong group docker", "logout/in hoặc newgrp docker"
    )


def check_earlyoom() -> Check:
    state = _active("earlyoom")
    if state == "active":
        return Check("earlyoom", OK, "active")
    return Check("earlyoom", FAIL, state, FIX_BOOTSTRAP)


def check_sysctl() -> Check:
    _, pp_out = _rc(["sysctl", "-n", "kernel.perf_event_paranoid"])
    _, mm_out = _rc(["sysctl", "-n", "vm.max_map_count"])
    try:
        pp = int(pp_out)
        mm = int(mm_out)
    except ValueError:
        return Check("sysctl", FAIL, f"không đọc được ({pp_out!r}, {mm_out!r})", FIX_BOOTSTRAP)
    detail = f"perf_event_paranoid={pp} · max_map_count={mm}"
    if mm < 262144:
        return Check("sysctl", FAIL, detail, FIX_BOOTSTRAP)
    if pp == 2:
        return Check("sysctl", OK, detail)
    if pp > 2:
        return Check("sysctl", FAIL, detail, FIX_BOOTSTRAP)
    return Check("sysctl", WARN, f"{detail} (thấp hơn khuyến nghị 2)", FIX_BOOTSTRAP)


def check_apport() -> Check:
    state = _active("apport.service")
    if state == "active":
        return Check("apport", FAIL, "đang bật", FIX_BOOTSTRAP)
    return Check("apport", OK, state)


def check_opencode() -> Check:
    exe = shutil.which("opencode")
    if not exe:
        cand = Path.home() / ".opencode" / "bin" / "opencode"
        if cand.is_file():
            exe = str(cand)
    if not exe:
        return Check("opencode", FAIL, "không có binary", "cài opencode + opencode auth login")
    _, out = _rc([exe, "--version"])
    ver = out.strip() or "?"
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", ver)
    if not match or match.group(1) != "2":
        return Check("opencode", WARN, f"không phải v2.x: {ver}", "pin v2.x (ADR-001)")

    problems: list[str] = []
    cfg = Path.home() / ".config" / "opencode"
    for name, target in (
        ("opencode.json", paths.REPO_ROOT / "runtime" / "opencode.json"),
        ("persona.txt", paths.REPO_ROOT / "runtime" / "persona.txt"),
    ):
        link = cfg / name
        if link.is_symlink():
            if link.resolve() != target.resolve():
                problems.append(f"{name} trỏ sai chỗ")
        elif link.exists():
            problems.append(f"{name} là file thật, không symlink về repo")
        else:
            problems.append(f"thiếu {name}")

    rc, auth_out = _rc([exe, "auth", "list"])
    auth_ok = rc == 0 and "stored" in auth_out
    if problems or not auth_ok:
        detail = ver + ("; " + "; ".join(problems) if problems else "")
        if not auth_ok:
            detail += "; chưa auth"
        return Check(
            "opencode", FAIL, detail, "./runtime/personabuilder.sh hoặc opencode auth login"
        )
    return Check("opencode", OK, ver)


def check_ida() -> Check:
    base = Path.home() / "ida-pro-9.4"
    needed = {
        "idat": base / "idat",
        "idalib": base / "idalib",
        "license (~/.idapro/ida.reg)": Path.home() / ".idapro" / "ida.reg",
    }
    missing = [k for k, p in needed.items() if not p.exists()]
    if missing:
        return Check(
            "ida", FAIL, f"thiếu: {', '.join(missing)}", "cài IDA 9.4 + license vào ~/.idapro"
        )
    return Check("ida", OK, str(base))


def check_disk() -> Check:
    usage = shutil.disk_usage(paths.REPO_ROOT)
    free_gb = usage.free / 1024**3
    if free_gb >= 100:
        return Check("disk", OK, f"{free_gb:.0f}G free")
    if free_gb >= 60:
        return Check("disk", WARN, f"{free_gb:.0f}G free (<100G)", "GC corpus/builds (§6.3)")
    return Check("disk", FAIL, f"{free_gb:.0f}G free (<60G)", "dọn corpus + prune docker (§6.3)")


def check_uv() -> Check:
    exe = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    if not Path(exe).is_file():
        return Check("uv", FAIL, "không có", FIX_BOOTSTRAP)
    _, out = _rc([exe, "--version"])
    return Check("uv", OK, out.strip() or "?")


def check_depot_tools() -> Check:
    d = Path.home() / "tools" / "depot_tools"
    if not (d / ".git").is_dir():
        return Check("depot_tools", FAIL, f"thiếu {d}", FIX_BOOTSTRAP)
    rc = _rc(["bash", "-lc", "grep -q depot_tools ~/.bashrc"])
    if rc[0] != 0:
        return Check("depot_tools", WARN, "chưa có trong ~/.bashrc PATH", FIX_BOOTSTRAP)
    return Check("depot_tools", OK, "clone + PATH")


def check_git_identity() -> Check:
    _, name = _rc(["git", "config", "--global", "user.name"])
    _, email = _rc(["git", "config", "--global", "user.email"])
    if name and email:
        return Check("git-identity", OK, f"{name} <{email}>")
    return Check("git-identity", WARN, "chưa set global", FIX_BOOTSTRAP)


def check_v8_checkout() -> Check:
    root = paths.V8_ROOT
    if (root / ".git").is_dir():
        _, out = _rc(["git", "-C", str(root), "rev-parse", "--short", "HEAD"])
        return Check("v8-checkout", INFO, f"{root} @ {out.strip()}")
    return Check("v8-checkout", INFO, f"chưa có {root} (task M0-04 sẽ fetch)")


def check_venv() -> Check:
    py = paths.REPO_ROOT / ".venv" / "bin" / "python"
    if py.is_file():
        _, out = _rc([str(py), "--version"])
        return Check("venv", INFO, out.strip())
    return Check("venv", INFO, "chưa tạo (acceptance/M0-scaffold.sh)")


CHECK_ORDER = (
    check_swap,
    check_slices,
    check_docker,
    check_earlyoom,
    check_sysctl,
    check_apport,
    check_opencode,
    check_ida,
    check_disk,
    check_uv,
    check_depot_tools,
    check_git_identity,
    check_v8_checkout,
    check_venv,
)


def run_doctor(as_json: bool = False) -> int:
    checks = [fn() for fn in CHECK_ORDER]
    code = exit_code(checks)

    if as_json:
        payload = {"ts": time.time(), "exit": code, "checks": [asdict(c) for c in checks]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return code

    width = max(len(c.name) for c in checks)
    counts = {OK: 0, WARN: 0, FAIL: 0, INFO: 0}
    for c in checks:
        counts[c.status] += 1
        line = f"[{c.status:4}] {c.name:<{width}}  {c.detail}"
        if c.fix:
            line += f"  → {c.fix}"
        print(line)
    print(
        f"\ndoctor: {counts[OK]} ok · {counts[WARN]} warn · "
        f"{counts[FAIL]} fail · {counts[INFO]} info"
    )
    return code
