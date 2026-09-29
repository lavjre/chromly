# M2-01 — Intel watcher (mirror + poll + filter)

**Status:** done
**Deliverable:** `chromly intel watch` — mirror shallow `v8/v8` tại `~/mirrors/v8` (`git clone --filter=blob:none`); poll mỗi giờ (`--once` cho test): fetch rev mới → list commit mới nhất theo path labels (`jit/ maglev/ turboshaft/ wasm/ regexp/ parser/ compiler/` + `sandbox`) + keyword security → normalize (commit hash, paths, subject) → ghi DB `intel` (review_status=pending, variant_flag=0) + diff dump `store/intel/<rev>/<commit>.diff` (kèm `--stat`). Lag mục tiêu <24h (đo = now - commit date của commit mới nhất đã thấy).
**Files:** `chromly/intel/__init__.py`, `chromly/intel/watcher.py`, `chromly/cli/app.py`, `tests/test_intel_watcher.py`, `acceptance/M2-watcher.sh`
**Acceptance:** `bash acceptance/M2-watcher.sh` → mirror tồn tại; `--once` chạy; ≥1 commit lọt filter vào DB từ mirror (fetch thật); diff file có nội dung; chạy lại idempotent (không nhân đôi row).
**Evidence:** count commits filtered + 1 diff path + lag đo được.
**Out of scope:** agent review (M2-02).
**Phụ thuộc:** — (network).
