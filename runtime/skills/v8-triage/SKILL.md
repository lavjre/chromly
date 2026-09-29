---
name: V8 Triage
description: Triage crash V8 trong case — xác nhận repro, phân loại bug class, map về source, score. Dùng khi case có crash/ASAN mới cần bức tranh tổng.
---

# V8 triage — từ ASAN tới phân loại

Mục tiêu: trả lời nhanh crash là gì · tái diễn được không · nhóm bug nào · chạm code nào.
**Không** kết luận exploitability ở bước này.

## Input có sẵn trong /case

- `asan.txt` — report đầy đủ đã symbolize
- `symbols.txt` — stack đã normalize
- `repro.js` (+ `repro.flags.txt` nếu có) — repro tối giản
- `triage.md` — chỗ ghi kết quả

## Workflow

1. Đọc `asan.txt`: fault type (heap-buffer-overflow / use-after-free / ...) · access size · vị trí
   read/write · có nằm trong JIT-generated code không (frame kiểu generated/Torque builtins).
2. Repro trên build sạch: `out/asan/d8 <flags> repro.js` ×5.
   - 5/5 → ok. <5/5 → ghi **tỉ lệ thật**, đánh dấu flaky. Không làm tròn.
3. Map source: lấy 2–3 frame nổi bật, Grep tên function trong checkout V8 (đường dẫn có trong
   symbols) → file:line ứng viên.
4. Classify + score theo §5.4: WRITE(3) > READ(1) · offset controllable(+2) · gần JIT tier(+2) ·
   dcheck-only(-2) · known-toy(-3). Mỗi thành phần phải có lý do — số phải giải thích được.
5. Viết `triage.md`: crash summary · repro result · bug class · source candidates · score + rationale · câu hỏi mở.

## Không được

- Không sửa `asan.txt` / `repro.js`.
- Evidence chưa đủ → ghi `unknown` + thiếu gì, không đoán bug class.
- Negative knowledge phải ghi lại: hướng đã loại, vì sao.
