# M1-07 — Metrics v0 + acceptance M1 tổng

**Status:** done
**Deliverable:** sampler 60s: execs/s per worker (parse log), RSS, uptime → `store/fuzz/metrics.jsonl` + rollup mỗi 5' vào DB (`metrics` bảng tối giản — M3 mở rộng); `chromly fuzz status` đọc metrics hiển thị tổng; `acceptance/M1.sh` tổng hợp: M1-fuzzilli · M1-farm · M1-libfuzzer · M1-watchdog · M1-crashstore · M1-corpus + đo **execs/s tổng ≥300** (window ≥3') + leak check (RSS delta qua 10' chạy).
**Files:** `chromly/fuzz/metrics.py`, `chromly/store/db.py` (thêm bảng metrics + bump SCHEMA_VERSION=2), `acceptance/M1.sh`, `tests/test_metrics.py`
**Acceptance:** `bash acceptance/M1.sh` → tất cả sub pass + số execs/s tổng ≥300 ghi lại + RSS stable.
**Evidence:** M1.sh output + số execs.
**Out of scope:** dashboard v1/alert engine (M3) · 24h soak (chạy tiếp sau, report riêng).
**Phụ thuộc:** M1-01..06.
