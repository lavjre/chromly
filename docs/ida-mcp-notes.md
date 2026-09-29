# IDA MCP — ghi chú vận hành (M0-06)

Server chính chủ **HexRaysSA/ida-mcp** (IDA Nexus). Command chuẩn (trong `runtime/opencode.json`):

```
uvx --exclude-newer=1s ida-mcp stdio --agent=opencode
```

## Trạng thái trên VM (2026-09-29)

- IDA Pro 9.4: `~/ida-pro-9.4` (idat + idalib). License: `~/.idapro/ida.reg` (+ `idapro.hexlic` trong IDA dir).
- ida-mcp server version: `20260924.0.3` — 6 tool: `open_database · execute_python · reference · list_databases · save_database · close_database`.
- Smoke (task M0-06): `tools/ida_smoke.py` — initialize → tools/list → open_database (`backend: idalib`) → execute_python (`IDA-SMOKE-OK`) → close_database. Exit 0.
- Log phiên: `~/.idapro/mcp/sessions/*.jsonl` · stderr smoke: `store/logs/acceptance/ida-smoke-stderr.log`.

## Vận hành

- Debug phiên MCP: `uvx ida-mcp dashboard` (xem session) hoặc `uvx ida-mcp logs` (export zip).
- **Serialize 1 phiên IDA nặng/lúc** (RAM trong slice `case`); tắt mọi MCP IDA khác — Hex-Rays khuyến nghị.
- Fallback khi container vướng license (M4): chạy trên VM `uvx ida-mcp http --host 127.0.0.1 --port 8737`, container trỏ vào.
- `--exclude-newer=1s`: pin tránh release mới nhất vừa publish có thể hỏng (uv loại bản mới hơn 1s trước hiện tại — no-op an toàn, operator đặt).
- `execute_python` bắt buộc tra `ida.reference` trước khi đoán API (theo TOOLS.md) — không đoán hàm ida-domain.

## Evidence M0-06

```
bash acceptance/M0-ida.sh   # → PASS (exit 0)
[ida-smoke] server: ida 20260924.0.3
[ida-smoke] tools/list: 6 tools: open_database, execute_python, reference, list_databases, save_database, close_database
[ida-smoke] execute_python → {"stdout": "IDA-SMOKE-OK\n"}
[ida-smoke] HANDSHAKE OK — IDA MCP sống, license + idalib hoạt động
```
