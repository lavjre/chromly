#!/usr/bin/env bash
# acceptance/M1-corpus.sh — M1-06: sync mjsunit → seeds, idempotent, trim dry-run
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

SEEDS="$REPO_ROOT/store/fuzz/corpus/fzil"

section "sync (limit 60)"
OUT1="$("$VENV_BIN/chromly" fuzz corpus sync --limit 60)"
echo "$OUT1"
if grep -qE "'ok': [1-9]" <<<"$OUT1" || grep -qE "'skip': [1-9]" <<<"$OUT1"; then
    pass "sync có seed"
else
    fail "sync không tạo seed nào (check parser: infra/fuzzilli-setup.sh)"
fi

n_seeds="$(ls "$SEEDS"/*.fzil 2>/dev/null | wc -l)"
[[ "$n_seeds" -ge 1 ]] && pass "seeds: $n_seeds .fzil" || fail "seeds dir trống"

section "idempotent (chạy lần 2)"
OUT2="$("$VENV_BIN/chromly" fuzz corpus sync --limit 60)"
echo "$OUT2"
if grep -qE "'ok': 0" <<<"$OUT2"; then
    pass "không nhân đôi (ok=0)"
else
    fail "chạy lần 2 vẫn build thêm"
fi

section "trim dry-run"
TR="$("$VENV_BIN/chromly" fuzz corpus trim)"
echo "$TR"
if grep -q "dry-run" <<<"$TR"; then
    pass "trim dry-run (không xoá)"
else
    fail "trim lỗi"
fi

ac_summary
