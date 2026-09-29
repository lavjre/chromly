---
name: VRP Report
description: Draft báo cáo VRP (Chromium) từ case đã validated — root cause, repro steps, impact, đề xuất fix. Dùng khi VERDICT = report-draft.
---

# VRP report — viết như cho người bận

Người đọc là triager: repro được trong 5 phút, hiểu root cause trong 2 phút.
Không khoe, không giấu, không tô hồng.

## Cấu trúc (§15)

1. **Title + severity** — một dòng: `[Component] Bug class in Function (write/read)`.
2. **Tóm tắt** — bug gì, ở đâu, hậu quả: 3–5 câu.
3. **Môi trường** — build rev + flags chính xác + version.
4. **Repro** —numbered steps copy-paste được từ clean build; kèm **tỉ lệ crash thật**
   (100%? 7/10?) — không nói quá.
5. **Root cause** — file:line + đoạn code sai + giải thích ngắn; đúng tầng logic, không phải symptom.
6. **Impact** — chứng minh bằng primitive đã có (L1/L2/L3). Không suy diễn RCE khi chưa có write.
7. **Đề xuất fix** — hướng, để dev quyết định.

## Checklist trước khi lưu `report.md`

- [ ] Repro 100% từ clean build (không 100% → ghi tỉ lệ + cách tăng ổn định, không giấu).
- [ ] Không bước thừa / file thừa trong `poc/` gửi kèm.
- [ ] Sanitize: không lộ path VM / username / hostname — thay placeholder.
- [ ] Mọi tuyên bố có evidence, hoặc ghi rõ "chưa kiểm chứng".
- [ ] Tiếng Anh, giọng trung tính.

## Ghi chú

- Case chưa đủ mạnh (chưa có primitive) → KHÔNG gửi; đề xuất bước tiếp (needs-human / tiếp lab).
- Sau khi gửi: ghi hash nội dung vào `knowledge.yaml` để dedup lần sau.
