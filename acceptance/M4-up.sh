#!/usr/bin/env bash
# acceptance/M4-up.sh — M4-07: supervisor umbrella up/down
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

section "up (farm + aux)"
OUT="$("$VENV_BIN/chromly" up | tee "$LOG_DIR/m4-up.log")"
echo "$OUT"
aux_started="$(grep -cE "^(watchdog|ingest|metrics|intel|sched): started" <<<"$OUT")"
[[ "$aux_started" -ge 4 ]] && pass "$aux_started aux started" || fail "aux thiếu ($aux_started)"

sleep 4
alive="$(pgrep -f "chromly.cli.app (fuzz|intel|sched)" | wc -l)"
[[ "$alive" -ge 4 ]] && pass "$alive aux process alive" || fail "chỉ $alive aux alive"

section "down"
"$VENV_BIN/chromly" down | tee "$LOG_DIR/m4-up-down.log"
sleep 3
left="$(pgrep -f "chromly.cli.app" | wc -l)"
[[ "$left" -eq 0 ]] && pass "down sạch (0 process)" || fail "còn $left process chromly.cli.app"
fuzz_left="$(pgrep -f FuzzilliCli | wc -l)"
[[ "$fuzz_left" -eq 0 ]] && pass "farm sạch" || fail "còn $fuzz_left FuzzilliCli"

ac_summary
