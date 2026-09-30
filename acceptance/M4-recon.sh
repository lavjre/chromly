#!/usr/bin/env bash
# acceptance/M4-recon.sh — M4-08: archaeology + surface report + classify fixture
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

parse() { # parse <key> <text>
    "$VENV_BIN/python" - "$1" "$2" <<'PY'
import re, sys

m = re.search(rf"{sys.argv[1]}=([0-9]+)", sys.argv[2])
print(m.group(1) if m else "")
PY
}

TOTAL_CLASSIFIED=0

for mirror in v8 chromium; do
    section "archaeology — $mirror"
    OUT="$("$VENV_BIN/chromly" recon archaeology --mirror "$mirror" --days 90 2>&1 | tee "$LOG_DIR/m4-recon-$mirror.log")"
    echo "$OUT"
    scanned="$(parse scanned "$OUT")"
    if [[ -n "$scanned" && "$scanned" -gt 0 ]]; then
        pass "$mirror: đọc được $scanned commit khớp security-grep"
    else
        fail "$mirror: scanned=$scanned"
    fi
    # tổng record phân loại (trừ 'other' = không map được path)
    n_records="$("$VENV_BIN/python" - "$mirror" <<'PY'
import json, sys
from chromly.intel import recon

d = recon._load_archaeology(sys.argv[1])
n = sum(v for k, v in d["counts"].items() if k != "other")
print(n)
PY
)"
    note "$mirror: $n_records commit map được surface (không kể 'other')"
    TOTAL_CLASSIFIED=$((TOTAL_CLASSIFIED + n_records))

    if "$VENV_BIN/python" - "$mirror" <<'PY'
import sys
from chromly.intel import recon

d = recon._load_archaeology(sys.argv[1])
assert d and d["records"], "không có record"
assert d["bug_class_counts"], "không có phân loại bug class"
sample = d["records"][0]
assert {"sha", "date", "subject", "surface", "bug_class"} <= set(sample)
PY
    then
        pass "$mirror: archaeology JSON hợp lệ (surface + bug class)"
    else
        fail "$mirror: archaeology JSON lỗi"
    fi
done

section "tổng phân loại ≥ 50"
if [[ "$TOTAL_CLASSIFIED" -ge 50 ]]; then
    pass "v8+chromium map được $TOTAL_CLASSIFIED commit (≥50)"
else
    fail "chỉ map được $TOTAL_CLASSIFIED commit (<50)"
fi

section "surface report"
REPORT="$("$VENV_BIN/chromly" recon report 2>&1 | tail -1)"
if [[ -f "$REPORT" ]]; then
    pass "report: $REPORT"
    for needle in "## V8" "## CHROMIUM" "| surface |" "Đề xuất"; do
        if grep -qF "$needle" "$REPORT"; then
            pass "report có «$needle»"
        else
            fail "report thiếu «$needle»"
        fi
    done
    if grep -qE '\| (jit|wasm|blink) \| [1-9]' "$REPORT"; then
        pass "bảng có số liệu surface thật"
    else
        fail "bảng surface trống"
    fi
else
    fail "không sinh được report ($REPORT)"
fi

section "classify fixture"
if "$VENV_BIN/python" - <<'PY'
from chromly.intel import recon

# fixture paths — chuẩn theo SURFACES map
cases_v8 = {
    "src/maglev/loop-peeling.cc": "jit",
    "src/wasm/baseline/x.cc": "wasm",
    "src/regexp/regexp-compiler.cc": "regexp",
    "docs/readme.md": "other",
}
for path, want in cases_v8.items():
    got = recon.classify_surface("v8", [path])
    assert got == want, f"v8 {path}: got {got}, want {want}"

cases_cr = {
    "third_party/blink/renderer/core/dom/x.cc": "blink",
    "mojo/core/channel.cc": "mojo-ipc",
    "sandbox/win/src/x.cc": "sandbox-browser",
    "other/foo.cc": "other",
}
for path, want in cases_cr.items():
    got = recon.classify_surface("chromium", [path])
    assert got == want, f"chromium {path}: got {got}, want {want}"

assert recon.guess_bug_class("Fix use-after-free in Foo") == "use-after-free"
assert recon.guess_bug_class("Harden bounds check in X") == "oob"

# bug class lấy từ chính record thật: mọi surface phải map được
from chromly.intel import recon as r

for mirror in ("v8", "chromium"):
    d = r._load_archaeology(mirror)
    for rec in d["records"][:100]:
        assert rec["surface"] in {s[0] for s in r.SURFACES[mirror]} | {"other"} or rec[
            "surface"
        ].startswith("v8:"), rec["surface"]
print("fixture classify: OK")
PY
then
    pass "classify + bug class fixture đúng"
else
    fail "classify fixture sai"
fi

ac_summary
