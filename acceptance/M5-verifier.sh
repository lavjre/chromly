#!/usr/bin/env bash
# acceptance/M5-verifier.sh — M5-01: verifier đo reliability (3 fixture)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

FX="$REPO_ROOT/store/exploit/fixtures"
mkdir -p "$FX"

cat >"$FX/always_ok.js" <<'EOF'
print("SUCCESS");
EOF

cat >"$FX/crash.js" <<'EOF'
throw new Error("boom");
EOF

cat >"$FX/flaky.js" <<'EOF'
if (Math.random() < 0.5) { print("SUCCESS"); } else { throw new Error("flake"); }
EOF

section "always-ok → rate 1.0"
OUT="$("$VENV_BIN/chromly" exploit verify --poc "$FX/always_ok.js" --runs 50 --marker SUCCESS --build asan)"
echo "$OUT"
grep -q "50/50" <<<"$OUT" && pass "rate 100%" || fail "rate sai"

section "crash → rate 0.0"
OUT="$("$VENV_BIN/chromly" exploit verify --poc "$FX/crash.js" --runs 20 --build asan || true)"
echo "$OUT"
grep -q "0/20" <<<"$OUT" && pass "rate 0%" || fail "rate sai"

section "flaky → 0 < rate < 1"
OUT="$("$VENV_BIN/chromly" exploit verify --poc "$FX/flaky.js" --runs 60 --marker SUCCESS --build asan || true)"
echo "$OUT"
"$VENV_BIN/python" - "$OUT" <<'PY'
import re, sys

m = re.search(r"(\d+)/(\d+)", sys.argv[1])
assert m, "không parse được"
ok, n = int(m.group(1)), int(m.group(2))
assert 0 < ok < n, f"rate lệch: {ok}/{n}"
print(f"flaky {ok}/{n} — hợp lệ")
PY
[[ $? -eq 0 ]] && pass "flaky trong khoảng" || fail "flaky lệch"

section "log JSON"
n="$(ls "$REPO_ROOT"/store/exploit/verify-*.json 2>/dev/null | wc -l)"
[[ "$n" -ge 3 ]] && pass "$n log verify-*.json" || fail "thiếu log"

ac_summary
