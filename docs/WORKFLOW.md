# chromly — Workflow hiện tại (2026-10-04)

> Mục đích: bức tranh end-to-end "hệ đang săn bug thế nào, từng mảnh nối nhau ra sao".
> Chi tiết từng mảnh: `build/tasks/M*.md` · quyết định: `docs/adr/` · đọc số: `docs/info-guide.md`.

## 0. Sơ đồ tổng

```
                ┌─────────────────────── Track A: fuzz 24/7 (no LLM) ───────────────────────┐
                │  fuzzilli (jobs=6)      → crashes/ *.js+.fzil                            │
                │  lfuzz-parser           → artifacts/ crash-*                             │
                │  lfuzz-wasm             → artifacts/ crash-*                             │
                │  diffopt lane (4 axis)  → diff miscompile / release-crash                │
                └───────────────────────────────┬──────────────────────────────────────────┘
                                                ▼
 ingest (15s) ──► crash store <sha256>/ + DB(state=raw)
                                                │
 triage (300s) ──► repro ×5 (out/asan) → classify (heap-buffer-overflow/UAF/dcheck/…) + score
                                                │
                 ┌──────────────┬───────────────┴───────────────┐
                 ▼              ▼                               ▼
              flaky          raw (0 repro)                  triaged (score≥…)
           (re-check 2h)   (backoff 6h)                         │
                                                                ▼
                                        auto-case (900s, 1/lúc) ── budget gate ──► agent
                                        (deepseek 4.1, scratch riêng) repro ×5, root-cause
                                                                │
                                            VERDICT: validated-crash · no-bug(→fp) · needs-human · report-draft
                                            TIMEOUT → auto-resume ≤8 · runner chết → reclaim ≤1 tick

                ┌─────────────────────── Track B: intel (patch-diff) ───────────────────────┐
                │  watcher (~1h): fetch v8+chromium → commit mới (SECURITY_KW)             │
                │  review (2h): agent đọc diff → review.md + variants.json (test_js)       │
                │  variants: chạy test trên asan+release d8 → crash store (source=variant) │
                │  audit (24h): delta mirror → regression test mới → crash (upstream-regress)│
                └───────────────────────────────┬──────────────────────────────────────────┘
                                                ▼
                                  (cùng đường triage → case như Track A)

                ┌─────────────────────── Track C: verify & quyết định ─────────────────────┐
                │  tot verify: repro trên ToT d8 → STILL-CRASHES / CLEAN (unfixed?)        │
                │  s1 (laya System One): kind/exploitable/impact/ladder/next — advisory    │
                │  exploit lab: L0/L1 ladder (M5-03) — chờ crash có primitive              │
                └──────────────────────────────────────────────────────────────────────────┘
```

## 1. Track A — fuzz farm

| Unit | Là gì | Output |
|---|---|---|
| `fuzzilli` | JS engine fuzzer (REPRL, jobs=6) | `store/fuzz/fuzzilli/crashes/` (.js + .fzil) |
| `lfuzz-parser` | libFuzzer engine, parse V8 (M1-08) | `store/fuzz/lfuzz-parser/artifacts/` |
| `lfuzz-wasm` | libFuzzer engine, wasm module | `store/fuzz/lfuzz-wasm/artifacts/` |
| `diffopt` lane | differential JIT: default vs `no-opt/no-sparkplug/no-maglev/deopt-100` | crash store (`source=diffopt`) |

- **ingest (15s)**: quét mọi nguồn trên → `store/crashes/<sha256>/` + DB (`state=raw`). Dedup theo hash.
- **triage (300s)**: raw → chạy repro ×5 trên `out/asan` → `classify` (fault_type) + `score`
  (§: WRITE +3 · READ +1 · UAF/TC +3 · gần JIT +2 · dcheck −2 · harness −3) → state
  `flaky` (chập chờn, re-check 2h) / `raw` (0 repro, backoff 6h) / `triaged`.
- **diffopt lane**: quét corpus tuần tự (cursor), mỗi program 2 cấu hình + confirm 6×/bên;
  diff → `miscompile-diff` (sev 4); crash release → `release-crash` (sev 5). Đây là lane bắt
  **miscompile không-crash** (lớp bug crash-detector bỏ lỡ).

## 2. Track B — intel (patch-diff)

- **watcher**: fetch mirror v8/chromium (~1h/lần), lọc commit theo keyword bảo mật → `store/intel/<sha>/` (diff + meta).
- **review (2h)**: agent (deepseek 4.1) + skill `patch-diff-review` → `review.md` + `variants.json`
  (test_js chạy được trên d8; đã nhắc bắt buộc `%PrepareFunctionForOptimization` trước intrinsics JIT).
- **variants**: chạy test_js trên `out/asan` + `out/release` → crash → crash store (`source=variant`).
  FP filters: flag-conflict · `fp-manual-opt` · async-worker.
