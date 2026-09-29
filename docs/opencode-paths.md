# OpenCode paths — chốt cho M4 (case runner, direct on VM — ADR-009)

> Sinh từ `opencode debug paths` trên VM (opencode v2.0.18, 2026-09-29) — task M0-05.
> Case runner (M4, trực tiếp trên VM — ADR-009) dùng các path này; `runtime/` là config qua symlink (PLAN §4.6).

| Key | Path |
|---|---|
| home | `/home/lavjre` |
| data | `/home/lavjre/.local/share/opencode` |
| cache | `/home/lavjre/.cache/opencode` |
| config | `/home/lavjre/.config/opencode` |
| state | `/home/lavjre/.local/state/opencode` |
| tmp | `/tmp/opencode` |
| bin | `/home/lavjre/.cache/opencode/bin` |
| log | `/home/lavjre/.local/share/opencode/log` |
| repos | `/home/lavjre/.local/share/opencode/repos` |
| db | `/home/lavjre/.local/share/opencode/opencode.db` |

## Ghi chú cho case runner (M4 — direct, ADR-009)

- `config` — `runtime/` symlink vào `~/.config/opencode` (persona · opencode.json · skills); repo là source of truth,
  `git pull` là cập nhật. Symlink hiện tại: `~/.config/opencode/{opencode.json,persona.txt,skills}`
  → `~/chromly/runtime/...` (xem `runtime/personabuilder.sh`).
- Skills: global discovery source của OpenCode V2 = `~/.config/opencode/skills` (docs: `.opencode/skills/<id>/SKILL.md`
  hoặc `skills/` folder); 6 playbook ở `runtime/skills/` — symlink sẵn, case process nhận trực tiếp.
- `data` — dùng chung db/log của VM user; session per-case tách bằng session id riêng (`opencode run -s <id>`).
- `tmp` — `/tmp/opencode` trên VM (đã pre-create; build/triage/IDA smoke dùng).
- Auth: `opencode auth` trên VM user; case process dùng cùng auth sẵn có (v2.0.18 lưu auth qua service — không cần mount file).

## Evidence M0-05

- `bash acceptance/M0-opencode.sh` → persona run trả `SMOKE-OK`, resume cùng session trả `RESUME-OK`
  (session `ses_f1448fb38ffe1Mu8edyRkX6Fej`).
- Log đầy đủ: `store/logs/acceptance/opencode-smoke.log` (+ `opencode-paths.txt`).
