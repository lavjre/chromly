# M4-11 — Runtime plugin `chromly` (§4.5) — deny-list + shell telemetry

**Status:** done
**Deliverable:** `runtime/plugins/chromly/index.ts` (OpenCode V2 plugin, load qua `plugins`
trong `runtime/opencode.json`):
- `ctx.permission.hook("evaluate")`: deny-list an toàn cho shell — `sudo`, `rm -rf /`(và ~/*),
  `mkfs`, `dd … of=/dev/…`, fork bomb, `shutdown/reboot`, `chmod -R 777 /` — deny + message.
- `ctx.shell.hook("create.before")`: telemetry — log mọi shell command (ts, cwd, 300 ký tự đầu)
  vào `store/logs/plugin-events.jsonl`.
- Options: `logPath` (default store/logs/plugin-events.jsonl).
**Files:** `runtime/plugins/chromly/index.ts`, `runtime/opencode.json`, `build/tasks/M4-11-runtime-plugin.md`
**Acceptance:** smoke `opencode run --agent persona` trả lời bình thường (plugin không phá runtime);
agent thử `sudo true` bị deny (message chromly); `plugin-events.jsonl` có entry shell.
**Evidence (2026-10-01):**
- Discovery layout qua symlink `~/.config/opencode/plugins -> runtime/plugins`; shared service
  tự hot-load (watcher) — `plugin-loaded` cho mọi location, không cần restart.
- Deny thật: agent trong `/tmp/opencode/chromly-case/PLUGIN-TEST` chạy `sudo true` →
  `permission.rejected: "sudo bị chặn trong phiên agent (chromly deny-list)"`; log có
  `deny scope=agent cmd=sudo true`.
- Scope: session người (cwd repo) chỉ bị LOG — lệnh test chứa chữ "sudo" không bị chặn
  (false-positive đã gặp và sửa bằng location-scope).
- M0-opencode smoke 4/4 (persona + resume vẫn xanh khi plugin bật).
**Out of scope:** nudge loop (case runner đã có resume), event-stream telemetry đầy đủ (follow-up).
**Phụ thuộc:** OpenCode v2 plugin API (docs /build/plugins).
