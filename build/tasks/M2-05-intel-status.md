# M2-05 — Intel status + milestone M2

**Status:** done
**Deliverable:** `chromly intel status|list` (đếm pending/reviewed, variant counts, lag); `acceptance/M2.sh` tổng: M2-watcher · M2-review · M2-variants · M2-kg + wire `chromly intel` CLI thật (bỏ stub).
**Files:** `chromly/intel/status.py`, `chromly/cli/app.py`, `acceptance/M2.sh`
**Acceptance:** `bash acceptance/M2.sh` → các sub pass; `chromly intel status` in số liệu thật; ≥1 variant test đã sinh + chạy (từ sub).
**Evidence:** status output + tổng kết.
**Out of scope:** scheduler intel theo telemetry (M3) · prompt CI gate cho skill (M4).
**Phụ thuộc:** M2-01..04.
