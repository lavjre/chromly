# M2-03 — Variant test generator + runner

**Status:** done
**Deliverable:** `chromly intel variants [--rev R]` — từ review.md: parse variant hypotheses → sinh test JS draft `tests/INTEL-<commit>/variant-N.js`; chạy mỗi test trên build active (d8 `out/asan` + `out/release`, timeout 60s) → kết quả (crash/no-crash/error) ghi `results.json` + DB intel.variant_flag; tạo case dir `cases/INTEL-<commit>/` khi có crash.
**Files:** `chromly/intel/variants.py`, `chromly/cli/app.py`, `tests/test_variants.py`, `acceptance/M2-variants.sh`
**Acceptance:** `bash acceptance/M2-variants.sh` → từ 1 review fixture (hoặc review thật): ≥1 variant test sinh + chạy trên d8, kết quả ghi lại.
**Evidence:** variant file + run result.
**Out of scope:** dedup/score sâu (M3 triage).
**Phụ thuộc:** M2-02 · d8 builds (M0-04).