- **audit (24h)**: delta giữa mirror và checkout → regression test mới chạy trên builds →
  crash (`source=upstream-regress`) — **n-day fuel** (đã fix upstream, dùng luyện pipeline + dataset).
- **KG**: mỗi commit review → node/edge (knowledge graph) cho tra cứu sau.

## 3. Track C — verify & quyết định

- **`chromly tot verify`** (ADR-012): build ToT (asan+dcheck) một lần, sau đó mọi repro chạy được
  trên ToT → `STILL-CRASHES` (còn sống) / `CLEAN` (đã fix). Case mission tự chèn đường dẫn ToT.
  Đây là bước bắt buộc trước mọi claim "0day".
- **`chromly s1`** (M5-05): decision layer local (laya, System One) — chấm crash theo
  `kind / exploitable / impact / ladder / next`. Hiện **advisory** (zero-shot chưa đủ tin);
  **M5-05b**: fine-tune trên dataset 14 item (crash store + calibration + verdict) đang chạy,
  eval trên holdout 3 item.
- **exploit lab** (M5): L0 assessment → L1 ladder (addrof/fakeobj, verifier ≥95%×200) — **chờ
  substrate** (chưa crash nào có primitive điều khiển được; xem `build/tasks/M5-03-l1-primitive.md`).

## 4. Vòng đời crash (DB state)

```
raw ──triage──► flaky ──(ổn định)──► triaged ──case──► fp (no-bug)
 │                │                      │
 │ (0 repro,      └─ re-check 2h         └─ validated-crash / needs-human / report-draft
 │  backoff 6h)                                (case VERDICT)
```

Severity ≥4 → auto-case bắt. Source: `fuzzilli · lfuzz-* · diffopt · variant · upstream-regress`.

## 5. Vòng đời case

`BUNDLED → RUNNING → VERDICT | HELP | TIMEOUT | ERROR`
- `TIMEOUT` → auto-resume (≤8 lượt, session cũ nếu có)
- runner chết giữa case → **reclaim ≤1 tick** → TIMEOUT (hết kẹt 6.5h)
- budget-deny → `DENIED` + vào `_archive` (không để husk)
- verdict `no-bug` → crash đánh dấu `fp` tự động.
- case chạy trong scratch riêng `/tmp/opencode/chromly-case/<id>`; agent **deepseek 4.1**.

## 6. Hạ tầng & giám sát

- **System slice**: farm + aux chạy dưới `chromly-supervisor.service` (systemd) — miễn nhiễm
  oomd user-slice (bài học 04/10: oomd kill cả scope terminal 35 process).
- **Aux loops (11)**: watchdog 60s · ingest 15s · metrics 60s · sched 60s · triage 300s ·
  cases 900s · diffopt 540s+120s · review 2h · audit 24h · intel ~1h · s1 serve (thường trú).
- **watchdog**: hang (CPU ticks đứng) / dead → kill+restart; crash-loop → degraded 30' rồi tự hồi;
  aux chết → respawn; case RUNNING quá hạn → TIMEOUT.
- **monitor**: `chromly info [-w]` (FARM · CORPUS · AUX · INTEL · CASES · CRASH · BUILD · TOT ·
  BUDGET · DISK) + `chromly trace -f` (feed sự kiện). Guide: `docs/info-guide.md`.
- **budget**: ngân sách ngày cho case (tier model); `alerts` telemetry; digest tuần (timer).

## 7. Các vòng phản hồi tự động (điểm mạnh của hệ)

```
audit ──► n-day crash ──► triage ──► case ──► verdict ─┐
variants ──► crash ────────────────────────────────────┤
diffopt ──► miscompile candidate ──────────────────────┤
                                                       ▼
                             crash store + verdict + ToT results
                                                       │
                                                       ▼
                                       dataset S1 (tự lớn) ──► fine-tune ──► ranking tốt hơn
```

## 8. Cheat sheet

```bash
chromly up / down / info -w / trace -f          # vận hành + giám sát
chromly fuzz status | engine --list | engine --merge --unit <u> | lfuzz --unit <u> --once
chromly triage list                              # crash + score + state
chromly case list                                # case + state
chromly tot build | status | verify <crash>      # unfixed check trên ToT
chromly s1 check | triage <hash> | dataset | finetune | eval-ft
chromly intel audit --max 40 | intel review --limit 2 | intel status
```

## 9. Trạng thái hiện tại (04/10 21:30)

- Crash store: **19 rows** (n-day 7 · variant fp 5 · diffopt/case artifacts …) — 0 unfixed.
- Cases: tới **CASE-0015** (hầu hết variant FP → đã auto-fp). *Follow-up: variant lane còn FP
  đều đặn (5 case fp gần đây) — nên thêm filter như đã làm với diffopt.*
- S1: M5-05b fine-tune đang chạy (2 epoch, CPU); eval holdout sẽ nổ số `ft_acc vs base_acc`.
- Gaps đang mở: exploit ladder (chờ substrate) · variant FP filter · refresh ToT khi có candidate.
