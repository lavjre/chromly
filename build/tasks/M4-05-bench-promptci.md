# M4-05 — Bench T1–T4 + Prompt CI

**Status:** done
**V0 note:** T1 đã chạy thật: analyst agent trên calib-567177599 → accuracy=1 (hits: peel, phi), 718s, $0.082. T2 (agent diff review) giữ queued — chạy khi có nhu cầu đo review precision.
**Deliverable:** `chromly bench --suite ci|T1..T4` — T1 root-cause (calibration bugs: agent analyst trả function/root cause, chấm accuracy) · T2 diff review (10 commit đã biết kết cục — 5 variant sống/5 sạch, chấm precision/recall của agent intel) · T3 triage classify (20 crash fixture đã label — chấm accuracy + score order) · T4 harness sanity (repro pipeline pass/fail); n≥5 run/task, median+spread; lưu `bench/runs/` + bảng bench_runs; **Prompt CI**: `chromly bench --suite ci` + gate: primary metric không giảm >2% & ≥1 metric tăng; fail → tag rollback; ghi prompt_registry hash.
**Files:** `chromly/bench/__init__.py`, `chromly/bench/suite.py`, `bench/tasks/*.json`, `chromly/cli/app.py`, `tests/test_bench.py`, `acceptance/M4-bench.sh`
**Acceptance:** `bash acceptance/M4-bench.sh` → T4 (deterministic) GREEN; T1/T3 chạy ≥1 run thật có số; CI gate chạy được (auto-revert path dry-run).
**Evidence:** bench report `bench/latest.md` + số.
**Phụ thuộc:** M3-03 (calibration) · M3-04/05 (telemetry/registry).
