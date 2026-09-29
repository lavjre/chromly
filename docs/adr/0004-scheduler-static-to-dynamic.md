# ADR-004 — Scheduler: tĩnh trước (M1), động theo metric sau (M4)

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

8 vCPU/16GB không chạy được đồng thời build (peak 8–10GB), fuzz 6 instance (3–5GB) và case container (3.5GB). Cần luật phân xử từ M1, nhưng dynamic scheduler cần dữ liệu PSI/queue/budget chưa tồn tại.

## Quyết định

- M1: luật tĩnh baseline §6.1 (`build` active → fuzz 6→2, case queue pause; `case` active → fuzz 6→4, build defer; default 6 fuzz).
- M4: dynamic scheduler §6.5 — inputs PSI/MemAvailable/queue/budget; modes NORMAL·FUZZ_LEAN·BUILD_WINDOW·CASE_PRIORITY·RED; deterministic không ML; điều kiện giữ ≥60s, dwell ≥10', mọi chuyển ghi `scheduler_decisions` kèm snapshot.

## Phương án đã loại

- **Dynamic ngay từ M1** — vi phạm hiến chương §1.6: "Never đổi scheduler không có telemetry làm bằng chứng".
- **Tĩnh mãi** — không tối ưu được theo số thật; metric §7.2 sẽ chỉ ra chỗ nghẽn mà không có cơ chế phản ứng.

## Hệ quả

+ An toàn trước (không OOM), tối ưu sau (có số liệu); M4 thay thế không phá thiết kế.
− Viết 2 lần có chủ đích; verify ngưỡng tĩnh phải đo lại sau 2 tuần telemetry.
