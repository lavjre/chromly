#!/usr/bin/env bash
# acceptance/M2-diffopt.sh — M2-10: differential opt/no-opt
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

section "unit tests"
if "$VENV_BIN/python" -m pytest -q tests/test_diffopt.py >/dev/null 2>&1; then
    pass "compare() + fake-d8 integration"
else
    fail "unit tests đỏ"
fi

section "chạy thật (limit 40)"
OUT="$("$VENV_BIN/chromly" fuzz diffopt --limit 40 2>&1 | tee "$LOG_DIR/m2-diffopt.log")"
echo "$OUT"
if grep -qE "diffopt: sampled=[0-9]+ diffs=[0-9]+" <<<"$OUT"; then
    pass "summary parse được"
else
    fail "không có summary"
fi
SAMPLED="$(grep -oE 'sampled=[0-9]+' <<<"$OUT" | head -1 | cut -d= -f2)"
[[ "${SAMPLED:-0}" -ge 1 ]] && pass "sample được $SAMPLED program" || fail "sampled=$SAMPLED (corpus trống?)"

section "last.json"
if "$VENV_BIN/python" - <<'PY'
import json
from pathlib import Path
p = Path("store/fuzz/diffopt/last.json")
d = json.loads(p.read_text())
assert "sampled" in d and "diffs" in d
print(f"last: sampled={d['sampled']} diffs={d['diffs']}")
PY
then
    pass "last.json hợp lệ"
else
    fail "last.json lỗi"
fi

ac_summary
