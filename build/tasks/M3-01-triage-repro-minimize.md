# M3-01 — Triage: repro + symbolize + minimize

**Status:** done
**Deliverable:** `chromly triage <crash_id|hash>` — từ store/crashes/<hash>/: detect format (fzil/js/raw) → lift fzil→js (FuzzILTool --liftToJS) nếu cần → repro ×5 trên `out/asan/d8` (đo tỉ lệ thật, loại flaky <5/5 ghi nhận riêng) → symbolize (llvm-symbolizer của V8 toolchain, ASAN report đầy đủ) → minimize: creduce-style pass (xoá block/dòng giữ crash; dùng fuzzilli minimizer nếu có đường CLI — verify trước, không đoán) → lưu `repro.js` + `repro.min.js` + `asan.txt` + `symbols.txt` vào store/triage/<hash>/.
**Files:** `chromly/triage/__init__.py`, `chromly/triage/repro.py`, `chromly/triage/minimize.py`, `chromly/cli/app.py`, `tests/test_triage_repro.py`, `acceptance/M3-triage.sh`
**Acceptance:** fixture crash (tạo từ d8: chạy 1 script crash ASAN sẵn — vd dùng `--abort-on-uncaught-exception`? phải là crash thật — dùng calibration/known crash khi có; v0: fixture từ d8 assert đơn giản) → repro 5/5, symbol hóa ra stack, minimize nhỏ hơn bản gốc.
**Evidence:** tỉ lệ repro + kích thước trước/sau minimize.
**Phụ thuộc:** M1-05 (crash store) · out/asan (M0-04).
