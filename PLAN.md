# CHROMly — Master Plan v1.6

> v1.5 → v1.6: **Phụ lục A → Chương 1 — Research Philosophy** (workflows + strategy + hiến pháp anti-patterns); thêm **Alert engine**, **KG query layer**, **calibration metadata**, **human override**, **KPI rubric**, **evolution v2–v4**; benchmark thêm **agent topology**; bỏ số capacity kinh tế cho tới M4.
> v1.4 → v1.5: nhận review kỹ thuật ngoài — thêm **Telemetry & Dashboard**, **Benchmark framework**, **Knowledge layer** (graph + notebook), **Prompt CI**, **Dynamic scheduler**, **ADR**; roadmap giãn **8–10 tuần** + tách **M5 Primitive / M6 Arb Read / M7 Arb RW**; kinh tế đổi thành **hypothesis** (đo lại sau M4).
> v1.3 → v1.4: thêm `TOOLS.md`; bỏ `ida.batch` khỏi chromly-tools.
> v1.2 → v1.3: Hex-Rays IDA MCP chính chủ (`HexRaysSA/ida-mcp`).
> v1.1 → v1.2: fallback chain = model free; Phụ lục A — reference workflows.
> v1.0 → v1.1: chốt — V8/Chrome · flash toàn lane · Go $10/tháng · corpus cả hai.
> Căn theo điều kiện thật: **VMware: 8 vCPU · 16 GB RAM · 200 GB SCSI · NAT · Ubuntu 26.04.1 LTS Desktop · IDA Pro 9.4.**

---

## 0. Executive view

**CHROMly là gì:** hệ thống tự hành hunt bug V8/Chrome — fuzzing chạy 24/7 không tốn LLM; intel track bòn patch-diff hằng ngày; khi có candidate, một case container chạy agent (OpenCode + persona Nini) để đi từ crash → root cause → PoC draft, không cần tay người.

**Chạy ở đâu:** Ubuntu VM 8c/16GB/200GB. Fuzz + build + case container sống chung — **scheduler theo metric là phần sống còn của thiết kế** (§6).

**Ra gì:** `cases/` đầy đủ, `runs.tsv` ledger, dashboard `chromly status`, và khi có finding thật — draft VRP report + PoC.

**Đường ăn sớm nhất:** Track B (patch-diff + variant). **Độ sâu dài hạn:** Track A (fuzz). **Thước đo trung thực:** calibration (§5.5) + benchmark (§8).

**Tự đo từ M3:** Telemetry → rollup → dashboard → trend → decision (§7.2) — mọi thay đổi vận hành phải trỏ về một metric. Thay đổi persona/skill/plugin nào cũng qua Prompt CI (§8).

**Chi phí:** Go $10/tháng — limit flash $60/tháng. **Hypothesis** (đo lại sau M4): intel daily + case volume **chưa ước lượng — đo ở M4**; chạm cap rơi về model **free**, không đứng máy (§11).

**Timeline:** M0–M4 = **8–10 tuần** (integration buffer ~30% đã tính) tới "crash → PoC không cần tay". M5–M7 exploit từ tuần 10+. M8 vận hành 24/7 liên tục.

**Tool surface:** 17 callable (built-in + IDA MCP) hôm nay → 28 ở M3 — chi tiết `TOOLS.md`.

---

## 1. Research Philosophy & Nguyên tắc (Chương 1)

> Toàn bộ kiến trúc phía sau sinh ra từ chương này. Đọc trước — §2+ chỉ trả lời "làm thế nào".

### 1.1 Reference workflows (vay từ researcher & dự án)

| Nguồn | Workflow cốt lõi | Áp ở |
|---|---|---|
| **Samuel Groß (saelo) / Project Zero — Fuzzilli** | REPRL fuzzing cho JS engine; exploit theo tầng primitive (addrof → fakeobj → arb R/W → exec); writeup kèm evidence từng bước | Track A (fuzzilli), §5.9 ladder M5–M7, notes.md `hypothesis \| evidence \| result` |
| **Ivan Fratric / P0 — Domato, structural fuzzing** | Grammar-based generation; đo fuzzer bằng coverage thật, không cảm tính | §5.2 structured seeds + corpus theo coverage; mọi đánh giá fuzzer kèm số (§7.2) |
| **Dataflow Security (Bruno Keith, Niklas Baumstark) — Pwn2Own Chrome** | Type confusion → primitive chuẩn; dev loop d8 + `--allow-natives-syntax`; đo reliability trước khi gọi là exploit | §5.9: ladder, verifier N=200→1000, dev trên d8 trước Chrome |
| **Man Yue Mo — V8 variant analysis & chains** | Fix commit là bản đồ: bug gì, thiếu check ở đâu, sibling path nào chưa fix; chain nhiều bug nhỏ | Track B intel; KG nodes commit→variant (§7.3); score ưu tiên chainable |
| **Brendon Tiszka — Chrome fuzzing program** | Đo lường & false-positive discipline; ưu tiên theo reward thật (VRP) | §5.4 FP filter + score; benchmark §8; acceptance số |
| **ZDI — Root Cause Analysis series** | RCA: root cause ≠ symptom; phân loại exploitable trước khi đầu tư | §5.4 classify + §5.6 notes protocol |
| **OSS-Fuzz-Gen / Big Sleep (Google)** | LLM sinh harness & phân tích variant — KHÔNG thay fuzzing; máy đọc crash theo batch | Track D: LLM chỉ ở triage/analysis |
| **ilio-mini (mahaloz)** | Harness agent-in-docker: loop + resume + nudge + ledger + HELP.md | §4.6, §5.6, §10 |

### 1.2 Ba workflow nguyên tinh thần

