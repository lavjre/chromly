# ADR-009 — Case chạy trực tiếp trên VM (supersede ADR-002)

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0 · **Supersedes:** [ADR-002](0002-case-container-docker.md)

## Bối cảnh

ADR-002 chọn docker container cho case agent để cách ly fs + limit RAM. Thực tế tới M0: VM **đã lab-only** (NAT, không creds host, không target bên thứ ba — §12), **1 case/lúc**, và docker kéo theo phức tạp thật: mount auth opencode (v2.0.18 lưu auth qua service, không phải file rời), mount IDA install + license, overhead ~1.2GB/container trên 16GB, GC image/volume. Operator chốt: **case chạy trực tiếp trên VM** — bỏ docker khỏi đường chạy.

## Quyết định

Case runner (M4) = **process trực tiếp trên VM** dưới `chromly-case.slice` (MemoryHigh=4G, CPUWeight=300):

- `opencode run` chạy cùng user `lavjre`, config = symlink `runtime/` (persona · skills · agent) — như mọi session khác; auth + IDA license dùng sẵn trong profile.
- Workdir giới hạn trong `cases/CASE-xxxx/` + V8 checkout (đọc); permission deny-list qua OpenCode permissions (§4.5: deny `sudo *`, `rm -rf /*`, ghi ngoài `/case`).
- IDA dùng trực tiếp idalib trên VM (không license mount, không http fallback vì license — fallback `http` chỉ còn cho GUI/đa client).
- Docker giữ cài nhưng **không nằm trên đường chạy** (doctor: optional).
- Supervisor quản case process: PID, nice, timeout, kill-stale (watchdog §10.2).

## Phương án đã loại

- **Docker container (ADR-002)** — overhead + auth/IDA plumbing; giá trị cách ly thấp khi VM đã chuyên dụng lab-only.
- **VM phụ mỗi case** — quá nặng so với 16GB (đã loại từ trước).

## Hệ quả

+ Đơn giản hơn hẳn: không image/volume/mount plumbing; tiết kiệm ~1.2GB RAM; IDA/license/GUI dùng trực tiếp; process dễ kill/restart/giám sát.
− Cách ly yếu hơn container — dựa vào OpenCode permission rules + slice + vành đai VM. Giảm thiểu: deny-list bắt buộc (§4.5), 1 case/lúc, watchdog kill process >6h idle, code case chỉ nằm trong `cases/`.
