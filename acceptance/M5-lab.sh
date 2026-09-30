#!/usr/bin/env bash
# acceptance/M5-lab.sh — M5-02: exploit run harness + lab state + L0 notes
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

FX="$REPO_ROOT/store/exploit/fixtures"
mkdir -p "$FX"
cat >"$FX/always_ok.js" <<'EOF'
print("SUCCESS");
EOF
cat >"$FX/crash_rc.js" <<'EOF'
throw new Error("boom");
EOF

section "exploit run — ok fixture"
if "$VENV_BIN/chromly" exploit run --poc "$FX/always_ok.js" --build asan --expect ok \
    >"$LOG_DIR/m5-lab-ok.log" 2>&1; then
    pass "ok fixture: rc=0 đúng kỳ vọng"
else
    fail "ok fixture lỗi — xem m5-lab-ok.log"
fi

section "exploit run — crash fixture"
if "$VENV_BIN/chromly" exploit run --poc "$FX/crash_rc.js" --build asan --expect crash \
    >"$LOG_DIR/m5-lab-crash.log" 2>&1; then
    pass "crash fixture: rc≠0 đúng kỳ vọng"
else
    fail "crash fixture lỗi — xem m5-lab-crash.log"
fi

section "exploit run — kỳ vọng âm bị bắt"
"$VENV_BIN/chromly" exploit run --poc "$FX/always_ok.js" --build asan --expect crash >/dev/null 2>&1
if [[ $? -eq 1 ]]; then
    pass "expect crash trên fixture ok → exit 1 (đúng)"
else
    fail "expectation âm không bị bắt"
fi

section "lab state (out/calib theo bug)"
STATE="$REPO_ROOT/store/exploit/lab/build-state.json"
if [[ -f "$STATE" ]]; then
    if "$VENV_BIN/python" - "$STATE" <<'PY'
import hashlib, json, sys
from pathlib import Path

st = json.loads(Path(sys.argv[1]).read_text())
for key in ("bug", "fix_sha", "d8_sha256", "built_at"):
    assert st.get(key), f"thiếu {key}"
d8 = Path.home() / "v8" / "v8" / "out" / "calib" / "d8"
assert d8.is_file(), "thiếu out/calib/d8"
h = hashlib.sha256()
with d8.open("rb") as f:
    while chunk := f.read(1 << 22):
        h.update(chunk)
assert h.hexdigest() == st["d8_sha256"], "d8 hiện tại khác state (out/calib đã build lại)"
print(f"state ok: {st['bug']} built_at={st['built_at']}")
PY
    then
        pass "build-state.json khớp out/calib"
    else
        fail "build-state.json không khớp"
    fi
    if "$VENV_BIN/chromly" exploit lab --status >/dev/null 2>&1; then
        pass "exploit lab --status chạy"
    else
        fail "exploit lab --status lỗi"
    fi
else
    fail "chưa có build-state.json — chạy: chromly exploit lab --bug <id>"
fi

section "L0 notes (calibration/exploits/*/notes.md)"
N_NOTES=0
for f in "$REPO_ROOT"/calibration/exploits/*/notes.md; do
    [[ -f "$f" ]] || continue
    N_NOTES=$((N_NOTES + 1))
    miss=""
    for sec in "## L0" "Hypothesis" "Evidence" "Result"; do
        grep -qF "$sec" "$f" || miss="$miss «$sec»"
    done
    if [[ -z "$miss" ]]; then
        pass "$(basename "$(dirname "$f")")/notes.md đủ mục"
    else
        fail "$(basename "$(dirname "$f")")/notes.md thiếu:$miss"
    fi
done
[[ $N_NOTES -ge 1 ]] && pass "$N_NOTES notes L0" || fail "chưa có notes L0 nào"

ac_summary
