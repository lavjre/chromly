# Hướng dẫn đọc `chromly info` + event feed (`chromly trace`)

> Viết 2026-10-02. Mục đích: nhìn 1 màn biết hệ đang khỏe hay không, có gì mới,
> và số nào cần hành động. Nguồn số liệu: `chromly/telemetry/monitor.py`.

## 1. Bố cục `chromly info`

```
══ chromly info — 2026-10-02 15:20:34 ══
FARM    lfuzz-parser ● 99/s · lfuzz-wasm ● 147/s · fuzzilli ● 45/s
AUX     10/10 loop sống
  audit      CRASH  test/mjsunit/.../regress-563068683.js → 216c15a22212  (9277s trước)
  ...
```

### 1.1 FARM — worker fuzz

| Hiển thị | Nghĩa |
|---|---|
| `●` | unit đang sống (nếu chết: `DEAD`, watchdog restart trong ≤60s) |
| `X/s` | throughput gần nhất parse từ log: fuzzilli = `execsPerSecond` (stats JSON); lfuzz-* = dòng `exec/s:` cuối trong log |

Đọc thế nào:

- **lfuzz-***: vài trăm/s là khỏe (wasm ~400–800, parser ~100–300). Tụt dần theo thời gian =
  corpus phình → chạy `chromly fuzz engine --merge --unit <u>` (đo thật: wasm 112→493/s sau merge).
- **fuzzilli**: ~40–55/s là bình thường trên box này (build dcheck, jobs=6). <10/s hoặc
  0 = xem `store/fuzz/logs/fuzzilli.log` (REPRL chết / kẹt corpus import).

### 1.2 AUX — 10 loop nền

Mỗi dòng: `tên  <dòng cuối log>  (X giây trước)`. `X` = mtime log — càng nhỏ càng mới.
Nhịp từng loop: watchdog 60s · ingest 15s · metrics 60s · triage 300s · cases 900s ·
sched 15s · diffopt 540s+120s · review 7200s (agent) · audit 86400s · intel 3600s.

- `(trống)` = loop sống, không có gì để in (vd ingest không có crash mới). **Không phải lỗi.**
- Dòng có nghĩa đặc biệt:
  - `audit CRASH <test> → <hash12> (Xs trước)` — lần cuối audit tìm được crash mới (n-day).
  - `review {"sha":…, "status":"reviewed", "variants":N}` — 1 commit vừa review xong, N variant.
  - `watchdog watchdog: aux:X restarted (dead)` — loop X từng chết, đã tự chữa. Thỉnh thoảng
    có là bình thường; lặp liên tục = loop X crash-loop.
- Loop nào có `X giây trước` quá lớn so với nhịp → đang chạy việc dài (review agent chạy ~2–3')
  hoặc treo (watchdog restart).

### 1.3 INTEL

`pending` commit chờ review · `reviewed` đã review · `variants` số commit đã chạy variant ·
`lag` độ trễ mirror so với upstream (càng nhỏ càng tốt; **>6h = watcher chậm, nên xem**).
`KG` = knowledge graph (node/edge).

### 1.4 CASES

`running=(không)` hoặc id case đang chạy · `cuối: CASE-XXXX <STATE>`.

Case states: `BUNDLED` (mới tạo) → `RUNNING` (agent đang làm) → `VERDICT` (xong, có kết luận |
`HELP` (agent cần người) | `TIMEOUT` (quá giờ — sẽ auto-resume ≤8 lần) | `ERROR`.

### 1.5 CRASH

`tổng=N` = số row trong store · `mới: <hash12> <fault_type> s<severity> (<source>)`.

States (vòng đời): `raw` (mới ingest, chờ triage) → `flaky` (không tái hiện ổn định, không auto-case;
re-check 2h/lần) → `triaged` (đã phân loại + chấm điểm) → có case → `fp` (kết luận không phải bug)
hoặc giữ `triaged` (bug thật, có thể đã nộp/không nộp được).

Severity (score §5.4): `WRITE +3 · READ +1 · UAF/type-confusion +3 · gần JIT +2 · dcheck −2 ·
fuzzer-harness −3`. **≥4 → auto-case bắt**; âm/0 = check-only, khó khai thác.

Sources: `fuzzilli` · `lfuzz-*` (engine) · `variant` · `upstream-regress` (audit) · `diffopt` ·
`fixture` (test).

### 1.6 BUILD / TOT

- `BUILD` = 3 record gần nhất: `<config> <status> <Xs>`. status: `ok` / `error` / `killed`
  (bị interrupt) / `running`. `killed 0s` đứng đầu = record cũ đã đóng, không phải lỗi mới.
- `TOT` = build upstream mới nhất (`ok <sha12> age=Xh`). Dùng `chromly tot verify <repro>`
  để check bug còn sống/unfixed. `age` > vài ngày → chạy lại `chromly tot build`.

### 1.7 BUDGET / DISK

`day $X · tier=flash` — chi phí LLM hôm nay + tier model case đang dùng (budget chọn theo ngày).
`DISK XG free · alerts(unacked)=N` — dung lượng + alert telemetry chưa xác nhận.

## 2. Event feed — `chromly trace -f`

Nguồn gộp: `store/fuzz/events.jsonl` (watchdog/farm) · `store/logs/plugin-events.jsonl`
(shell/deny) · `cases/*/log.jsonl` (case) · KG · MCP · aux logs · DB. Lọc: `--source watchdog,case,...`.

### 2.1 Event watchdog/farm (`events.jsonl`)

| event | nghĩa |
|---|---|
| `kill` | unit bị kill, kèm `reason`: `dead` (chết) · `hang` (treo >HANG_S) · `cooldown-recovery` |
| `restart` | unit được respawn |
| `degraded` | crash-loop ≥3 lần/10' → tạm dừng 30' |
| `recover` | hết cooldown, tự chạy lại |
| `corpus-quarantine` | fuzzilli corpus import abort → đổi tên corpus cũ, chạy sạch |
| `unit-broken` | record hỏng, bỏ qua (không chết watchdog) |
| `restart-failed` | respawn fail (thiếu binary…) |
| `aux-restart` | loop nền chết → respawn |
| `case-stale` | case RUNNING >6.5h → đánh TIMEOUT (lưới an toàn) |
| `case-reclaim` | runner chết giữa case → TIMEOUT sớm (≤1 tick) |

### 2.2 Event plugin (`plugin-events.jsonl`)

- `shell` — command chạy trong vùng agent (telemetry).
- `deny` — command khớp deny-list (vd `rm -rf /`, fork bomb…) bị chặn.

### 2.3 Case events (`case log.jsonl`)

`case CASE-XXXX new …` (tạo mới) · `case CASE-XXXX state <STATE> …` (đổi trạng thái).

## 3. Đọc nhanh (cheat sheet)

| Câu hỏi | Nhìn đâu |
|---|---|
| Có gì mới? | FARM rates · CRASH mới · audit/review/diffopt (AUX) |
| Có candidate 0day? | CRASH `s≥4` + source `variant`/`upstream-regress` → `chromly tot verify` |
| Hệ khỏe không? | AUX 10/10 + số giây vừa nhịp + BUDGET trong hạn + DISK dư |
| Vì sao không có case chạy? | `cases: 0 candidate` = không crash nào đủ điểm + chưa có case (bình thường) |
| Fuzz chậm? | lfuzz tụt → `engine --merge`; fuzzilli tụt → xem log |
