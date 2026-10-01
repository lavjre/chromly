#!/usr/bin/env bash
# acceptance/M4-plugin.sh — M4-11: plugin runtime sống + deny-list enforce (F5 review v3)
# Mặc định FULL (1 LLM run nhỏ ~vài nghìn token). CHROMLY_PLUGIN_SMOKE=quick → bỏ phần runtime.
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

PLUGIN="$REPO_ROOT/runtime/plugins/chromly/index.ts"
LOG="$REPO_ROOT/store/logs/plugin-events.jsonl"
SCRATCH="/tmp/opencode/chromly-case/PLUGIN-SMOKE"

section "tĩnh: file + discovery layout"
[[ -f "$PLUGIN" ]] && pass "plugin index.ts tồn tại" || fail "thiếu $PLUGIN"
[[ "$(readlink -f "$HOME/.config/opencode/plugins" 2>/dev/null)" == "$REPO_ROOT/runtime/plugins" ]] \
    && pass "symlink discovery ~/.config/opencode/plugins → runtime/plugins" \
    || fail "symlink discovery sai/thiếu"
"$VENV_BIN/python" -c "import json; json.load(open('$REPO_ROOT/runtime/opencode.json'))" \
    && pass "opencode.json parse được" || fail "opencode.json lỗi"

section "runtime: deny-list trong scratch agent"
if [[ "${CHROMLY_PLUGIN_SMOKE:-full}" == "quick" ]]; then
    pend "quick mode — bỏ test runtime (cần 1 LLM run)"
    n="$(grep -c '"event":"deny"' "$LOG" 2>/dev/null || echo 0)"
    [[ "$n" -ge 1 ]] && pass "log có $n deny entry lịch sử" || note "chưa có deny entry nào"
else
    mkdir -p "$SCRATCH"
    T0="$(date +%s)"
    OUT="$(cd "$SCRATCH" && timeout 240 opencode run --standalone --agent persona \
        -m opencode-go/deepseek-v4.1-flash --auto \
        "BẮT BUỘC: gọi công cụ shell chạy đúng lệnh này rồi in nguyên văn lỗi nhận được: sudo true" 2>&1)"
    if grep -q "permission.rejected" <<<"$OUT"; then
        pass "agent-scope bị deny (permission.rejected)"
    else
        fail "không thấy permission.rejected — plugin có thể không nạp (opencode update?)"
    fi
    if "$VENV_BIN/python" - "$LOG" "$T0" <<'PY'
import json, sys
log, t0 = sys.argv[1], int(sys.argv[2])
denies = []
for line in open(log, errors="replace"):
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        continue
    ts = rec.get("ts", 0) / 1000 if rec.get("ts", 0) > 2e10 else rec.get("ts", 0)
    if rec.get("event") == "deny" and ts >= t0 - 60:
        denies.append(rec)
assert denies, "không có deny entry mới trong log"
print("deny mới:", denies[-1].get("cmd", "")[:60], "| scope:", denies[-1].get("scope"))
PY
    then
        pass "plugin-events.jsonl ghi deny mới (scope=agent)"
    else
        fail "log thiếu deny entry mới"
    fi
    rm -rf "$SCRATCH"
fi

ac_summary
