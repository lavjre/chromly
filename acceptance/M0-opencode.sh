#!/usr/bin/env bash
# acceptance/M0-opencode.sh — M0-05: opencode smoke (version · paths · persona · resume)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

MODEL="${CHROMLY_MODEL:-opencode-go/deepseek-v4.1-flash}"
SMOKE_LOG="$LOG_DIR/opencode-smoke.log"
: >"$SMOKE_LOG"

section "opencode version"
if command -v opencode >/dev/null 2>&1; then
    VER="$(opencode --version 2>&1)"
    note "opencode $VER"
    if grep -qE 'v?2\.[0-9]+\.[0-9]+' <<<"$VER"; then
        pass "opencode v2.x"
    else
        fail "opencode không phải v2.x: $VER"
    fi
else
    fail "opencode không có trong PATH"
fi

section "debug paths (chốt cho M4)"
opencode debug paths >"$LOG_DIR/opencode-paths.txt" 2>&1
if grep -q '^config' "$LOG_DIR/opencode-paths.txt" && grep -q '^data' "$LOG_DIR/opencode-paths.txt"; then
    pass "debug paths OK (log: store/logs/acceptance/opencode-paths.txt)"
else
    fail "debug paths lạ"
fi

section "persona smoke — SMOKE-OK"
OUT1="$(opencode run --format json --agent persona -m "$MODEL" \
    "Reply with exactly this token and nothing else: SMOKE-OK" 2>&1)"
echo "$OUT1" >>"$SMOKE_LOG"
SID="$(grep -oE 'ses_[A-Za-z0-9]+' <<<"$OUT1" | head -1)"
if grep -q "SMOKE-OK" <<<"$OUT1"; then
    pass "persona trả lời SMOKE-OK (session=$SID)"
else
    fail "persona không trả SMOKE-OK — xem $SMOKE_LOG"
fi

section "resume — RESUME-OK"
if [[ -n "$SID" ]]; then
    OUT2="$(opencode run -s "$SID" --format json \
        "Reply with exactly this token and nothing else: RESUME-OK" 2>&1)"
    echo "$OUT2" >>"$SMOKE_LOG"
    if grep -q "RESUME-OK" <<<"$OUT2"; then
        pass "resume cùng session OK ($SID)"
    else
        fail "resume thất bại — xem $SMOKE_LOG"
    fi
else
    fail "không bắt được session id từ run 1"
fi

ac_summary
