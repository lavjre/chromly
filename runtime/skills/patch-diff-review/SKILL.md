---
name: Patch Diff Review
description: Review commit/diff V8 như bản đồ bug — fix gì, guard nào thêm, variant nào còn sống. Dùng cho intel lane khi có commit đáng review.
---

# Patch-diff review — fix là bản đồ

Mỗi fix trả lời ba câu: (1) bug gì (2) thiếu check ở đâu (3) sibling path nào có thể chưa fix.
Trả lời đủ ba — đừng dừng ở tóm tắt diff.

## Workflow

1. Đọc commit message + diff (đã normalize). Phân loại security-class hay không
   (memory safety · bounds · lifetimes · type checks).
2. **Fix gì**: tìm guard/check mới thêm (điều kiện if, size check, lifetime fix).
   Ghi chính xác: file · hàm · điều kiện trước/sau.
3. **Bug gì**: suy ngược từ fix — input nào lọt qua trước fix?
   (vd: check mới chặn `length > N` ⇒ trước đó `length == N` lọt.)
4. **Variant còn sống** — ba câu hỏi bắt buộc:
   - Cùng hàm: callpath khác còn thiếu check tương tự?
   - Sibling: hàm/op tương tự cùng module?
   - Cùng pattern: module khác (builtins / torque / compiler) có pattern y hệt?
   Grep theo mảnh code mới thêm để tìm "anh em" của nó.
5. Sinh variant test: `tests/INTEL-xxxx/variant-N.js` — dự đoán crash type + cách verify
   trên build active + previous.
6. Ghi KG: commit node · variant hypothesis nodes (edge `derived_from`) · rejections.
7. Output `review.md`: 3 câu tóm tắt + danh sách variant test + độ tin (high/med/low) từng cái.

## Không được

- Variant không có cơ sở từ diff = không ghi — spam hypothesis làm nhiễu KG.
- Không chỉ đọc diff: commit message + bug link (nếu public) là một nửa câu chuyện.
- Rejections phải ghi — negative knowledge là tài sản.
