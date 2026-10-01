# ADR — Architecture Decision Records

Mỗi quyết định kiến trúc của chromly = 1 file, 10–20 dòng. Format: `0000-template.md`.

**Rule: không ADR, không merge** — mọi thay đổi kiến trúc phải kèm ADR (PLAN §9).

## Danh sách

| ADR | Quyết định | Trạng thái |
|---|---|---|
| [001](0001-opencode-persona-runtime.md) | OpenCode V2 + persona.txt làm agent runtime | Accepted |
| [002](0002-case-container-docker.md) | Case container (docker) thay vì venv/process | Superseded by [009](0009-case-direct-on-vm.md) |
| [003](0003-mcp-boundary.md) | MCP bridge `chromly-tools` là boundary duy nhất agent ↔ hạ tầng | Accepted |
| [004](0004-scheduler-static-to-dynamic.md) | Scheduler: tĩnh trước (M1), động theo metric sau (M4) | Accepted |
| [005](0005-flash-plus-free-fallback.md) | Flash models + fallback free của opencode-go | Accepted |
| [006](0006-v8-first.md) | V8 first (thay vì JSC/SpiderMonkey) | Accepted |
| [007](0007-calibration-vs-benchmark.md) | Calibration (đúng/sai) tách khỏi Benchmark (so sánh) | Accepted |
| [008](0008-ida-official-mcp-single.md) | 1 server IDA duy nhất (Hex-Rays official MCP) | Accepted |
| [009](0009-case-direct-on-vm.md) | Case chạy trực tiếp trên VM (supersede 002) | Accepted |
| [010](0010-libfuzzer-engine-defer.md) | libFuzzer engine: replay v0, engine để v2 (shim) | Superseded by [011](0011-libfuzzer-engine-relink.md) |
| [011](0011-libfuzzer-engine-relink.md) | libFuzzer engine: re-link ninja + vendor source (không patch V8) | Accepted |
