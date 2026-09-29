# ADR — Architecture Decision Records

Mỗi quyết định kiến trúc của CHROMly = 1 file, 10–20 dòng. Format: `0000-template.md`.

**Rule: không ADR, không merge** — mọi thay đổi kiến trúc phải kèm ADR (PLAN §9).

## Danh sách

| ADR | Quyết định | Trạng thái |
|---|---|---|
| [001](0001-opencode-persona-runtime.md) | OpenCode V2 + persona.txt làm agent runtime | Accepted |
| 002 | Case container (docker) thay vì venv/process | Backfill M0 |
| 003 | MCP bridge `chromly-tools` là boundary duy nhất agent ↔ hạ tầng | Backfill M0 |
| 004 | Scheduler: tĩnh trước (M1), động theo metric sau (M4) | Backfill M0 |
| 005 | Flash models + fallback free của opencode-go | Backfill M0 |
| 006 | V8 first (thay vì JSC/SpiderMonkey) | Backfill M0 |
| 007 | Calibration (đúng/sai) tách khỏi Benchmark (so sánh) | Backfill M0 |
| 008 | 1 server IDA duy nhất (Hex-Rays official MCP) | Backfill M0 |
