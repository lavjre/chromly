// chromly runtime plugin — §4.5
// - Deny-list an toàn cho shell (permission hook) + telemetry shell (mọi lệnh → plugin-events.jsonl).
// - Scope: nhóm THẢM HỌA luôn chặn; nhóm `sudo`/`rm -rf /` chỉ chặn trong scratch của agent
//   không-giám-sát (/tmp/opencode/chromly-case/*, /tmp/opencode/chromly-intel/*) — session người
//   (operator/builder) giữ tự do, chỉ log. Tránh false-positive khi lệnh chỉ *nhắc tới* sudo.
// Đặt trong ~/.config/opencode/plugins/ (discover layout) — zero-dep, pattern-match thuần.
import { appendFileSync } from "node:fs"

type Rule = { test: (cmd: string) => boolean; why: string }

function rmRoot(cmd: string): boolean {
  const parts = cmd.match(/(^|[\s;&|])rm\s+[^;&|\n]+/g) ?? []
  for (const part of parts) {
    const recursive = /(^|\s)(-[a-zA-Z]*r|--recursive)/.test(part)
    const force = /(^|\s)(-[a-zA-Z]*f|--force)/.test(part)
    const rootTarget = /(\s|^)(\/|\/\*)(\s|$)/.test(part)
    if (recursive && force && rootTarget) return true
  }
  return false
}

// Luôn chặn — không có nhu cầu chính đáng nào trong vận hành chromly.
const ALWAYS: Rule[] = [
  { test: (c) => /(^|[\s;&|])mkfs(\S*)?(\s|$)/.test(c), why: "mkfs bị chặn (chromly deny-list)" },
  {
    test: (c) => /(^|[\s;&|])dd\s[^;&|\n]*of=\/dev\//.test(c),
    why: "dd ghi vào /dev bị chặn (chromly deny-list)",
  },
  { test: (c) => /:\s*\(\s*\)\s*\{[^}]*\}\s*;\s*:/.test(c), why: "fork bomb bị chặn" },
  {
    test: (c) => /(^|[\s;&|])(shutdown|reboot|poweroff)(\s|$)/.test(c),
    why: "lệnh tắt máy bị chặn (chromly deny-list)",
  },
  {
    test: (c) => /(^|[\s;&|])chmod\s+-R\s+777\s+\/(\s|$)/.test(c),
    why: "chmod -R 777 / bị chặn (chromly deny-list)",
  },
]

// Chỉ trong scratch của agent tự hành — nơi không có người ngồi trước màn hình.
const AGENT_ONLY: Rule[] = [
  { test: (c) => /(^|[\s;&|])sudo(\s|$)/.test(c), why: "sudo bị chặn trong phiên agent (chromly deny-list)" },
  { test: rmRoot, why: "rm -rf / bị chặn (chromly deny-list)" },
]

type Ctx = {
  options: Record<string, unknown>
  app: { version: string }
  location: { directory: string }
  permission: { hook: (name: string, cb: (event: any) => void) => Promise<unknown> }
  shell: { hook: (name: string, cb: (event: any) => void) => Promise<unknown> }
}

export default {
  id: "chromly",
  async setup(ctx: Ctx) {
    const logPath =
      typeof ctx.options.logPath === "string"
        ? ctx.options.logPath
        : "/home/lavjre/chromly/store/logs/plugin-events.jsonl"
    const dir = ctx.location.directory ?? ""
    const agentScope =
      dir.startsWith("/tmp/opencode/chromly-case/") || dir.startsWith("/tmp/opencode/chromly-intel/")

    const log = (entry: Record<string, unknown>) => {
      try {
        appendFileSync(logPath, JSON.stringify({ ts: Date.now(), ...entry }) + "\n")
      } catch {
        // logging không được làm chết runtime
      }
    }

    await ctx.permission.hook("evaluate", (event) => {
      if (event.effect === "deny") return
      if (event.action !== "shell") return
      const rules = agentScope ? [...ALWAYS, ...AGENT_ONLY] : ALWAYS
      for (const resource of event.resources ?? []) {
        const hit = rules.find((r) => r.test(String(resource)))
        if (hit) {
          event.effect = "deny"
          event.message = `${hit.why}: ${String(resource).slice(0, 200)}`
          log({
            event: "deny",
            scope: agentScope ? "agent" : "global",
            action: event.action,
            why: hit.why,
            cmd: String(resource).slice(0, 300),
          })
          return
        }
      }
    })

    await ctx.shell.hook("create.before", (event) => {
      log({ event: "shell", cwd: event.cwd, cmd: String(event.command).slice(0, 300) })
    })

    log({
      event: "plugin-loaded",
      version: ctx.app.version,
      directory: dir,
      agentScope,
    })
  },
}
