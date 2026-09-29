#!/usr/bin/env bash
# acceptance/M0.sh — milestone M0 tổng (PLAN §13)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SCRIPTS=(M0-bootstrap M0-scaffold M0-doctor M0-build M0-opencode M0-ida M0-skills M0-adr)
overall=0
for s in "${SCRIPTS[@]}"; do
    section "$s"
    bash "$REPO_ROOT/acceptance/$s.sh"
    rc=$?
    [[ $rc -eq 0 ]] || { overall=1; note "$s đỏ (rc=$rc)"; }
done

printf '\n'
if [[ $overall -eq 0 ]]; then
    printf '========= M0 ACCEPTANCE: GREEN =========\n'
else
    printf '========= M0 ACCEPTANCE: RED ===========\n'
fi
exit $overall
