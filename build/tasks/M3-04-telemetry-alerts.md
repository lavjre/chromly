# M3-04 — Telemetry v1 + alert engine

**Status:** done
**Deliverable:** thu thập: crash rate, dedup ratio, FP rate, case MTTR (khi M4 có case — để trống chỗ), execs/s, refusal rate, budget day, watcher lag, queue depth, disk/PSI → rollup theo giờ/ngày (bảng metrics + metrics_rollup, migration v4) → **alert engine**: rules trên rollup (crash rate tụt 7d · corpus stale >14d · refusal >2σ · cost/case tăng · watcher lag tăng · disk ngưỡng) → alert vào bảng `alerts` + digest text; `chromly telemetry rollup|alerts [--ack id]`.
**Files:** `chromly/telemetry/__init__.py`, `chromly/telemetry/rollup.py`, `chromly/telemetry/alerts.py`, `chromly/cli/app.py`, `tests/test_telemetry.py`, `acceptance/M3-telemetry.sh`
**Acceptance:** rollup từ metrics hiện có chạy ra số; alert rule trigger tổng hợp (fixture đẩy crash-rate 0) → alert row + digest; ack được.
**Evidence:** rollup sample + alert row.
**Phụ thuộc:** M1-07 (metrics sampler).
