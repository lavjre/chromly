#!/usr/bin/env bash
# acceptance/lib.sh — helper chung cho acceptance scripts (PLAN §14.1: acceptance = trọng tài khách quan)
set -uo pipefail

_AC_PASS=0
_AC_FAIL=0
_AC_PEND=0

pass() { printf '  [PASS] %s\n' "$1"; _AC_PASS=$((_AC_PASS + 1)); }
fail() { printf '  [FAIL] %s\n' "$1"; _AC_FAIL=$((_AC_FAIL + 1)); }
pend() { printf '  [PEND] %s\n' "$1"; _AC_PEND=$((_AC_PEND + 1)); }
note() { printf '  [note] %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

ac_summary() {
    printf '\n-- summary: %d pass · %d fail · %d pending --\n' "$_AC_PASS" "$_AC_FAIL" "$_AC_PEND"
    [[ $_AC_FAIL -eq 0 ]]
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_BIN="$REPO_ROOT/.venv/bin"
LOG_DIR="$REPO_ROOT/store/logs/acceptance"
mkdir -p "$LOG_DIR"
