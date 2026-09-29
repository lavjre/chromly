# M0-02 — Repo scaffold + `chromly check` (G0)

**Status:** done
**Deliverable:** package Python `chromly/` đúng layout §14.5 chạy được entry point `chromly`; `chromly check` = ruff + pytest + import sanity (G0, §14.3); CLI skeleton: `check` thật, các lệnh còn lại khai báo + stub `exit 3` "scheduled Mx"; `chromly/paths.py` (repo/store/cases/v8 paths + env override); `chromly/store/db.py` — SQLite schema v1 tập vận hành (crashes · cases · builds · runs · intel · budget, `user_version=1`); `tests/` khung.
**Files:** `pyproject.toml`, `chromly/__init__.py`, `chromly/paths.py`, `chromly/check.py`, `chromly/cli/app.py`, `chromly/store/db.py`, `chromly/{orchestrator,builds,fuzz,intel,knowledge,telemetry,triage,bench,case,mcp,exploit}/__init__.py`, `tests/*`, `acceptance/M0-scaffold.sh`, `acceptance/lib.sh`
**Acceptance:** `bash acceptance/M0-scaffold.sh` → tạo `.venv` (Python 3.12.12), cài editable, `chromly check` xanh; chạy lần 2 không lỗi (idempotent).
**Evidence:** output `chromly check` (ruff + số test pytest) trong commit body.
**Out of scope:** logic fuzz/intel/triage/case (M1+) · schema telemetry/KG/bench (M3+).
**Phụ thuộc:** — (M0-01 cho môi trường chuẩn, nhưng scaffold chạy được trước bootstrap).
