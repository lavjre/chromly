# ADR-007 — Calibration (đúng/sai) tách khỏi Benchmark (so sánh)

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

Hai câu hỏi khác nhau: (1) "hệ thống có đúng không — có bắt được bug thật không?" (2) "cấu hình nào tốt hơn — model/prompt/skill/plugin/scheduler nào?" Trộn chung một bộ đo làm méo cả hai: bug dễ làm benchmark trông tốt, bug khó làm calibration nhiễu.

## Quyết định

- **Calibration harness (§5.5):** revert fix lịch sử V8 → build có ground-truth bug; 5 bug đầu (parser · regexp · wasm · 2 JIT/type-confusion) + metadata bắt buộc (surface/bug_class/difficulty/coverage/history); chạy tự động hàng tuần. Đây là acceptance test của cả hệ thống.
- **Benchmark suite (§8):** T1–T4 (root-cause · diff review · triage classify · harness sanity); n ≥ 5 run/task, báo median + spread; A/B model/persona/skill/plugin/scheduler/topology; Prompt CI gate (>2% giảm → auto-revert).

## Phương án đã loại

- **Một suite chung** — không trả lời được đồng thời "đúng chưa" và "cái nào tốt hơn"; ngưỡng gate lẫn lộn.
- **Chỉ benchmark** — không có ground truth thật; tối ưu trên proxy sẽ trôi khỏi mục tiêu bắt bug.

## Hệ quả

+ Hai thước đo rõ nghĩa, gate Prompt CI chỉ dựa số so sánh; calibration giữ hệ thống khỏi tự lừa mình.
− Chi phí duy trì 2 bộ (5 bug rebuild ~2 tháng/lần + bench chạy đêm); giảm thiểu: chạy trong slice `svc`, tận dụng đêm.