1. **Saelo — exploit theo tầng.** Không nhảy từ crash → "RCE". Mỗi case đi tuần tự: root cause → inline primitive → arb R/W → (sau) execution. Notes từng bước, mỗi bước có evidence. → ladder §5.9.
2. **Man Yue Mo — fix là bản đồ.** Mỗi security fix là một hint; Track B chạy hàng ngày; agent `intel` kết thúc bằng "variant nào còn sống"; KG ghi lại từng nhánh.
3. **Dataflow — đo trước khi tin.** Exploit chỉ là "có" khi verifier đủ N lần đạt ngưỡng; mọi tuyên bố kèm số. → verifier §5.9 + acceptance toàn roadmap.

### 1.3 Research Strategy — dùng workflow nào khi nào

| Tín hiệu | Đường đi | Lý do |
|---|---|---|
| Patch nhỏ, security-labeled | Track B variant analysis (auto) | fix là bản đồ — variant là đường rẻ nhất |
| Patch lớn / refactor rộng | intel lane deep-dive + IDA diff | auto-filter miss nhiều trong diff lớn |
| Crash mới, score cao | Case pipeline (triage → agent) | cần root cause + PoC |
| Variant hypothesis từ KG | Test trực tiếp trên build active + previous | có định hướng, không fuzz mù |
| Regression (calibration fail) | Calibration refresh + bench trước | sửa hệ thống trước khi săn bug |
| Surface stale (crash rate ↓) | Đổi corpus/chiến lược theo alert (§7.2) | telemetry dẫn đường |

### 1.4 Điều kiện đã chốt

**Đã chốt:**
- VM: 8 vCPU, 16 GB RAM, 200 GB disk, NAT, Ubuntu 26.04.1 LTS Desktop.
- Engine #1: **V8/Chrome**.
- Model: **flash toàn bộ lane** (`opencode-go/deepseek-v4.1-flash`) — §4.1.
- Ngân sách: **Go $10/tháng** — §11.
- Corpus: **kéo cả hai** (fuzzilli public + seed mjsunit) — §5.2.
- IDA Pro 9.4 + **Hex-Rays IDA MCP chính chủ** (`HexRaysSA/ida-mcp`) → first-class tool (§5.8).
- Provider: opencode-go. Runtime: OpenCode V2.
- Persona: `persona.txt` verbatim — mọi agent nạp persona Nini, không nhánh nào rơi về generic-assistant.

### 1.5 Nguyên tắc
1. **Fuzzing ngu–nhanh–rẻ, agent sâu–chậm–đắt.** LLM chỉ gọi khi có thứ đáng gọi.
2. **Supervisor không suy nghĩ về bug. Agent không quản hạ tầng.**
3. **Nguồn sự thật duy nhất:** persona.txt, kế hoạch này, store, ADR.
4. **Tất cả nặng (build / case / full fuzz) là mutually exclusive** — scheduler quyết định.
5. **Đo trước, tin sau:** calibration + benchmark + acceptance số ở mọi milestone.
6. Scope: V8/Chromium upstream + build local, report qua Chromium VRP. Ba hard stops persona giữ nguyên.
7. **Không telemetry thì không tối ưu** — mọi thay đổi vận hành (scheduler, corpus, model, prompt, ngưỡng score) phải trỏ được về một trend (§7.2).
8. **Mọi quyết định kiến trúc = 1 ADR (§9). Mọi thay đổi prompt/persona/skill = 1 lần bench qua Prompt CI (§8).** Không có ngoại lệ.

### 1.6 Hiến pháp — Anti-patterns (Never)

- **Never** để LLM thay fuzzing — LLM chỉ ở tầng triage/analysis.
- **Never** đổi persona/skill/plugin không qua benchmark — Prompt CI (§8).
- **Never** đổi scheduler không có telemetry làm bằng chứng (§6.5).
- **Never** đóng case không ingest knowledge (§7.3) — không có `knowledge.yaml` = case chưa xong.
- **Never** đổi kiến trúc không có ADR (§9).
- **Never** skip calibration refresh (§5.5).
- **Never** tối ưu một con số không được ghi lại (§7.2).

**Links chính:** github.com/googleprojectzero/fuzzilli · github.com/googleprojectzero/domato · github.com/google/oss-fuzz-gen · saelo.github.io · github.com/mahaloz/ilio-mini · github.com/HexRaysSA/ida-mcp · bughunters.google.com (Chromium VRP) · zerodayinitiative.com/blog

*Retro mỗi case: ghi 1 dòng "học được gì từ nguồn nào" vào notes — chương này sống, cập nhật liên tục.*

---

## 2. Bối cảnh kỹ thuật — bản đồ attack surface

**Target #1: V8/Chrome — chốt.**

| Surface | Bug class kỳ vọng | Kênh tiếp cận |
|---|---|---|
| TurboFan/Maglev/Turboshaft JIT | type confusion, OOB do optimizing sai | fuzzilli + intel diff `jit/ maglev/ turboshaft/` |
| Parser / AST | OOB, stack overflow sâu | libFuzzer `parser_fuzzer` + domato-style |
| RegExp engine | OOB, UAF, irregexp | libFuzzer + fuzzilli mutations |
| Wasm (compiler + runtime) | OOB, type confusion | libFuzzer wasm decoders + fuzzilli wasm |
| GC (scavenger/marking) | UAF, race | fuzzilli stress + dcheck builds |
| Sandbox (V8 sandbox, cushions) | bypass | ưu tiên thấp giai đoạn này |

**Chuỗi giá trị:** surface → (A fuzz ∥ B intel ∥ F calibration) → C triage → D case pipeline → E exploit lab → report.

---

## 3. Kiến trúc tổng thể

