---
name: Repro Minimize
description: Ổn định + tối giản repro V8 — từ repro.js về repro.min.js giữ nguyên crash. Dùng khi repro flaky hoặc quá lớn để phân tích.
---

# Repro & minimize

Nguyên tắc: repro không tái diễn được = không tồn tại. Minimize trước khi đào sâu —
repro nhỏ là tài sản của cả pipeline.

## Workflow

1. Baseline: chạy repro ×10 trên `out/asan/d8`; ghi tỉ lệ crash thật (kể cả fail).
2. Flags tối thiểu: thử bỏ từng flag một; giữ `--allow-natives-syntax` nếu cần natives;
   ghi lại bộ flags cần thiết vào `repro.flags.txt`.
3. Minimize:
   - Có fuzzilli minimizer (farm M1+) → dùng trước.
   - Không có → delta thủ công: xoá từng khối (hàm → dòng → biến), giữ crash, lặp tới đáy.
4. Verify: `repro.min.js` crash ≥5/5 và **đúng bug cũ** (so 2–3 frame đầu với gốc).
5. Ghi: giữ cả `repro.js` gốc; thêm `repro.min.js` + `repro.flags.txt`; cập nhật mục `## Repro`
   trong `notes.md` (tỉ lệ + kích thước trước/sau).

## Không được

- Không đổi ngữ nghĩa để "cho dễ crash" (sleep tay, ép GC, bơm heap) mà không ghi chú rõ.
- Không xoá repro gốc.
- Không nhận "chắc là cùng bug" — so stack, không cảm tính.
