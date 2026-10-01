#!/usr/bin/env bash
# acceptance/M2-priority.sh — M2-09: review ưu tiên security-class
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

section "dry-run thứ tự ưu tiên"
OUT="$("$VENV_BIN/chromly" intel review --dry-run --limit 8 2>&1 | tee "$LOG_DIR/m2-priority.log")"
echo "$OUT"

if [[ -z "$OUT" ]]; then
    pend "không có commit pending — bỏ qua"
    ac_summary
    exit 0
fi

if "$VENV_BIN/python" - "$LOG_DIR/m2-priority.log" <<'PY'
import re
import sys

scores = []
for line in open(sys.argv[1]):
    m = re.match(r"score=(-?\d+) ", line)
    if m:
        scores.append(int(m.group(1)))
assert scores, "không parse được score nào"
assert scores == sorted(scores, reverse=True), f"không giảm dần: {scores}"
assert max(scores) >= 3, f"không có dòng score ≥3: {scores}"
print(f"scores: {scores}")
PY
then
    pass "xếp hạng giảm dần, có security-class (≥3)"
else
    fail "xếp hạng sai"
fi

section "unit tests xếp hạng"
if "$VENV_BIN/python" -m pytest -q tests/test_review_priority.py >/dev/null 2>&1; then
    pass "priority_score unit tests"
else
    fail "unit tests đỏ"
fi

ac_summary
