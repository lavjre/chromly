# ADR-008 — 1 server IDA duy nhất (Hex-Rays official MCP)

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

Agent cần decompile/xrefs/patch trên d8/Chrome binaries. IDA Pro 9.4 + license đã có trên VM. Cộng đồng có nhiều MCP IDA khác nhau; chạy nhiều server cùng lúc gây agent confusion (nhiều tool trùng chức năng, DB không share).

## Quyết định

Dùng **duy nhất** `HexRaysSA/ida-mcp` (official, build trên IDA Nexus — multi-client share/operate chung một DB): `uvx ida-mcp stdio --agent=opencode`. Tắt mọi MCP IDA khác (§5.8). Serialize 1 phiên IDA nặng/lúc (RAM); job nặng headless qua idalib; fallback `uvx ida-mcp http --host 127.0.0.1 --port 8737` khi container vướng license. `ida.batch` không nhân bản trong `chromly-tools` (TOOLS.md).

## Phương án đã loại

- **Tự viết MCP IDA** — công bảo trì vô ích; Hex-Rays đã có server chính chủ + hỗ trợ idalib/Nexus.
- **Nhiều MCP IDA song song** — trùng tool, split state, đúng cảnh báo Hex-Rays về agent confusion.

## Hệ quả

+ Chính chủ, đủ 6 tool (open/execute/reference/list/save/close), multi-client qua Nexus; smoke M0-06 đã xác nhận (idalib + license chạy).
− Phụ thuộc dự án bên thứ ba + 1 seat license; giảm thiểu: fallback http mode, batch idalib dự phòng, pin version qua `uvx --exclude-newer`.
