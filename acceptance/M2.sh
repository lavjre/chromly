#!/usr/bin/env bash
# acceptance/M2.sh — milestone M2 (PLAN §13): watcher lag <24h · ≥1 review auto · variant test · KG
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SCRIPTS=(M2-watcher M2-review M2-variants M2-kg M2-audit M2-seed M2-priority M2-diffopt)
overall=0
for s in "${SCRIPTS[@]}"; do
    section "$s"
    bash "$REPO_ROOT/acceptance/$s.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "$s đỏ (rc=$rc)"; }
done

section "intel status"
"$VENV_BIN/chromly" intel status | tee "$LOG_DIR/m2-status.json"

printf '\n'
if [[ $overall -eq 0 ]]; then
    printf '========= M2 ACCEPTANCE: GREEN =========\n'
else
    printf '========= M2 ACCEPTANCE: RED ===========\n'
fi
exit $overall
