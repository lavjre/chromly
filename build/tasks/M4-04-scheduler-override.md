# M4-04 — Dynamic scheduler + human override (§6.5, §10.4)

**Status:** done
**Deliverable:** scheduler deterministic: modes `NORMAL|FUZZ_LEAN|BUILD_WINDOW|CASE_PRIORITY|RED`; inputs: MemAvailable + PSI cpu/mem, disk %, queue depth, budget tier, case phase; điều kiện giữ ≥60s, dwell ≥10', mọi chuyển ghi `scheduler_decisions(ts, from, to, reason, snapshot)`; `chromly sched status` + `chromly sched eval --once` (tick) + `chromly sched override <mode> <duration>` → bảng `overrides`; rule từ §6.1 làm baseline.
**Files:** `chromly/orchestrator/scheduler.py`, `chromly/orchestrator/override.py`, `chromly/cli/app.py`, `tests/test_scheduler.py`, `acceptance/M4-sched.sh`
**Acceptance:** `bash acceptance/M4-sched.sh` → tick với fixture áp lực cao → FUZZ_LEAN/RED + decision row; override 5' → mode ghi lại + hết hạn tự về; dwell guard (đổi liên tục không nhảy mode).
**Evidence:** decision rows + override row.
**Phụ_dep:** M3-04 (telemetry).
