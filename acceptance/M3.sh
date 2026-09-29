#!/usr/bin/env bash
# acceptance/M3.sh — milestone M3 (PLAN §13): triage · classify · telemetry · registry (+ calibration queued)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SCRIPTS=(M3-triage M3-classify M3-telemetry M3-registry)
overall=0
for s in "${SCRIPTS[@]}"; do
    section "$s"
    bash "$REPO_ROOT/acceptance/$s.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "$s đỏ (rc=$rc)"; }
done

section "dashboard v1"
"$VENV_BIN/chromly" status | tee "$LOG_DIR/m3-status.txt"

if [[ -f "$REPO_ROOT/acceptance/M3-calibration.sh" ]]; then
    section "M3-calibration"
    bash "$REPO_ROOT/acceptance/M3-calibration.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "M3-calibration đỏ"; }
else
    note "M3-calibration.sh chưa có (task M3-03 đang mở — cần bug revert đầu tiên)"
fi

printf '\n'
if [[ $overall -eq 0 ]]; then
    printf '========= M3 ACCEPTANCE: GREEN =========\n'
else
    printf '========= M3 ACCEPTANCE: RED ===========\n'
fi
exit $overall
