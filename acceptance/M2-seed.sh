#!/usr/bin/env bash
# acceptance/M2-seed.sh — M2-08: seed corpus từ delta test
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

section "fuzz seed — lượt 1"
O1="$("$VENV_BIN/chromly" fuzz seed 2>&1 | tee "$LOG_DIR/m2-seed-1.log")"
echo "$O1"
A1="$(grep -oE 'tổng\)' <<<"$O1" >/dev/null && grep -oE '\+[0-9]+ \(tổng\)' <<<"$O1" | grep -oE '[0-9]+')"
[[ -n "$A1" ]] && pass "seed chạy (thêm $A1)" || fail "seed lỗi"

section "fuzz seed — lượt 2 (dedup)"
O2="$("$VENV_BIN/chromly" fuzz seed 2>&1 | tee "$LOG_DIR/m2-seed-2.log")"
A2="$(grep -oE '\+[0-9]+ \(tổng\)' <<<"$O2" | grep -oE '[0-9]+')"
[[ "${A2:-1}" -eq 0 ]] && pass "lượt 2 thêm 0 (dedup)" || fail "lượt 2 thêm $A2 (kỳ vọng 0)"

section "corpus có seed hash-prefixed"
N="$(ls store/fuzz/libfuzzer-parser/corpus 2>/dev/null | grep -cE '^[0-9a-f]{12}-')"
if [[ "$N" -ge 1 ]]; then
    pass "$N seed từ delta trong corpus"
    ls store/fuzz/libfuzzer-parser/corpus | grep -E '^[0-9a-f]{12}-' | head -3
elif [[ -z "$(ls store/regress-audit/tests 2>/dev/null)" ]]; then
    pend "delta trống (audit chưa chạy) — seed sẽ tự chạy khi có"
else
    fail "corpus không có seed hash-prefixed"
fi

ac_summary
