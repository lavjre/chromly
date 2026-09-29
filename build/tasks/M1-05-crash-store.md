# M1-05 — Crash store (incoming → DB, <5')

**Status:** done
**Deliverable:** ingest loop: scan `store/fuzz/incoming/*/` mỗi 15s → mỗi crash: lưu artifact (repro program + flags + raw log) vào `store/crashes/<hash>/`, hash sha256(nội dung normalize), dedup (cùng hash = tăng counter), ghi DB `crashes` (fault_type raw, source, build_rev, state=raw). Crash → DB <5' từ lúc file xuất hiện.
**Files:** `chromly/fuzz/crashes.py`, `chromly/fuzz/farm.py`, `tests/test_crashes.py`, `acceptance/M1-crashstore.sh`
**Acceptance:** `bash acceptance/M1-crashstore.sh` → thả crash giả vào incoming; <5' sau: có row DB + artifact dir; thả bản copy lần 2 → dedup (1 row, counter=2).
**Evidence:** DB row + timing đo được.
**Out of scope:** minimize/classify (M3 triage).
**Phụ thuộc:** M1-02.
