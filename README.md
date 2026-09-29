# CHROMly

Autonomous V8/Chrome bug-hunting system — fuzzing 24/7 (no LLM) + patch-diff intel + OpenCode agent cases (persona Nini). Target box: Ubuntu VM 8 vCPU · 16 GB · 200 GB.

- **Kế hoạch:** [PLAN.md](PLAN.md) — đọc **Chương 1 (§1) Research Philosophy** trước, rồi mới tới kiến trúc.
- **Tool inventory:** [TOOLS.md](TOOLS.md) — 30 callable surfaces at M3.
- **Quyết định kiến trúc:** [docs/adr/](docs/adr/) — không ADR, không merge.
- **Runtime:** `runtime/` — mount → `/root/.config/opencode/` trong case container (`persona.txt` + `opencode.json` + IDA MCP).

Trạng thái: **M0-ready** (docs + runtime config). Supervisor / fuzz farm / triage code bắt đầu từ M0.
