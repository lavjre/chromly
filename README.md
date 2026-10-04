# chromly

Autonomous V8/Chrome bug-hunting system — fuzzing 24/7 (no LLM) + patch-diff intel + OpenCode agent cases (persona Nini). Target box: Ubuntu VM 8 vCPU · 16 GB · 200 GB.

- **Kế hoạch:** [PLAN.md](PLAN.md) — đọc **Chương 1 (§1) Research Philosophy** trước, rồi mới tới kiến trúc.
- **Đọc monitor:** [docs/info-guide.md](docs/info-guide.md) — hướng dẫn đọc `chromly info` + event feed (`chromly trace`).
- **Tool inventory:** [TOOLS.md](TOOLS.md) — 30 callable surfaces at M3.
- **Quyết định kiến trúc:** [docs/adr/](docs/adr/) — không ADR, không merge.
- **Runtime:** `runtime/` — symlink vào `~/.config/opencode/` (`persona.txt` + `opencode.json` + `skills/` + IDA MCP); case chạy trực tiếp trên VM (ADR-009).

Trạng thái: **M0–M4 GREEN (2026-10-02)** — foundation · fuzz farm (**libFuzzer engine mode thật — ADR-011**: re-link ninja per-target + vendor source, không patch V8; farm = fuzzilli (jobs=6, ~53 exec/s sustained) + `lfuzz-parser` ~150-330/s + `lfuzz-wasm` ~370-840/s, corpus tự mọc, per-target 16 harness) · **diffopt lane liên tục** (4 axis JIT, cursor sweep ~4k program/cycle, finding → crash store) · **ToT verify (ADR-012)**: `chromly tot build|verify` — check unfixed trên upstream mới nhất (2 chiều đã smoke: CLEAN cho bug đã fix · STILL-CRASHES cho crash giả lập) · watchdog · crash store · corpus (+`engine --merge`) · metrics · intel track (watcher lag ~1h, review agent, KG; FP filter `%Optimize*`-thiếu-prepare) · triage + telemetry · **calibration 5/6 tái hiện trên x64** (parser · regexp · 2×JIT · maglev-phi; wasm entry arch-locked RISC-V/LoongArch/MIPS/PPC/s390x — xem `calibration/exploits/`) · case pipeline (**tự reclaim case kẹt + resume ≤8**; CASE-0001 → validated-crash 11.6' · $0.06; CASE-0004 → validated-crash, xác nhận đã-fix-upstream qua ToT) · MCP bridge (13 tool) · budget · scheduler · bench T1–T4 (T1 acc=1) · supervisor `chromly up/down` + systemd (supervisor · digest timer). Tiếp theo: **M5–M7 exploit lab**.

## Fuzz farm — lệnh chính

```bash
chromly up                                        # supervisor: farm units + aux loops
chromly fuzz status                               # fuzzilli + lfuzz-parser + lfuzz-wasm
chromly fuzz engine --list                        # 16 per-target harness trong out/libfuzzer
chromly fuzz engine --build [--fuzzer regexp]     # vendor libFuzzer + re-link engine (không patch V8)
chromly fuzz lfuzz --unit lfuzz-<target> --once   # mutation 1 cycle cho bất kỳ harness nào
chromly fuzz lanes                                # xoay 2 lane phụ qua 14 target (full 16)
chromly fuzz engine --merge --unit lfuzz-parser   # tối giản corpus định kỳ (giữ backup)
chromly tot build · status · verify <crash|file>  # build ToT + check "còn sống" (unfixed)
chromly s1 serve · check · triage <hash>          # System One (laya) — chấm crash (advisory)
chromly s1 dataset · finetune · eval-ft          # fine-tune S1 trên data chromly (M5-05b)
chromly info -w · chromly trace -f                # monitor + trace
```


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
