#!/usr/bin/env bash
# acceptance/M2-audit.sh — M2-06: upstream-regress delta audit
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "$REPO_ROOT"

section "dry-run liệt kê test sau-checkout"
OUT="$("$VENV_BIN/chromly" intel audit --dry-run --max 5 2>&1 | tee "$LOG_DIR/m2-audit-dry.log")"
echo "$OUT"
if grep -q "scanned=" <<<"$OUT"; then
    pass "dry-run chạy"
else
    fail "dry-run lỗi"
fi

section "audit thật (--max 24)"
OUT="$("$VENV_BIN/chromly" intel audit --max 24 2>&1 | tee "$LOG_DIR/m2-audit.log")"
echo "$OUT" | tail -12
CRASHES="$(grep -oE 'crashes=[0-9]+' <<<"$OUT" | head -1 | cut -d= -f2)"
SCANNED="$(grep -oE 'scanned=[0-9]+' <<<"$OUT" | head -1 | cut -d= -f2)"
note "scanned=$SCANNED crashes=$CRASHES"
if [[ -n "$SCANNED" && "$SCANNED" -gt 0 ]]; then
    pass "quét được $SCANNED test"
else
    fail "không quét được test nào (mirror/rev?)"
fi
if [[ -n "$CRASHES" && "$CRASHES" -ge 1 ]]; then
    pass "phát hiện $CRASHES crash thật trên snapshot"
else
    fail "không phát hiện crash (kỳ vọng ≥1: regress-563882510 / 567538973 / 567126756)"
fi

section "crash store rows (source=upstream-regress)"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
rows = con.execute(
    "SELECT hash, fault_type, severity, state FROM crashes WHERE source = 'upstream-regress'"
).fetchall()
assert rows, "chưa có crash upstream-regress trong DB"
for r in rows:
    print(f"{r['hash'][:12]} class={r['fault_type']} score={r['severity']} state={r['state']}")
con.close()
PY
then
    pass "DB có row upstream-regress"
else
    fail "DB thiếu row upstream-regress"
fi

ac_summary
