#!/usr/bin/env bash
# fixcheck — ADR-013: verify upstream fix coverage trước mọi claim "0day".
#
# Apply patch commit fix (chỉ src/*) từ mirror lên V8 snapshot → rebuild build đích → chạy test
# → tự revert + rebuild lại (kể cả khi lỗi). Test clean trên build có fix = bug đã được cover
# (n-day, không report); còn crash = candidate sống.
#
# usage: tools/fixcheck.sh <fix-sha> <test.js> [<test2.js> ...]
#   env: V8=~/v8/v8  MIRROR=~/mirrors/v8  OUT=out/release  NO_REBUILD=1 (skip rebuild lúc revert)
set -euo pipefail

V8="${V8:-$HOME/v8/v8}"
MIRROR="${MIRROR:-$HOME/mirrors/v8}"
OUT="${OUT:-out/release}"
FIX="${1:?usage: fixcheck.sh <fix-sha> <test.js>...}"
shift
[ $# -ge 1 ] || { echo "thiếu test file" >&2; exit 2; }

reverted=0
cleanup() {
  [ "$reverted" = 1 ] && return 0
  reverted=1
  echo "── revert + rebuild..."
  git -C "$V8" checkout -- src/ 2>/dev/null || true
  if [ "${NO_REBUILD:-0}" != "1" ]; then
    (cd "$V8" && PATH="$HOME/tools/depot_tools:$PATH" autoninja -C "$OUT" d8 >/dev/null 2>&1) \
      && echo "── revert rebuild OK" || echo "!! revert rebuild FAIL — kiểm tra tay"
  fi
}
trap cleanup EXIT

echo "── apply fix $FIX"
git -C "$MIRROR" format-patch -1 "$FIX" --stdout | git -C "$V8" apply --include='src/*'
echo "── build $OUT (có thể lâu)"
(cd "$V8" && PATH="$HOME/tools/depot_tools:$PATH" autoninja -C "$OUT" d8)

D8="$V8/$OUT/d8"
for t in "$@"; do
  flags=$(grep -m1 -oE '// flags:.*' "$t" 2>/dev/null | sed 's|// flags:||' || true)
  st=clean
  timeout 60 "$D8" --allow-natives-syntax $flags "$t" >/tmp/opencode/fixcheck.out 2>&1 || st="rc=$?"
  msg=$(grep -m1 -E "SEGV|Check failed|Fatal error|FAIL" /tmp/opencode/fixcheck.out | cut -c1-100 || true)
  echo "$(basename "$t"): $st ${msg:+| $msg}"
done
