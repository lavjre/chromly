# chromly

Autonomous V8/Chrome bug-hunting system — fuzzing 24/7 (no LLM) + patch-diff intel + OpenCode agent cases (persona Nini). Target box: Ubuntu VM 8 vCPU · 16 GB · 200 GB.

- **Kế hoạch:** [PLAN.md](PLAN.md) — đọc **Chương 1 (§1) Research Philosophy** trước, rồi mới tới kiến trúc.
- **Tool inventory:** [TOOLS.md](TOOLS.md) — 30 callable surfaces at M3.
- **Quyết định kiến trúc:** [docs/adr/](docs/adr/) — không ADR, không merge.
- **Runtime:** `runtime/` — symlink vào `~/.config/opencode/` (`persona.txt` + `opencode.json` + `skills/` + IDA MCP); case chạy trực tiếp trên VM (ADR-009).

Trạng thái: **M0–M4 GREEN (2026-09-29/30)** — foundation · fuzz farm (1042 exec/s, watchdog, crash store, corpus, metrics) · intel track (watcher lag ~1h, agent review, KG) · triage + telemetry + **calibration 5/6 tái hiện trên x64** (parser · regexp · 2×JIT · maglev-phi; wasm entry arch-locked RISC-V/LoongArch/MIPS/PPC/s390x — xem `calibration/exploits/`) · case pipeline (**CASE-0001 → validated-crash, 11.6' · $0.06**) · MCP bridge (13 tool) · budget · scheduler · bench T1–T4 (T1 acc=1) · supervisor `chromly up/down` + systemd (supervisor · digest timer). Tiếp theo: **M5–M7 exploit lab**.

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
