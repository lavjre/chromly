#!/usr/bin/env bash
# acceptance/M2-kg.sh — M2-04: KG ingest + query (schema v3)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

FIXTURE_SHA="$(printf 'fixture-%s' "m2kg" | sha1sum | cut -c1-40)"

section "fixture: review với 2 variants"
FDIR="$REPO_ROOT/store/intel/$FIXTURE_SHA"
mkdir -p "$FDIR"
echo '{"subject": "Fix bounds check (fixture)", "date": "2026-09-29"}' >"$FDIR/meta.json"
cat >"$FDIR/variants.json" <<'JSON'
[
  {"title": "sibling path missing check", "confidence": "med"},
  {"title": "same pattern in builtins", "confidence": "low"}
]
JSON

section "kg ingest"
"$VENV_BIN/chromly" kg ingest "$FIXTURE_SHA" | tee "$LOG_DIR/m2-kg.log"

section "kg query"
Q="$("$VENV_BIN/chromly" kg query --type hypothesis | tee -a "$LOG_DIR/m2-kg.log")"
echo "$Q"
if grep -q "sibling path missing check" <<<"$Q"; then
    pass "query ra hypothesis nodes"
else
    fail "query không thấy hypothesis"
fi

section "kg neighbors (derived_from edge)"
HID="$(grep -oE '^\[[0-9]+\]' <<<"$Q" | head -1 | tr -d '[]')"
if [[ -n "$HID" ]]; then
    N="$("$VENV_BIN/chromly" kg neighbors "$HID")"
    echo "$N"
    grep -q "derived_from" <<<"$N" && pass "edge derived_from" || fail "thiếu edge"
else
    fail "không lấy được node id"
fi

section "schema v3"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
v = con.execute("PRAGMA user_version").fetchone()[0]
assert v == db.SCHEMA_VERSION == 3, v
n = con.execute("SELECT COUNT(*) AS n FROM kg_nodes").fetchone()["n"]
e = con.execute("SELECT COUNT(*) AS n FROM kg_edges").fetchone()["n"]
print(f"user_version={v} nodes={n} edges={e}")
assert n >= 2 and e >= 2
PY
then
    pass "DB v3 + counts"
else
    fail "schema/counts sai"
fi

ac_summary
