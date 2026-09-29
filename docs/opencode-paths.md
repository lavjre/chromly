# OpenCode paths — chốt cho M4 (case container)

> Sinh từ `opencode debug paths` trên VM (opencode v2.0.18, 2026-09-29) — task M0-05.
> Case container (M4) mount các path này theo `runtime/` (PLAN §4.6).

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

## Ghi chú mount cho case container (M4)

- `config` — mount `runtime/` (persona.txt · opencode.json) read-only; repo là source of truth,
  `git pull` là cập nhật persona. Symlink hiện tại trên VM: `~/.config/opencode/{opencode.json,persona.txt}`
  → `~/chromly/runtime/...` (xem `runtime/personabuilder.sh`).
- `data` — mount volume riêng của container (session db + log per-case); không chia sẻ db với VM
  (tránh đụng session của operator), auth mount theo §4.6 khi cần.
- `tmp` — trỏ `/tmp/opencode` trong container; đã pre-create trên VM.
- Auth: `opencode auth` trên VM user; path auth lấy từ `opencode debug paths` + kiểm tra `auth list`
  (bản v2.0.18 lưu auth qua service, không có file `auth.json` rời — xác nhận lại khi dựng image M4).

## Evidence M0-05

- `bash acceptance/M0-opencode.sh` → persona run trả `SMOKE-OK`, resume cùng session trả `RESUME-OK`
  (session `ses_f1448fb38ffe1Mu8edyRkX6Fej`).
- Log đầy đủ: `store/logs/acceptance/opencode-smoke.log` (+ `opencode-paths.txt`).
