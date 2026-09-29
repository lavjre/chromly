#!/usr/bin/env bash
# acceptance/M2-variants.sh — M2-03: variant test sinh + chạy trên d8
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

FIXTURE_SHA="$(printf 'fixture-%s' "m2variants" | sha1sum | cut -c1-40)"

section "variants cho commit reviewed thật"
OUT="$("$VENV_BIN/chromly" intel variants 2>&1 | tee "$LOG_DIR/m2-variants.log")"
echo "$OUT"
gen="$(grep -oE 'generated=[0-9]+' <<<"$OUT" | head -1 | cut -d= -f2)"

if [[ "${gen:-0}" -ge 1 ]]; then
    pass "commit thật sinh $gen variant test"
else
    note "commit thật không có test_js — verify pipeline bằng fixture"
    FDIR="$REPO_ROOT/store/intel/$FIXTURE_SHA"
    mkdir -p "$FDIR"
    cat >"$FDIR/variants.json" <<'JSON'
[{"title": "fixture variant", "confidence": "high", "test_js": "print('fixture-ok');"}]
JSON
    OUT2="$("$VENV_BIN/chromly" intel variants --sha "$FIXTURE_SHA" 2>&1 | tee -a "$LOG_DIR/m2-variants.log")"
    echo "$OUT2"
    if grep -qE "generated=[1-9]" <<<"$OUT2"; then
        pass "fixture pipeline: sinh + chạy OK"
    else
        fail "fixture pipeline lỗi"
    fi
fi

section "kết quả ghi lại"
if "$VENV_BIN/python" - <<'PY'
import glob, json

files = glob.glob("store/intel/*/variant-results.json")
assert files, "không có variant-results.json"
latest = max(files, key=lambda f: __import__("os").path.getmtime(f))
data = json.load(open(latest))
print(f"{latest}: generated={data['generated']} builds={data['builds']} results={len(data['results'])}")
assert data["results"] or data["generated"] == 0
PY
then
    pass "variant-results.json hợp lệ"
else
    fail "thiếu variant-results.json"
fi

ac_summary
