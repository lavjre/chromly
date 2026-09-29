# ADR-003 — MCP `chromly-tools` là boundary duy nhất agent ↔ hạ tầng

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

Agent cần case/crash/repro/build/fuzz/store/kg (§5.7). Cho agent shell trần vào hạ tầng = không audit được, không version được, nguy cơ sửa state ngoài ý muốn. Supervisor là nguồn sự thật của ledger/budget/queue.

## Quyết định

Mọi tương tác agent → hạ tầng đi qua MCP server `chromly-tools` duy nhất, versioned `/v1`, log mọi call, timeout mặc định 15'. CLI trực tiếp (`chromly ...`) chỉ dành cho operator và supervisor nội bộ.

## Phương án đã loại

- **Agent gọi CLI/socket trực tiếp** — trôi quyền dần theo thời gian, không audit, khó chặn theo permission.
- **File protocol (drop file/spool)** — race condition, không request/response, versioning khó.

## Hệ quả

+ Boundary rõ, audit được, testable, thay implementation sau lưng không đổi contract.
− Thêm 1 hop + phải viết/test server; schema `/v1` phải backward-compatible trong suốt v1. Xây ở M4, trước đó agent không có đường nào chạm hạ tầng.
