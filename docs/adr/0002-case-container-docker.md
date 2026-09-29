# ADR-002 — Case container (docker) thay vì venv/process

**Trạng thái:** Superseded by [ADR-009](0009-case-direct-on-vm.md) · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

Case agent (opencode + persona) cần môi trường cách ly mỗi case: fs riêng (`/case`), RAM giới hạn (slice `case` 4GB, §6.4), không đụng hạ tầng host, IDA license không bake vào image, d8/build mount read-only. 16GB RAM không cho phép nhân bản VM.

## Quyết định

Mỗi case = 1 docker container từ image `chromly-case:mX`; mount `/case` (rw), V8 out dirs (ro), `runtime/` (ro), IDA install + license (ro); cgroup trong `chromly-case.slice`; policy permission deny `sudo *`/`rm -rf /*` (§4.5). Container dừng khi có VERDICT/HELP/TIMEOUT (§5.6).

## Phương án đã loại

- **Venv + process trực tiếp** — không cách ly fs/process, permission khó chặt, agent dễ đụng hạ tầng; không giới hạn RAM theo case.
- **VM phụ mỗi case** — quá nặng với 8 vCPU/16GB; clone/boot chậm hơn nhiều so với container.

## Hệ quả

+ Cách ly + limit RAM/CPU sẵn qua slice; dọn dẹp = xóa container; image versioned theo milestone.
− Docker overhead ~1.2GB/container + cần GC image/volume (§6.3); đường mount IDA license phải kiểm tra ở M4. Giảm thiểu: dọn định kỳ + fallback IDA http mode (§5.8).
