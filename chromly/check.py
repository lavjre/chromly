"""G0 — `chromly check`: import sanity + ruff + pytest (§14.3)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from chromly import paths


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip()
    return proc.returncode, out


def _find_tool(name: str) -> str | None:
    """Ưu tiên tool cạnh python hiện tại (venv), rồi mới tới PATH."""
    sibling = Path(sys.executable).parent / name
    if sibling.is_file():
        return str(sibling)
    return shutil.which(name)


def run_check(root: Path | None = None, python: str | None = None) -> int:
    """Chạy G0 từ repo root. Trả 0 nếu xanh, 1 nếu có bước đỏ."""
    root = root or paths.REPO_ROOT
    py = python or sys.executable
    failed = False

    rc, out = _run([py, "-m", "compileall", "-q", "chromly", "tests"], root)
    print(f"[check] compileall: {'ok' if rc == 0 else 'FAIL'}")
    if rc:
        print(out)
        failed = True

    rc, out = _run(
        [py, "-c", "import chromly, chromly.paths, chromly.store.db, chromly.cli.app"],
        root,
    )
    print(f"[check] import sanity: {'ok' if rc == 0 else 'FAIL'}")
    if rc:
        print(out)
        failed = True

    ruff = _find_tool("ruff")
    if ruff is None:
        print("[check] ruff: MISSING — cài dev deps: uv pip install -e '.[dev]'")
        failed = True
    else:
        for sub in (["check", "chromly", "tests"], ["format", "--check", "chromly", "tests"]):
            rc, out = _run([ruff, *sub], root)
            label = f"ruff {sub[0]}" + (" --check" if sub[0] == "format" else "")
            print(f"[check] {label}: {'ok' if rc == 0 else 'FAIL'}")
            if rc:
                print(out)
                failed = True

    rc, out = _run([py, "-m", "pytest", "-q"], root)
    tail = out.splitlines()[-1] if out else ""
    print(f"[check] pytest: {'ok' if rc == 0 else 'FAIL'} ({tail})")
    if rc:
        print(out)
        failed = True

    print(f"[check] G0 {'XANH' if not failed else 'ĐỎ'}")
    return 1 if failed else 0
