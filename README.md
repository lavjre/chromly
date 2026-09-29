# chromly

Autonomous V8/Chrome bug-hunting system — fuzzing 24/7 (no LLM) + patch-diff intel + OpenCode agent cases (persona Nini). Target box: Ubuntu VM 8 vCPU · 16 GB · 200 GB.

- **Kế hoạch:** [PLAN.md](PLAN.md) — đọc **Chương 1 (§1) Research Philosophy** trước, rồi mới tới kiến trúc.
- **Tool inventory:** [TOOLS.md](TOOLS.md) — 30 callable surfaces at M3.
- **Quyết định kiến trúc:** [docs/adr/](docs/adr/) — không ADR, không merge.
- **Runtime:** `runtime/` — symlink vào `~/.config/opencode/` (`persona.txt` + `opencode.json` + `skills/` + IDA MCP); case chạy trực tiếp trên VM (ADR-009).

Trạng thái: **M0 DONE (2026-09-29)** — doctor xanh · build rig (ASAN d8 43.9') · persona+resume · IDA handshake · skills runtime · 8/8 task acceptance GREEN. Tiếp theo: **M1 fuzz farm**.

## Dev flow

- **Build + chạy: chỉ trong Ubuntu VM** — V8, fuzzilli, docker, systemd, cgroup: Linux-only. Windows không build được fuzzer stack (và không nên — giành tài nguyên với VM).
- Windows/host: edit docs + config → `git push`; VM: `git pull` để chạy.
- Hoặc VS Code Remote-SSH thẳng vào VM — edit & run cùng chỗ, git vẫn là cầu.

## Quickstart — persona trên VM (sau clone)

```bash
cd ~/chromly
opencode auth login                  # một lần: chọn opencode-go
./runtime/personabuilder.sh          # mini + persona + flash (flags verified v2.0.18)
./runtime/personabuilder.sh -t       # full TUI (persona qua default_agent)
./runtime/personabuilder.sh -r "hi"  # headless one-shot
```

Script tự symlink `persona.txt` + `opencode.json` → `~/.config/opencode/` — repo vẫn là source of truth, `git pull` là cập nhật persona.
