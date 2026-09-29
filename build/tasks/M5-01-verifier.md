# M5-01 — Verifier harness (đo reliability PoC)

**Status:** done
**Deliverable:** `chromly exploit verify --poc <file> --runs N [--build asan|calib|release] [--marker TOKEN]` — chạy PoC ×N với ASLR, đo success rate; success = exit 0 (+ marker nếu có); log JSON `store/exploit/verify-<ts>.json`; fail sample lưu stdout/stderr. Nền tảng cho ladder M5–M7 (§5.9: "exploit chỉ là có khi verifier đủ N lần đạt ngưỡng").
**Files:** `chromly/exploit/verifier.py`, `chromly/cli/app.py`, `tests/test_exploit.py`, `acceptance/M5-verifier.sh`
**Acceptance:** `bash acceptance/M5-verifier.sh` → fixture: always-ok → rate 1.0; crash → rate 0.0; flaky → 0<rate<1; JSON log ghi.
**Evidence:** 3 fixture results.
**Phụ thuộc:** out/asan (M0-04).
