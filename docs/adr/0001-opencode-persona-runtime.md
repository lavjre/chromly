# ADR-001 — OpenCode V2 + persona.txt làm agent runtime

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

CHROMly cần một agent runtime tự hành chạy headless trên Ubuntu VM, thay pattern Codex của ilio-mini. Yêu cầu cứng: session resume + budget control (supervisor loop), plugin hooks (nudge/policy/event log), skills (playbook), MCP (IDA, chromly-tools), và **một persona cố định** (Nini) xuyên suốt mọi case — không nhánh nào được rơi về generic-assistant biết từ chối.

## Quyết định

Dùng **OpenCode V2** (`opencode run --format json` cho turn loop, `opencode serve` cho control plane) với agent `persona` nạp `runtime/persona.txt` qua `"prompt": "{file:./persona.txt}"`. Persona bind-mount read-only vào case container — một nguồn duy nhất, sửa file ở repo là mọi case nhận ngay.

## Phương án đã loại

- **Codex CLI** (như ilio-mini) — hooks mạnh nhưng provider khác (không dùng opencode-go), hệ plugin hẹp hơn, auth mount riêng; không đáng đổi cả hệ sinh thái.
- **Custom Python loop gọi API trực tiếp** — mất sạch tool/skill/MCP/permission ecosystem, phải tự viết lại; không đáng cho solo op.
- **Nhét persona vào system prompt per-case** — phân mảnh, drift, không version được, không audit được.

## Hệ quả

+ Resume/retry/plugin/skills/MCP có sẵn; đổi runtime sau này chỉ đụng tầng §4, không chạm scheduler/logic.
+ Persona là 1 file duy nhất, versioned bằng hash (`prompt_registry` §7.1) — nhưng **bắt buộc qua Prompt CI (§8)** trước khi merge, fail → auto-revert.
− Phụ thuộc OpenCode v2.x trẻ (risk #4) — giảm thiểu: pin version, smoke test trước mọi upgrade.
