#!/usr/bin/env bash
# acceptance/M1-crashstore.sh — M1-05: incoming → DB <5' + dedup
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

INC="$REPO_ROOT/store/fuzz/fuzzilli/crashes"
mkdir -p "$INC"

section "thả crash giả → ingest"
head -c 64 /dev/urandom >"$INC/acceptance-crash-1.bin"
t0=$SECONDS
OUT1="$("$VENV_BIN/chromly" fuzz ingest --once)"
dt=$((SECONDS - t0))
echo "$OUT1"
if grep -q "crash \[new\]" <<<"$OUT1"; then
    pass "ingest new (${dt}s)"
else
    fail "không ingest được file mới"
fi
[[ $dt -lt 300 ]] && pass "crash → store <5' (${dt}s)" || fail "quá 5' (${dt}s)"

section "bản copy → dedup"
cp "$INC/acceptance-crash-1.bin" "$INC/acceptance-crash-2.bin"
OUT2="$("$VENV_BIN/chromly" fuzz ingest --once)"
echo "$OUT2"
if grep -q "crash \[dup\]" <<<"$OUT2"; then
    pass "dedup theo hash"
else
    fail "không dedup"
fi

section "DB rows"
if "$VENV_BIN/python" - <<'PY'
from chromly.store import db

con = db.ensure_db()
n = con.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()["n"]
d = con.execute("SELECT MAX(dup_count) AS d FROM crashes").fetchone()["d"]
print(f"rows={n} max_dup_count={d}")
assert n >= 1 and (d or 0) >= 2
PY
then
    pass "DB ok"
else
    fail "DB check fail"
fi

ac_summary
