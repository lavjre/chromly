# CHROMly — Tool List

> Đồng bộ PLAN.md v1.3. Trạng thái: ✅ có sẵn trong runtime hôm nay · 🚧 kế hoạch (milestone).
> Agent (OpenCode) gọi tool qua 3 tầng: built-in → MCP servers → skills.

---

## Tầng 0 — Built-in OpenCode V2 (✅ mọi agent, mọi lane)

| Tool | Action permission | Dùng cho | Policy chromly |
|---|---|---|---|
| `read` | `read` | source V8, asan.txt, notes.md | allow trong /case + /v8 |
| `edit` / `write` / `patch` | `edit` | notes.md, poc/, VERDICT.md, patch thử | allow trong /case; **triage/intel: deny** |
| `glob` | `glob` | tìm file case, build out dirs | allow |
| `grep` | `grep` | grep source V8, logs, crash | allow |
| `shell` | `shell` | chạy d8, repro.js, git, ninja, scripts | allow + deny-list: `sudo *`, `rm -rf /*` |
| `webfetch` | `webfetch` | docs V8, commit pages, VRP policy | allow |
| `websearch` | `websearch` | tra API/flag docs | allow |
| `subagent` | `subagent` | chia lane (case lead only) | allow cho `persona`; **analyst: deny** |
| `skill` | `skill` | load playbook `$v8-triage`... | allow |
| `question` | `question` | hỏi anh khi bí (→ HELP.md) | persona only |
| `execute` (Code Mode) | `execute` | batch nhiều call trong 1 bước | allow |

---

## Tầng 1 — MCP `ida` — Hex-Rays IDA MCP chính chủ (✅ đã wire trong `runtime/opencode.json`)

Server: `HexRaysSA/ida-mcp` (IDA Nexus, multi-client share DB). Chạy trong case container:
`uvx ida-mcp stdio --agent=opencode`.

| Tool | Chức năng | CHROMly dùng vào |
|---|---|---|
| `ida.open_database` | Mở binary / .i64 trong IDA Pro — headless idalib worker hoặc attach file đang mở trong GUI; chạy auto-analysis | Mở d8 release/ASAN, chrome binary, hoặc .i64 sẵn của case |
| `ida.execute_python` | Kênh chính: chạy IDAPython + ida-domain trên DB đang mở — decompile ra Hex-Rays, disasm, xrefs/callers/callees, func@addr, types/structs, rename, comment, **patch bytes**. Imports/vars persist theo lease | analyst: disasm crash-site khi source lệch binary; exploit-dev: gadget hunting, patch thử; intel: diff hàm trước/sau fix |
| `ida.reference` | Tra ida-domain API theo task/tên (bắt buộc tra trước execute_python — không đoán API) | Mọi lane dùng IDA |
| `ida.list_databases` | Liệt kê DB đang mở (GUI + idalib workers) + instance ids | Case lead quản phiên; anh xem chung GUI |
| `ida.save_database` | Save .i64 — persist rename/comment/type/patch | Cuối phiên IDA của case |
| `ida.close_database` | Nhả lease của session này (không đụng client khác); chờ shutdown an toàn nếu là lease cuối | Đóng phiên khi case xong |

Serialize: 1 phiên IDA nặng/lúc (RAM), nice 5, trong slice `case`. Fallback khi container vướng license: `uvx ida-mcp http --host 127.0.0.1 --port 8737` trên VM rồi container trỏ vào.

---

## Tầng 2 — MCP `chromly-tools` (🚧 M3, §5.7 — boundary duy nhất agent ↔ hạ tầng)

| Tool | Input → Output | Ai dùng |
|---|---|---|
| `case.get` / `case.update` | case_id → case state / patch state | persona |
| `crash.list` | filters → danh sách crash + score | persona, analyst |
| `crash.detail` | crash_id → metadata + asan + symbols | analyst, triage |
| `repro.run` | crash_id, build → ok/fail + output | analyst, exploit-dev |
| `build.request` / `build.status` | config, rev → build_id / status | persona, supervisor |
| `fuzz.status` | — → instances, execs/s | persona, dashboard |
| `store.put` / `store.get` | key, blob → — / blob | tất cả |
| `runs.append` | run record → — | supervisor |
| `kg.query` / `kg.neighbors` | câu hỏi cấu trúc → nodes + edges + lessons | agent (reason) |

Versioned `/v1/`, log mọi call, timeout mặc định 15'.

> Ghi chú: `ida.batch` **bỏ khỏi** chromly-tools — IDA đã có MCP chính chủ, giữ 1 server IDA duy nhất (Hex-Rays khuyến nghị tắt mọi MCP IDA khác để tránh agent confusion).

---

## Tầng 3 — Phase sau (🚧 chưa wire)

| MCP | Khi nào | Vì sao |
|---|---|---|
| `chrome-devtools` | M5 (exploit lab) | CDP điều khiển Chrome trên VM — PoC renderer, verifier, snapshot heap |
| `pao-tools` (rig Windows anh) | chưa — chỉ khi cần | VM tự đủ gdb/lldb/pwndbg cho ELF; không port giai đoạn này |
| `burpsuite` | không | V8 không phải target web |

---

## Skills (không phải tool — playbook agent load bằng `skill`)

`$v8-triage` · `$patch-diff-review` · `$repro-minimize` · `$exploit-primitive` · `$vrp-report` · `$ida-batch` (pattern dùng `ida.*` MCP + batch idalib cho job nặng)

---

## Supervisor CLI (không cho agent — cho anh)

`chromly up` · `chromly status` · `chromly cases list/show` · `chromly build` · `chromly intel` · `chromly doctor`

---

### Tổng kết hiện tại

- **✅ Hôm nay agent có:** 11 built-in + 6 tool IDA = **17 callable surfaces**
- **🚧 M3 thêm:** 13 tool chromly-tools = 30
- **🚧 M5 thêm:** chrome-devtools (30 tool của CDP family — chỉ bật khi cần)
