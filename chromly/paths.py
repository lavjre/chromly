"""Path layout (§14.5). Override bằng env: CHROMLY_STORE · CHROMLY_CASES · CHROMLY_V8_ROOT."""

from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parent


def _env_path(var: str, default: Path) -> Path:
    raw = os.environ.get(var)
    return Path(raw).expanduser() if raw else default


STORE_DIR = _env_path("CHROMLY_STORE", REPO_ROOT / "store")
CASES_DIR = _env_path("CHROMLY_CASES", REPO_ROOT / "cases")
RESEARCH_DIR = REPO_ROOT / "research"
BENCH_DIR = REPO_ROOT / "bench"

BUILDS_DIR = STORE_DIR / "builds"
LOGS_DIR = STORE_DIR / "logs"
DB_PATH = STORE_DIR / "chromly.db"

# Checkout V8 (task M0-04): gclient solution root ~/v8, repo tại ~/v8/v8
V8_ROOT = _env_path("CHROMLY_V8_ROOT", Path.home() / "v8" / "v8")
V8_OUT = V8_ROOT / "out"


def ensure_dirs() -> None:
    for d in (STORE_DIR, BUILDS_DIR, LOGS_DIR, CASES_DIR, RESEARCH_DIR, BENCH_DIR / "runs"):
        d.mkdir(parents=True, exist_ok=True)
