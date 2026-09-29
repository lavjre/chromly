#!/usr/bin/env bash
# acceptance/M3-registry.sh — M3-05: prompt registry sync/list
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "sync lần 1"
OUT1="$("$VENV_BIN/chromly" prompts sync | tee "$LOG_DIR/m3-registry.log")"
echo "${OUT1:-（không có entry mới — đã sync trước đó）}"

section "list"
LST="$("$VENV_BIN/chromly" prompts list)"
echo "$LST"
N="$(grep -c . <<<"$LST")"
[[ "$N" -ge 7 ]] && pass "registry có $N entries (persona+agent+6 skills)" || fail "chỉ $N entries"

section "idempotent"
OUT2="$("$VENV_BIN/chromly" prompts sync)"
[[ -z "$(grep ^new: <<<"$OUT2")" ]] && pass "sync lần 2: không entry mới" || fail "sync lần 2 vẫn thêm"

ac_summary
