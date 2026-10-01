# M2-07 — Audit loop (tự chạy daily)

**Status:** done
**Deliverable:** `chromly intel audit --loop [--interval 86400]` + aux entry `audit` trong
supervisor (`chromly up` tự spawn; chạy 1 lượt ngay khi start rồi sleep interval).
Mục tiêu: mirror tiến liên tục → mỗi fix mới kèm test mới = bug còn sống trong snapshot;
audit quét định kỳ để không bỏ lọt delta.
**Files:** `chromly/intel/regress_audit.py`, `chromly/cli/app.py`, `chromly/orchestrator/supervisor.py`
**Acceptance:** `chromly intel audit --dry-run` chạy; `chromly up` thấy aux `audit` alive;
log `store/fuzz/logs/aux-audit.log` có dòng summary.
**Evidence:** `chromly up` output + aux log.
**Phụ thuộc:** M2-06.
