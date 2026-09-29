#!/usr/bin/env bash
# acceptance/M0-adr.sh — M0-07: ADR backfill 002–008 đủ mục bắt buộc
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

N=0
for f in docs/adr/000[2-9]-*.md; do
    [[ -f "$f" ]] || continue
    N=$((N + 1))
    miss=""
    for sec in "## Bối cảnh" "## Quyết định" "## Phương án đã loại" "## Hệ quả"; do
        grep -qF "$sec" "$f" || miss="$miss «$sec»"
    done
    if [[ -z "$miss" ]]; then
        pass "$(basename "$f")"
    else
        fail "$(basename "$f") thiếu:$miss"
    fi
done
[[ $N -eq 8 ]] && pass "đủ 8 file ADR (002–009)" || fail "chỉ có $N/8 file ADR"

missing=""
for n in 002 003 004 005 006 007 008 009; do
    grep -q "\[$n\]" docs/adr/README.md || missing="$missing $n"
done
if [[ -z "$missing" ]]; then
    pass "README liệt kê 002–009"
else
    fail "README thiếu:$missing"
fi

ac_summary
