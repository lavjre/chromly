# ADR-006 — V8 first (thay vì JSC/SpiderMonkey)

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

Cần chốt engine #1 cho M0–M8. Tiêu chí: kênh thưởng thật (Chromium VRP), ecosystem fuzzing trưởng thành, intel patch-diff dày, kỹ năng transferable sang mục tiêu khác, vừa năng lực 1 VM.

## Quyết định

Chỉ V8/Chromium upstream + build local; report qua Chromium VRP. Engine khác (JSC/SpiderMonkey) để evolution v3 với trigger rõ: V8 track chín (≥1 chu kỳ finding hoàn chỉnh) + calibration ổn định. Kernel/mobile sau v3.

## Phương án đã loại

- **JSC/SpiderMonkey** — bounty ít/thấp hơn, fuzzer ecosystem mỏng hơn (fuzzilli WebKit port kém), writeup tham chiếu ít hơn cho workflow §1.
- **Kernel/mobile** — độ khó cao hơn năng lực hiện tại của 1 VM/1 người; setup debug/test tốn kém hơn nhiều.

## Hệ quả

+ Focus tối đa; dùng thẳng fuzzilli/domato + intel diff hàng ngày; calibration có ground truth phong phú.
− Phụ thuộc 1 target/1 nhà; giảm thiểu: v3 có trigger định lượng, kiến trúc đã tách engine layer từ đầu (§13 Evolution).
