#!/usr/bin/env bash
# acceptance/M0-scaffold.sh — M0-02: repo scaffold + chromly check (G0)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "python 3.12 + venv"
PY312="${CHROMLY_PYTHON:-$HOME/.pyenv/versions/3.12.12/bin/python3}"
if [[ ! -x "$PY312" ]]; then
    PY312="$(command -v python3.12 || true)"
fi
if [[ ! -x "$VENV_BIN/python" ]]; then
    if [[ -x "$PY312" ]]; then
        if uv venv --python "$PY312" "$REPO_ROOT/.venv" >/dev/null 2>&1; then
            pass "venv created ($("$VENV_BIN/python" --version 2>&1))"
        else
            fail "uv venv"
        fi
    else
        fail "không tìm thấy python3.12 (đặt CHROMLY_PYTHON)"
    fi
else
    pass "venv đã có ($("$VENV_BIN/python" --version 2>&1))"
fi

section "editable install [dev]"
if (cd "$REPO_ROOT" && uv pip install --python "$VENV_BIN/python" -q -e '.[dev]'); then
    pass "uv pip install -e .[dev]"
else
    fail "uv pip install -e .[dev]"
fi

section "chromly check (G0: ruff + pytest + import sanity)"
if "$VENV_BIN/chromly" check 2>&1 | tee "$LOG_DIR/m0-scaffold-check.log"; then
    pass "chromly check xanh"
else
    fail "chromly check đỏ"
fi

ac_summary
