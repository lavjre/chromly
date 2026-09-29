#!/usr/bin/env bash
# acceptance/M0-doctor.sh — M0-03: chromly doctor đúng ngữ nghĩa
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

# Các mục cần sudo — được phép PEND trước khi operator chạy bootstrap
OPERATOR_PENDING="swap slices docker earlyoom sysctl apport"
BOOTSTRAP_MARK=/etc/systemd/system/chromly-svc.slice

section "chromly doctor --json"
DOCTOR_JSON="$LOG_DIR/doctor.json"
if "$VENV_BIN/chromly" doctor --json >"$DOCTOR_JSON" 2>"$LOG_DIR/doctor.err"; then
    DOCTOR_RC=0
else
    DOCTOR_RC=$?
fi

if [[ ! -s "$DOCTOR_JSON" ]]; then
    fail "doctor không xuất JSON (xem $LOG_DIR/doctor.err)"
    ac_summary
    exit 1
fi
pass "doctor chạy, rc=$DOCTOR_RC"

section "ngữ nghĩa"
RESULT="$("$VENV_BIN/python" - "$DOCTOR_JSON" "$OPERATOR_PENDING" "$([ -f "$BOOTSTRAP_MARK" ] && echo yes || echo no)" <<'PY'
import json, sys

doc = json.load(open(sys.argv[1]))
pending_set = set(sys.argv[2].split())
bootstrap_ran = sys.argv[3] == "yes"

checks = doc["checks"]
assert len(checks) >= 12, f"quá ít check: {len(checks)}"
by_status = {"ok": 0, "warn": 0, "fail": 0, "info": 0}
fails = []
for c in checks:
    by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    if c["status"] == "fail":
        fails.append(c["name"])

print(f"checks={len(checks)} ok={by_status['ok']} warn={by_status['warn']} fail={by_status['fail']} info={by_status['info']}")
print(f"fails={fails}")

fails_not_pending = [f for f in fails if f.split(":")[0].strip() not in pending_set]

if bootstrap_ran and fails:
    print(f"RESULT=fail bootstrap_ran nhưng còn FAIL: {fails}")
    sys.exit(1)
if fails_not_pending:
    print(f"RESULT=fail có FAIL ngoài danh sách chờ-operator: {fails_not_pending}")
    sys.exit(1)
if doc.get("exit") != (1 if fails else 0):
    print(f"RESULT=fail exit không khớp (exit={doc.get('exit')}, fails={len(fails)})")
    sys.exit(1)
if fails:
    print(f"RESULT=pend chờ operator bootstrap: {fails}")
else:
    print("RESULT=pass doctor xanh")
PY
)"
echo "$RESULT"
if grep -q "^RESULT=pass" <<<"$RESULT"; then
    pass "doctor xanh hoàn toàn"
elif grep -q "^RESULT=pend" <<<"$RESULT"; then
    pend "doctor: các mục chờ operator (sudo infra/bootstrap.sh)"
else
    fails_line="$(grep '^RESULT=' <<<"$RESULT" | head -1)"
    fail "${fails_line:-doctor semantics}"
fi

ac_summary
