# M2-11 — Variants: tự thêm flag thiếu từ lỗi "enable with --X"

**Status:** done
**Deliverable:** `variants.run_test` bắt regex `enable with (--[\w-]+)` trong output →
tự chạy lại kèm flag còn thiếu (tối đa 2 lượt, không lặp flag). Outcome mới `skipped`
khi vẫn thiếu flag (không tính là pass); `flags_added` ghi lại flag đã thêm.
**Files:** `chromly/intel/variants.py`, `tests/test_variants.py`
**Acceptance:** unit test: fake d8 cần `--wasm-shared` → outcome ok + flags_added; flag vô vọng → skipped.
**Evidence:** e944471c7b re-run: 3 variant trước đây "ok" giả (FAIL vì thiếu flag) giờ chạy thật
với `flags_added=['--wasm-shared']` trên cả asan+release — kết quả thật: no-crash.
**Phụ thuộc:** M2-03.
