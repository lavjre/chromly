#!/usr/bin/env bash
# acceptance/M1-farm.sh — M1-02: farm up/status/down (fuzzilli)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

export PATH="$HOME/.local/share/swiftly/bin:$PATH"

section "farm up"
if "$VENV_BIN/chromly" fuzz up; then
    pass "up"
else
    fail "up lỗi"
fi

section "chạy 180s rồi status"
sleep 180
ST="$("$VENV_BIN/chromly" fuzz status)"
echo "$ST"

alive_n="$(grep -c "alive" <<<"$ST")"
[[ "$alive_n" -ge 1 ]] && pass "$alive_n worker alive" || fail "không worker nào alive"

execs="$("$VENV_BIN/python" - "$ST" <<'PY'
import re, sys
vals = [float(m) for m in re.findall(r"execs=([0-9.]+)/s", sys.argv[1])]
print(sum(vals))
PY
)"
note "execs/s tổng (từ log): $execs"

section "down"
"$VENV_BIN/chromly" fuzz down
sleep 2
if pgrep -f "FuzzilliCli" >/dev/null; then
    fail "còn process FuzzilliCli sau down"
else
    pass "down sạch (0 process)"
fi

ac_summary
