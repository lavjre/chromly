# M1-02 — Fuzz farm orchestrator (fuzzilli ×4)

**Status:** done
**Deliverable:** `chromly fuzz up|down|status` — quản 4 worker fuzzilli (nice 5) dưới user lavjre; corpus chung (shared dir), storage crash riêng per-worker (`store/fuzz/incoming/fuzzilli-N/`); log per worker `store/fuzz/logs/`; state `store/fuzz/state.json`; stop sạch (SIGTERM → grace → SIGKILL); status in execs/s tổng + uptime + RSS từng worker.
**Files:** `chromly/fuzz/farm.py`, `chromly/fuzz/__init__.py`, `chromly/cli/app.py`, `tests/test_farm.py`, `acceptance/M1-farm.sh`
**Acceptance:** `bash acceptance/M1-farm.sh` → up 4 worker, 3 phút sau: 4 process alive, execs/s tổng đo được từ log (ghi số), down sạch (0 process còn lại).
**Evidence:** status output + số execs/s + trước/sau của down.
**Out of scope:** libFuzzer (M1-03) · watchdog (M1-04) · systemd integration (M4 supervisor).
**Phụ thuộc:** M1-01.
