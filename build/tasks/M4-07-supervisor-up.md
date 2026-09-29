# M4-07 — Supervisor umbrella `chromly up/down`

**Status:** done
**Deliverable:** `chromly up` = farm workers + aux loops (watchdog 60s · ingest 15s · metrics 60s · intel watch 1h · sched loop 60s) chạy detached, log `store/logs/aux-*.log`, state chung `store/fuzz/state.json` (mục `aux`); `chromly down` = dừng hết sạch (farm.down + kill aux). Đây là bản tạm trước khi có systemd units đầy đủ (§10.1).
**Files:** `chromly/orchestrator/supervisor.py`, `chromly/cli/app.py`, `chromly/orchestrator/scheduler.py` (`sched loop`), `acceptance/M4-up.sh`
**Acceptance:** `bash acceptance/M4-up.sh` → up: farm + ≥4 aux alive; down: 0 process còn lại (pgrep FuzzilliCli/chromly.cli.app rỗng).
**Evidence:** up/down outputs + pgrep trước/sau.
**Phụ thuộc:** M1-02 · M1-04/05/06/07 · M2-01 · M4-04.
