# build/ — protocol cho builder agent

Nguồn đầy đủ: PLAN **§14**. Đọc file này trước khi làm bất kỳ task nào.

## Bắt đầu một task

1. Đọc task file trong `tasks/` — mọi thứ nằm ở đó: deliverable · files · acceptance · evidence · phụ thuộc.
2. Implement **đúng phạm vi**. Không thêm file ngoài danh sách. Không thêm dependency (cần thì DỪNG → ADR).
3. Chạy theo thứ tự: `chromly check` (G0) → unit tests (G1) → `acceptance/Mx.sh` (G2).
4. Commit: `Mx-NN: <what>` — evidence (lệnh + output chính) trong commit body.
5. Đánh dấu task file: `status: done` + commit hash.

## Khi bị chặn

- Blocked >30 phút: ghi `build/BLOCKED.md` (task id · câu hỏi · đã thử những gì) → báo operator → **chuyển task khác**. Không ngồi chờ.

## Cấm

- Sửa `runtime/` không qua Prompt CI (G3).
- Đổi kiến trúc / thêm dependency không có ADR (G4).
- Commit khi G0–G2 chưa xanh. Merge khi operator chưa duyệt (giai đoạn M0–M1).

## Ghi chú

- Acceptance scripts: architect viết cho task logic lõi (triage · scheduler · bench · budget); builder được viết cho task infra (bootstrap · scaffold · wrappers).
- Builder chạy trên **VM** (có sudo cài đặt) — khác case container.
