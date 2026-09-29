# M1-04 — Watchdog

**Status:** done
**Deliverable:** watchdog per worker: hang >120s không exec mới → kill + restart + log repro attempt; crash loop (restart >3 lần/10') → worker về trạng thái `degraded` + alert line; event ghi `store/fuzz/events.jsonl`. Test mode: worker giả sleep (env `CHROMLY_TEST_HANG=1`) để verify.
**Files:** `chromly/fuzz/watchdog.py`, `chromly/fuzz/farm.py`, `tests/test_watchdog.py`, `acceptance/M1-watchdog.sh`
**Acceptance:** `bash acceptance/M1-watchdog.sh` → worker giả bị kill ≤120s+grace, auto restart, 2 event (kill + restart) trong events.jsonl.
**Evidence:** timestamps kill/restart + events.jsonl trích.
**Out of scope:** OOM react (earlyoom lo; §10.2 ghi nhận event khi phát hiện.
**Phụ thuộc:** M1-02.
