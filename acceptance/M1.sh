#!/usr/bin/env bash
# acceptance/M1.sh — milestone M1 (PLAN §13): farm ≥300 exec/s tổng, watchdog, crash store
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SCRIPTS=(M1-fuzzilli M1-farm M1-libfuzzer M1-watchdog M1-crashstore M1-metrics M1-triage-auto)
overall=0
for s in "${SCRIPTS[@]}"; do
    section "$s"
    bash "$REPO_ROOT/acceptance/$s.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "$s đỏ (rc=$rc)"; }
done

section "throughput ≥300 exec/s tổng (180s window)"
export PATH="$HOME/.local/share/swiftly/bin:$PATH"
"$VENV_BIN/chromly" fuzz up >/dev/null
sleep 180
"$VENV_BIN/chromly" fuzz metrics --once >/dev/null
ST="$("$VENV_BIN/chromly" fuzz status)"
echo "$ST"
TOTAL="$("$VENV_BIN/python" - "$ST" <<'PY'
import re, sys
vals = [float(m) for m in re.findall(r"execs=([0-9.]+)/s", sys.argv[1])]
print(f"{sum(vals):.1f}")
PY
)"
note "tổng execs/s = $TOTAL"
"$VENV_BIN/chromly" fuzz down >/dev/null
if "$VENV_BIN/python" -c "import sys; sys.exit(0 if float('$TOTAL') >= 300 else 1)"; then
    pass "≥300 exec/s tổng ($TOTAL/s)"
else
    fail "<300 exec/s tổng ($TOTAL/s)"
fi

printf '\n'
if [[ $overall -eq 0 ]]; then
    printf '========= M1 ACCEPTANCE: GREEN =========\n'
else
    printf '========= M1 ACCEPTANCE: RED ===========\n'
fi
exit $overall