```
UBUNTU VM (8 vCPU · 16 GB · 200 GB)
┌──────────────────────────────────────────────────────────────────────┐
│ systemd slices: [svc 1.5G] [build 9G] [fuzz 4.5G] [case 4G]          │
│ CHROMLY SUPERVISOR (Python 3.12, asyncio)          ~0.2G             │
│   queue · budget governor · resume policy · ledger · watchdogs       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐             │
│  │ FUZZ FARM     │  │ BUILD RIG     │  │ INTEL WATCHER │             │
│  │ fuzzilli×4    │  │ V8×3 configs  │  │ V8+Chromium   │             │
│  │ libFuzzer×2   │  │ cache+GC      │  │ commit diff   │             │
│  └──────┬────────┘  └──────┬────────┘  └──────┬────────┘             │
│         │ crash            │build             │diff/hypothesis       │
│         └────────┬─────────┴──────────────────┘                      │
│                  ▼                                                   │
│  ┌────────────────────────────┐   ┌────────────────────────────┐     │
│  │ TRIAGE (no-LLM)            │   │ CALIBRATION HARNESS        │     │
│  │ repro · minimize · dedup   │   │ reverted-fix ground truth  │     │
│  │ classify · score           │   └────────────────────────────┘     │
│  └────────────┬───────────────┘                                      │
│               │ candidate                                            │
│               ▼                                                      │
│  ┌──────────────────────────┐  MCP   ┌──────────────────────────┐    │
│  │ MCP BRIDGE chromly-tools │◄──────►│ CASE CONTAINER (docker)  │    │
│  │ case/crash/repro/build/  │        │ opencode + persona.txt   │    │
│  │ fuzz/store/runs          │        │ agents · skills · plugin │    │
│  └──────────────────────────┘        │ /case mount · IDA 9.4    │    │
│                                      └────────────┬─────────────┘    │
│               ┌───────────────────────┐           │ VERDICT.md       │
│               │ EXPLOIT LAB           │◄──────────┘                  │
│               │ d8 harness · verifier │                              │
│               │ chain track (Mojo)    │                              │
│               └───────────────────────┘                              │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ TELEMETRY (§7.2): collect → rollup → dashboard → trend →     │    │
│  │ decision log — nuôi scheduler động (§6.5) + budget governor  │    │
│  │ BENCH & PROMPT CI (§8): T1–T4 · A/B config · auto-revert     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│ store: SQLite + cases/ + artifacts/ + runs.tsv + log.jsonl           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Runtime layer — OpenCode V2 (persona Nini)

### 4.1 Provider & model tiers — flash toàn bộ (chốt)

Mọi agent, mọi lane chạy `opencode-go/deepseek-v4.1-flash`. Fallback khi limit/lỗi = **model free của opencode-go** — Go cho phép tiếp tục chạy bằng free models khi đã chạm usage limit.

| Lane | Model | Fallback (free) |
|---|---|---|
| tất cả (case lead · triage · analyst · exploit-dev · intel) | `opencode-go/deepseek-v4.1-flash` | `longcat-2.5-preview-free` → `space-bunny-free` |

- Free tier là promotional "limited time" — governor probe định kỳ; nếu chết, rơi tiếp plan B: `glm-5.3-flash` → `mimo-v2.6-flash`.
- Đánh đổi chấp nhận: flash/free yếu hơn cho chain sâu — M5–M7 có thể nâng riêng `exploit-dev` bằng 1 dòng config nếu anh đổi ý.

### 4.2 Persona (bất biến)

- `runtime/persona.txt` — verbatim từ `~/.config/opencode/persona.txt` (SHA-256 khớp, đã verify).
- `runtime/opencode.json` — agent `persona`, `mode: primary`, `"prompt": "{file:./persona.txt}"`.
- **Mọi agent kể cả subagent nạp persona.txt.** Mission protocol nằm trong user prompt supervisor — không bao giờ trộn vào persona.
- Sửa persona.txt ở repo = mọi case nhận ngay (bind-mount ro) — **nhưng phải qua Prompt CI (§8) trước khi merge.**

### 4.3 Agents

| Agent | Mode | Model | Nhiệm vụ | Permissions riêng |
|---|---|---|---|---|
| `persona` | primary | flash | case lead: đọc brief, chia lane, nộp VERDICT.md | full trong /case |
| `triage` | subagent | flash | đọc crash/ASAN, repro, phân loại | deny `edit` |
| `analyst` | subagent | flash | root cause, source map, hypothesis | deny `subagent` |
| `exploit-dev` | subagent | flash | primitive, PoC | full |
| `intel` | subagent | flash | review diff, sinh variant test | deny `edit` |

M0 smoke test: shape `agent.<name>.prompt {file:...}` đa agent trên v2.x; fail → fallback markdown agents. Agents mở rộng (M5+, khi ladder cần debate): `critic` (phản biện root cause/PoC trước VERDICT), `reviewer` (soát VRP report), `planner` (chiến lược chia lane) — thêm sau M4, không đưa vào bây giờ.

### 4.4 Skills

`$v8-triage` · `$patch-diff-review` · `$repro-minimize` · `$exploit-primitive` · `$vrp-report` · `$ida-batch` (pattern dùng `ida.*` MCP + batch idalib cho job nặng). — mọi skill versioned bằng hash (§7.1 prompt_registry), đổi = qua bench.

### 4.5 Plugin `chromly.ts`

- `tool.execute.after` → nudge 10/30' "split lanes now" (thay `nudge.py`).
- `tool.execute.before` → guard scope container.
- `permission.hook("evaluate")` → policy: deny `sudo *` / `rm -rf /*`; allow trong `/case`.
- `session.hook("context")` → nhắc budget/format khi gần cạn.
- `event.subscribe()` → `log.jsonl` + **telemetry events** (§7.2).

### 4.6 Vòng lặp

```
opencode run --format json --agent persona -m opencode-go/<model> --auto "case: /case/CASE-xxxx ..."
opencode run -s <session-id> "you stopped without VERDICT; tiếp tục"     # resume
opencode run --fork -s <session-id> ...                                   # nhánh mới
opencode serve → /api/session/{id}/wait · /interrupt · /compact · stats   # control plane (từ M4)
```

- Budget mặc định/case: **wall 8h · resume ≤8 · token ≤6M** (calibrate lại bằng dữ liệu thật sau M4).
- VERDICT.md (validated-crash | no-bug | needs-human | report-draft) → stop container.
- HELP.md → dừng, gọi anh.
- Refusal/errors: `retry` hook → swap model → fresh session.
- Auth: `opencode auth` trên VM user; mount config/data ro vào container (paths từ `opencode debug paths`, chốt ở M0).

---

## 5. Subsystem specs

### 5.1 Build rig

- 1 checkout V8 duy nhất (gclient, shallow) + 3 out dirs: `out/release`, `out/dcheck` (`dcheck_always_on`), `out/asan` (`is_asan=true` + `v8_enable_verify_heap`).
- Build flags chuẩn: `is_debug=false`, `symbol_level=1` (asan: 2), `use_lld=true`, `v8_monolithic=true` cho d8, và target `v8_fuzzers` cho libFuzzer.
- Command surface: `chromly build --config asan --rev <ref>` chạy qua slice `build`, `ninja -j6`, nice 10. Cache: mỗi config giữ 1 revision active + 1 previous (cho diff test variant).
- Disk math (§6.3) — build rig là consumer lớn nhất. GC: xóa out dirs cũ theo revision khi disk alarm.

### 5.2 Fuzz farm

| Instance | Engine | Config | Vai trò |
|---|---|---|---|
| fuzzilli ×4 | d8 ASAN | REPRL, corpus chung | JIT/engine chính |
| libFuzzer ×2 | `v8_fuzzers` (parser, wasm) | corpus riêng | memory-safety nhanh |

- Watchdog per instance: hang >120s → kill + restart + log repro attempt.
- execs/s trung thực (ước tính, đo lại ở M1): fuzzilli 50–200/s/instance tuỳ program; libFuzzer parser 1–5k/s. **Mục tiêu M1: ≥300/s tổng ổn định 24h.**
- Corpus: **kéo cả hai** — corpus fuzzilli public + seed mjsunit (chốt); cull theo coverage-trim mỗi tuần; mọi crash lưu kèm corpus snapshot.

### 5.3 Intel watcher

- Sources: mirror GitHub `v8/v8` + `chromium/src` (fetch `--filter=blob:none`), poll mỗi giờ.
- Filter: path labels (`jit/ maglev/ turboshaft/ wasm/ regexp/ parser/ compiler/` + `sandbox`), keywords security.
- Pipeline: diff → normalize → agent `intel` review (bug gì · fix thế nào · variant nào còn sống) → nếu có variant hypothesis → auto-gen test chạy trên build active + previous → `cases/INTEL-*`.
- Cadence thực tế: ước tính 3–10 commit đáng review/ngày. Kết quả đổ vào knowledge layer (§7.3) — mỗi commit reviewed = 1 node.

### 5.4 Triage pipeline (no-LLM)

```
crash → repro ×5 trên build sạch (loại flaky) → minimize (d8→creduce-style>fuzzilli minimizer)
     → symbolize (llvm-symbolizer, ASAN report đầy đủ)
     → dedup: hash(stack frames đã normalize + fault type + access size)
     → classify: {heap-buffer-overflow, UAF, type-confusion(dcheck), OOM, timeout, ...}
     → score: WRITE(3) > READ(1); offset controllable(+2); gần JIT tier(+2); dcheck-only(-2); known-toy(-3)
     → score ≥ ngưỡng → queue case
```

- FP filter: crash trong fuzzer hạ tầng (harness bug), timeout, OOM-allocation → rớt không lên agent.
- Mọi bước ghi vào store + telemetry; case chỉ được tạo khi có repro tối giản + ASAN report + score.

### 5.5 Calibration harness (correctness)

- Cơ chế: chọn N fix lịch sử của V8 (đã public), **revert fix trên nhánh lab**, build → có ground-truth bug.
- Dùng để: (1) verify fuzz farm còn bắt được bug loại đó; (2) đo toàn pipeline: crash → triage → case → VERDICT (agent có tìm lại đúng root cause không); (3) đo MTTR và cost/case thật.
- Bộ chuẩn: 5 bug đầu (1 parser, 1 regexp, 1 wasm, 2 JIT/type-confusion). Rebuild + refresh mỗi ~2 tháng theo V8 mới.
- **Metadata mỗi bug (bắt buộc):** surface · bug_class · difficulty 1–3 · coverage intent · regression history (lần fail gần nhất) — lưu bảng `calibration` (§7.1), dùng cho bench T1 và chọn bug theo coverage của KG.
- Đây là **acceptance test của cả hệ thống**, chạy tự động hàng tuần. Phân biệt với **benchmark** (§8): calibration = đúng/sai, benchmark = cái nào tốt hơn.

### 5.6 Case pipeline (state machine)

```
NEW → BUNDLED (case dir: repro, asan, symbols, notes/, src-ref, triage.md, brief.md ← top-k related từ knowledge layer §7.3)
    → RUNNING (container opencode; resumes; nudges; budget)
    → VERDICT | HELP | TIMEOUT
    → ARCHIVED (nén artifacts, ghi runs.tsv, ingest knowledge.yaml, học vào calibration nếu đặc biệt)
```

- Case dir chuẩn: `cases/CASE-xxxx/{triage.md, brief.md, repro.js, asan.txt, symbols.txt, notes.md, knowledge.yaml, lessons.md, poc/, lanes/, VERDICT.md, log.jsonl}`.
- Prefetch trước khi agent chạy (giống ilio): symbolize + reproduce + build-check — agent mở mắt là đã có data.
- Case close: agent viết `knowledge.yaml` (nodes + edges + rejections bắt buộc — negative knowledge) → supervisor ingest vào §7.3.

### 5.7 MCP bridge `chromly-tools`

| Tool | Input | Output | Ai dùng |
|---|---|---|---|
| `case.get/update` | case_id, patch | case state | agent |
| `crash.list/detail` | filters, crash_id | metadata + asan | agent, supervisor |
| `repro.run` | crash_id, build | ok/fail + output | agent |
| `build.request/status` | config, rev | build_id, status | agent, supervisor |
| `fuzz.status` | — | instances, execs/s | supervisor, dashboard |
| `store.put/get` | key, blob | — | tất cả |
| `runs.append` | run record | — | supervisor |
| `kg.query` / `kg.neighbors` | câu hỏi cấu trúc (surface/function/commit/primitive) | nodes + edges + lessons | agent (reason, không chỉ retrieve) |

Boundary duy nhất agent ↔ hạ tầng. Versioned (`/v1/`), log mọi call, timeout mặc định 15'. **IDA đã có MCP chính chủ riêng (§5.8) — không nhân bản `ida.batch` ở đây** (Hex-Rays khuyến nghị 1 server IDA duy nhất). Inventory tool đầy đủ 3 tầng: `TOOLS.md`.

### 5.8 IDA Pro 9.4 + Hex-Rays IDA MCP (official)

- Server chính chủ **`HexRaysSA/ida-mcp`** (build trên **IDA Nexus** — nhiều client share/operate chung một IDA database).
- Cài: `uvx ida-hcli mcp install` (GUI plugin + agent plugin) — requirements: `uv` trong PATH, **IDA 9.4+ với idalib**, Python 3.11+.
- Kênh agent: **`uvx ida-mcp stdio --agent=opencode`** chạy trong case container, mount IDA install + license ro (RAM trong slice `case`); fallback `uvx ida-mcp http --host 127.0.0.1 --port 8737` trên VM khi cần GUI/đa client.
- Kênh batch (bổ sung): idalib/`idat -A -S` cho job nặng headless — crash-site disasm khi source không khớp binary, gadget hunting, diff hàm trước/sau fix trên release d8.
- Serialize 1 phiên IDA/lúc; **tắt mọi MCP IDA khác** (Hex-Rays khuyến nghị — tránh agent confusion); debug bằng `uvx ida-mcp dashboard` / `logs`.
- IDA license: giữ trong VM user profile, **không bake vào image**.

### 5.9 Exploit lab (M5–M7)

- d8 harness trước (no sandbox), Chrome `--no-sandbox` trên VM desktop sau.
- **Ladder (tách theo review — mỗi rung 1 milestone, không gộp):**
  - M5 · **Inline primitive**: addrof/fakeobj ổn định trên ≥1 calibration bug; harness tái dùng.
  - M6 · **Arb Read**: read primitive + leak; verifier ≥95% cho read.
  - M7 · **Arb RW**: đủ read/write; verifier ≥95% (N=1000).
- Verifier tự động: chạy PoC ×N với ASLR, log success rate, chặn "exploit chỉ đúng một lần".
- Chain track: sandbox escape (Mojo) nghiên cứu ở phase riêng sau M7 — không trộn acceptance.

---

## 6. Tài nguyên — căn theo 8 vCPU / 16 GB / 200 GB

### 6.1 RAM budget (16 GB)

| Thành phần | Steady | Peak | Ghi chú |
|---|---|---|---|
| OS + desktop | 1.5–2 GB | 2.5 | desktop giữ cho IDA GUI |
| Supervisor + SQLite + telemetry | 0.2 GB | 0.5 | telemetry sampling ~0.1 core |
| Fuzz A: fuzzilli ×4 | 2.5–3.5 GB | 5 | spike khi allocation lớn |
| Fuzz B: libFuzzer ×2 | 0.8–1.2 GB | 2 | |
| Triage workers | 0.5 GB | 2 | burst |
| Case container | 1.2 GB | 3.5 | opencode+node+IDA batch |
| Build `ninja -j6` | 0 (idle) | 8–10 | link bằng lld |
| Headroom | 1.5 GB | — | để không tự bắn chân |

**Luật scheduler baseline (M1 — tĩnh):**
- `build` active → fuzz 6→2 instance, case queue tạm dừng (trừ case đang chạy <1h).
- `case` active → fuzz 6→4, build defer.
- default → 6 fuzz + triage.
- Swap file 16–32 GB bật (spike ASAN); `earlyoom` bật; `oom_score_adj` fuzzer = 500 (vật tế), build/case = 100.
- Note host: VMware cảnh báo host recommend 13.3 GB — nếu host swap nhiều, chuyển profile 12 GB (bỏ 1 fuzzilli + giảm headroom).

### 6.2 CPU

- 8 vCPU: supervisor+OS ~1, fuzz 6 (nice +5), build nice 10 (`ninja -j6`), case container nice 0, IDA batch nice 5.
- CPU governor: performance; tắt apport; `perf_event_paranoid=2` (không hạ hơn — fuzz đủ quyền).

### 6.3 Disk (200 GB)

| Mục | GB |
|---|---|
| Ubuntu + tools + IDA | 25 |
| depot_tools + V8 checkout (shallow) | 25 |
| out dirs (release 8 + dcheck 12 + asan 18) | 38 |
| Docker (2 images + volumes) | 20 |
| store (corpus 10 + cases 10 + artifacts 10 + bench 2) | 32 |
| Headroom | ~60 |

- Watchdog: warn 75%, cull corpus + prune docker 80%, pause fuzz 85%, halt + gọi anh 90%.
- Case artifacts >30 ngày: zstd, giữ repro+VERDICT ở dạng đọc được.

### 6.4 systemd slices (cgroup v2)

```
chromly-svc.slice   MemoryHigh=1.5G
chromly-build.slice MemoryHigh=9G   CPUWeight=50   Nice=10
chromly-fuzz.slice  MemoryHigh=4.5G CPUWeight=200  Nice=5
chromly-case.slice  MemoryHigh=4G   CPUWeight=300  Nice=0
```

### 6.5 Dynamic scheduler (M4+ — nâng cấp từ luật tĩnh)

- **Inputs:** RAM pressure (MemAvailable + PSI), CPU pressure (PSI cpu.some), disk %, queue lengths (fuzz backlog, case queue, build queue), budget usage (rolling 5h/tuần), case phase.
- **Modes:** `NORMAL` (6 fuzz) · `FUZZ_LEAN` (2 fuzz) · `BUILD_WINDOW` (build active, fuzz 2) · `CASE_PRIORITY` (fuzz 4, build defer) · `RED` (halt heavy + alert).
- **Luật chuyển:** điều kiện giữ ≥60s mới chuyển; dwell tối thiểu 10'; mọi lần chuyển ghi `scheduler_decisions(ts, from, to, reason, snapshot)` — telemetry làm bằng chứng.
- **Deterministic, không ML.** Ngưỡng ban đầu = baseline §6.1; sau 2 tuần telemetry thì tinh chỉnh ngưỡng theo số thật (ví dụ: PSI >40% giữ 5' trong NORMAL → FUZZ_LEAN).
- Override tay: `chromly sched override <mode> <duration>`.

---

## 7. Dữ liệu, Telemetry & Knowledge

### 7.1 SQLite (chromly.db)

```sql
-- vận hành
crashes(id, hash, fault_type, stack_norm, severity, build_rev, source, created, state)
cases(id, crash_id, source, state, verdict, created, closed, budget_used, notes_path)
builds(id, config, rev, status, artifact_path, started, finished)
runs(id, case_id, session_id, model, prompt_hash, tokens_in, tokens_out, cost_est, wall_s, outcome)
intel(commit, paths, review_status, variant_flag, case_id)
budget(day, model, tokens_in, tokens_out, cost_est, tier_alerts)
-- telemetry (M3+)
metrics(ts, scope, name, value, tags)                 -- raw, sample 60s + event-based
metrics_rollup(day, scope, name, avg, p50, p95, max, n)
scheduler_decisions(ts, from_mode, to_mode, reason, snapshot_json)
alerts(id, ts, rule, severity, payload, ack)          -- alert engine (§7.2)
overrides(id, ts, operator, scope, action, reason, expires)  -- human override (§10.4)
prompt_registry(hash, kind, version, created, diff_note)   -- persona|skill|plugin|agent
-- knowledge (M3+)
kg_nodes(id, type, ref, attrs_json, case_id, created)
kg_edges(src_id, dst_id, rel, attrs_json, created)
lessons(id, case_id, kind, text, created)             -- lesson|failed_idea|interesting_commit|future_variant
calibration(id, bug, surface, bug_class, difficulty, coverage_note, last_fail)  -- §5.5 metadata
-- benchmark (M4+)
bench_runs(id, suite, config_hash, metrics_json, started, finished)
```

### 7.2 Telemetry pipeline — Collect → Aggregate → Alert → Dashboard → Trend → Decision

- **Collect:** supervisor + watchdogs + runner wrappers, sample 60s + event-based (crash found, case open/close, scheduler switch, refusal, limit-hit).
- **Aggregate (rollup giờ/ngày):** execs/s · crash rate · dedup ratio · FP rate · case MTTR · tokens/case · cost/case · refusal rate · watcher lag · queue depth · PSI/MemAvailable · bench deltas.
- **Alert engine:** rules chạy trên rollup — crash rate tụt 7d · corpus stale >14d không growth · refusal rate tăng >2σ · cost/case tăng 7d · watcher lag tăng · disk ngưỡng (§6.3) — alert vào dashboard + digest; severity cao → HELP gọi anh. Mọi alert có rule id + payload số, ack được (bảng `alerts` §7.1).
- **Dashboard:** `chromly status` (live) + digest tuần tự sinh (`store/reports/weekly-YYYY-WW.md`).
- **Trend:** slope 7d/28d cho: execs/s, crash discovery, cost/case, FP — phát hiện thoái hóa sớm (corpus cạn, fuzzer degrade, model đắt lên, prompt regression).
- **Decision:** mọi điều chỉnh (scheduler mode, corpus cull, model swap, ngưỡng score, prompt rollback) ghi lại kèm lý do + số liệu. **Không có metric thì không có quyền đổi thứ gì.**

### 7.3 Knowledge layer (graph-ready + notebook)

- **Graph-ready trong SQLite** (không graph DB ở giai đoạn này; export JSONL khi cần query phức tạp).
- **Node types:** crash/bug · commit/fix · surface · function · primitive · hypothesis · evidence · case · report · lesson. **Edges:** derived_from · fixed_by · affects · duplicates · variant_of · confirmed_by · rejected_by · produced.
- **Nguồn ghi:** triage (crash nodes) · intel (commit + variant nodes) · case close (`knowledge.yaml` ingest — rejections bắt buộc ghi: negative knowledge là tài sản).
- **Tiêu dùng:** case brief tự động kèm top-k node liên quan (cùng surface/commit/function) → agent không săn lại thứ đã chết; dashboard truy vấn "surface nào đang productive"; calibration chọn bug theo coverage của KG.
- **Query layer (active reasoning — không chỉ retrieve):** agent hỏi thẳng KG qua `kg.query`/`kg.neighbors` (§5.7): "surface này đã fail hypothesis nào?", "primitive nào từng thành công trên surface này?", "commit nào liên quan case hiện tại?" → trả về nodes+edges+lessons; mọi query log lại (query lặp nhiều = tín hiệu làm skill/bench).
- **Research Notebook:** `research/notebook.md` (curated, sống) + `cases/*/lessons.md`; digest tuần tự tổng hợp: Lesson Learned · Failed Ideas · Interesting Commits · Future Variants. Đây là trí nhớ dài hạn — review mỗi cuối tuần.

### 7.4 Retention & backup

- `cases/` + `store/` là vài GB đá — **snapshot VM hàng tuần** (ngoài VM, trên host), giữ 4 snapshots.
- DB: `sqlite3 .backup` hằng ngày vào `store/backup/` (giữ 7).
- Corpus: cull ≥7 ngày không coverage growth; crash repro không bao giờ xoá khi case chưa archived.
- Telemetry raw: giữ 30 ngày rồi chỉ giữ rollup. Bench data giữ vô hạn (nhỏ).

### 7.5 Evaluation rubric — KPI dài hạn

| KPI | Định nghĩa | Baseline | Đích 6 tháng |
|---|---|---|---|
| Finding rate | finding chất lượng / tháng (≥ validated-crash) | đo từ M4 | ≥1/quý — thực tế; hơn là bonus |
| Variant precision | % variant hypothesis từ intel thành test có giá trị | đo từ M2 | ≥40% |
| False positive | % case không có bug thật sau khi đóng | đo từ M3 | <15% |
| Research time | MTTR case: crash → VERDICT | đo từ M4 | median <6h |
| VRP success | report accepted / gửi | — | ≥1 accepted |

KPI sống trong dashboard (§7.2); mỗi tháng review — đổi target phải kèm lý do (decision log).

---

## 8. Benchmark & Prompt CI

**Phân biệt:** calibration (§5.5) = **đúng/sai** (hệ thống bắt được bug không). Benchmark = **cái nào tốt hơn** (model/prompt/skill/plugin/scheduler config nào).

**Suite `bench/`:**

| Task | Nguồn | Chấm |
|---|---|---|
| T1 root-cause | 5 calibration bug | accuracy: đúng function/root cause |
| T2 diff review | 10 commit đã biết kết cục (5 có variant sống / 5 sạch) | precision/recall của `intel` |
| T3 triage classify | 20 crash đã label | accuracy phân loại + score order |
| T4 harness sanity | repro pipeline | pass/fail end-to-end |

- **Metrics per run:** accuracy · tokens · wall · cost. **n ≥ 5 run/task**, báo median + spread (không tin 1 lần chạy).
- **Factors A/B:** model · persona hash · skills set · plugin on/off · scheduler mode · **agent topology** (số lane 0/2/4 · planning flat vs planner+critic). Benchmark luôn tính topology — không chỉ prompt.
- **Prompt registry (§7.1):** mọi phiên bản persona/skill/plugin/agent = 1 hash; mọi `runs` ghi hash → regression truy vết được về đúng thay đổi.
- **Prompt CI:** đổi persona/skill/plugin → `chromly bench --suite ci` chạy T1–T4; **gate: primary metric không giảm >2%, tối thiểu 1 metric cải; fail → auto-revert commit** (tag rollback). Chạy ban đêm trong slice `svc`.
- Bench data lưu `bench/runs/` + DB; report mới nhất `bench/latest.md`; dashboard hiển thị delta so với lần trước.

---

## 9. ADR — Architecture Decision Records

- `docs/adr/` — template (`0000-template.md`) + mỗi quyết định kiến trúc 1 file 10–20 dòng: **Bối cảnh / Quyết định / Phương án đã loại / Hệ quả**.
- Seed: ADR-001 (mẫu, đã viết) · ADR-002..008 backfill ở M0: case container · MCP boundary · static→dynamic scheduler · flash + free fallback · V8 first · calibration/benchmark split · IDA official MCP single-server.
- **Rule: không ADR, không merge.** Sau vài tháng đây là bộ nhớ kiến trúc của dự án.

---

## 10. Vận hành

### 10.1 systemd units

`chromly-supervisor.service` · `chromly-fuzz@.service` (instance) · `chromly-watchdog.timer` (60s) · `chromly-intel.timer` (1h) · `chromly-calibrate.timer` (weekly) · `chromly-bench.timer` (đêm) · `chromly-gc.timer` (daily) · `chromly-report.timer` (weekly).

### 10.2 Failure matrix

| Symptom | Detect | React |
|---|---|---|
| d8 hang | watchdog 120s | kill + restart + lưu repro attempt |
| OOM spike | earlyoom | pause 2 fuzzers, restart nạn nhân, log |
| Disk 85% | watchdog | cull corpus → prune docker → pause fuzz |
| opencode 429/limit | run log | backoff + swap free theo governor |
| refusal spiral | 2 lần liên tiếp | swap model + fresh session |
| container leak | `docker ps` >6h idle | kill + đánh dấu case |
| git fetch fail | 3 lần | backoff, alert |
| symbol fail | triage log | check llvm-symbolizer path, fallback addr2line |
| IDA seat busy | ida MCP lease | serialize, chờ (không song song) |
| VM host swap nặng | telemetry PSI + host cảm giác | hạ profile RAM 12GB |
| prompt regression | Prompt CI fail | auto-revert + ADR note |
| telemetry gap | watchdog check | re-arm sampler, alert |

### 10.3 Update policy

- V8 rev: pin theo milestone + update có chủ đích (không auto-roll giữa case).
- OpenCode: upgrade khi có lý do, sau khi smoke test lại (§4.6).
- Fuzzilli: pin commit; update định kỳ theo calibration week.
- Docker images: rebuild theo M-milestone, tag `chromly-case:mX`.
- Persona/skills/plugins: qua Prompt CI (§8) — không có đường tắt.

### 10.4 Human override

- Đường tắt cho anh ở mọi tầng: `chromly override <scope> <action> [--for 30m]` — scope: sched · case · fuzz · intel · budget.
- Mọi override ghi bảng `overrides` (§7.1) kèm lý do; override cùng chỗ ≥3 lần = thiết kế sai → mở ADR/plan update.
- Operator → Override → Record → ADR. Không override nào vô hình.

---

## 11. Kinh tế (opencode-go) — hypothesis, đo lại sau M4

**Plan: Go $10/tháng.** Limit tháng của `deepseek-v4.1-flash`: **$60** (5h = 20% → $12; tuần = 50% → $30).

| Hoạt động | Token (hypothesis) | Cost (hypothesis) |
|---|---|---|
| triage pass | 150–400k | $0.05–0.15 |
| analyst pass | 1–3M | $0.30–0.80 |
| exploit session | 1–2M | $0.50–1.50 |
| intel review/ngày | 1–3M | $0.30–0.60 |

- **Cap (đặt trước, chỉnh sau):** case $2 · ngày $2.5 · tháng $55 (chừa 10% dưới limit $60). Governor tôn trọng cửa sổ rolling: 5h ($12) và tuần ($30) — chạm → rơi về **model free** (`longcat-2.5-preview-free` → `space-bunny-free`), chỉ nhận case score cao; free chết → plan B `glm-5.3-flash`. **Có fallback free = không bao giờ đứng máy vì limit.**
- **Measurement plan (M4):** sau 2 tuần vận hành + 10 case thật, tính lại từ bảng `runs` (tokens/case thực, wall thực, refusal rate) → sửa caps, sửa budget §6, viết ADR cập nhật. **Capacity: chưa đưa con số — chỉ có số sau M4.**
- Cost target M4: <$2/case (đo thật, không phải đoán).

---

## 12. An toàn & opsec

- VM lab-only: NAT, không port-forward, không host creds trong VM, không target bên thứ ba — chỉ V8/Chromium upstream + build local, report qua Chromium VRP.
- Secrets: opencode auth mount ro; IDA license trong profile, không vào image.
- Artifacts chứa PoC nguyên — không rời VM khi chưa sanitize (paths, usernames) cho report.
- LUKS khi cài (tùy chọn desktop installer) — khuyến nghị.
- Ba hard stops persona giữ nguyên; không có luật mới nào được viết thêm vào runtime mà không qua anh + ADR.

---

## 13. Roadmap + acceptance + risk

**Timeline: 8–10 tuần tới M4 (integration buffer ~30% đã tính — coding nhanh, integration chậm).**

| Mốc | Tuần | Acceptance (đo được) |
|---|---|---|
| M0 Foundation & Doctor | 1 | `chromly doctor` xanh (swap, slices, docker, opencode, IDA, disk); build sạch ASAN d8 ≤90' với -j6; persona + resume `-s` OK; `debug paths` chốt; **IDA MCP handshake OK**; ADR-001..008 backfill |
| M1 Fuzz farm | 2–3 | ≥300 exec/s tổng, 24h liên tục, 0 leak; crash → store <5'; watchdog test pass |
| M2 Intel track | 3–5 | watcher lag <24h; ≥3 review/ngày tự động; ≥1 variant test sinh + chạy; KG nhận commit nodes |
| M3 Triage & Calibration | 5–7 | 5/5 ground-truth bắt được; FP filter ≥90%; score đúng thứ tự; **telemetry + dashboard v1 lên sóng**; prompt_registry hoạt động |
| M4 Case pipeline | 7–10 | 1 case ground-truth không cần tay <8h, <$2; **đo lại hypothesis kinh tế**; **dynamic scheduler bật**; bench suite T1–T4 chạy được; Prompt CI gate hoạt động |
| M5 Exploit lab — Primitive | 10+ | inline primitive (addrof/fakeobj) ổn định trên ≥1 calibration bug; harness tái dùng được |
| M6 Arb Read | tiếp | read primitive + leak; verifier ≥95% cho read |
| M7 Arb RW | tiếp | read/write đầy đủ; verifier ≥95% (N=1000) |
| M8 24/7 | liên tục | 7 ngày không can thiệp; dashboard + digest tuần tự động; trend report ra quyết định |

**Evolution sau M8 (trigger-driven — không hứa trước):**

| Ver | Scope | Kích hoạt khi |
|---|---|---|
| v2 | Distributed — nhiều worker VM/box, supervisor điều phối farm | 1 VM bão hòa (execs/s chạm trần liên tục) |
| v3 | Multiple targets — JSC/SpiderMonkey trước, kernel/mobile sau | V8 track chín (≥1 chu kỳ finding hoàn chỉnh) + calibration ổn định |
| v4 | Cross-engine differential — đối chiếu hành vi giữa các engine | v3 chạy ≥2 engine song song |

**Risk register:**

| # | Rủi ro | Xác suất | Giảm thiểu |
|---|---|---|---|
| 1 | 16GB không đủ khi fuzz+build+case chồng | cao | scheduler §6.1/§6.5, profile 12GB dự phòng |
| 2 | fuzzilli bề mặt hiện đại khó ra bug | trung bình | Track B + calibration giữ hệ thống có giá trị trước khi fuzz nổ |
| 3 | Model từ chối việc exploit | trung bình | persona + fallback free + fresh session; đo refusal rate ở M4 |
| 4 | OpenCode API drift (v2.x trẻ) | trung bình | pin version, smoke test trước upgrade |
| 5 | Disk đầy (build+corpus) | trung bình | budget §6.3 + GC timer |
| 6 | Calibration bug quá dễ/khó (méo số liệu) | trung bình | bộ 5 bug đa dạng + refresh định kỳ + bench T1 |
| 7 | VM host swapping kéo tụt tốc độ | trung bình | telemetry PSI + hạ RAM profile |
| 8 | Timeline integration trượt | trung bình | buffer 30% đã tính; milestone nào trượt thì cắt scope, không cắt acceptance |
| 9 | Prompt/system drift không phát hiện | thấp | Prompt CI + prompt_registry + auto-revert |
| 10 | Telemetry/bench ăn tài nguyên | thấp | chạy trên slice `svc` (~0.1 core), sample 60s, bench chạy đêm |
| 11 | Sau này exploit cần Chrome/mojo — ngoài 16GB | thấp | M5 dùng d8 trước; Chrome chạy từng phiên, không song song build |
| 12 | Crash trùng lặp đội queue | thấp | dedup ở C + KG duplicate edges trước khi tạo case |

---

## 14. Còn lại (nhỏ, không chặn M0)

- **LUKS** khi cài Ubuntu — đề xuất: có nếu không phiền passphrase mỗi boot; không trả lời → mặc định không, thêm sau được.
- **Snapshot VM weekly ×4** — bật khi host dư ≥60 GB; không dư thì snapshot trước mỗi milestone.
- Đã chốt: V8/Chrome · flash toàn lane · Go $10 · corpus cả hai.

---

## Phụ lục A — đã chuyển

Reference workflows từ v1.6 nằm ở **Chương 1 (§1) — Research Philosophy**. Giữ mục này để link cũ không gãy.
