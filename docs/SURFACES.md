# chromly — Target surfaces (toàn bộ, 2026-10-04)

> Legend: ● đang chạy · ○ sẵn sàng (1 lệnh) · ◐ chỉ theo dõi (intel) · ✗ chưa có.
> Số liệu fix/90d + bug-class mix: `store/reports/surface-<date>.md` (tự sinh bởi `chromly recon report`).

## 1. Lanes đang fuzz (●)

| surface | lane | cấu hình | Phủ gì |
|---|---|---|---|
| JS engine (full) | `fuzzilli` jobs=6 | `--profile=v8 --fuzzing --harmony --experimental-fuzzing --js-staging --wasm-staging --wasm-fast-api --expose-fast-api --wasm-test-streaming` | parser, interpreter, sparkplug/maglev/turbofan, IC, GC, builtins, wasm, harmony/JSPI, fast-api |
| JS parser | `lfuzz-parser` | libFuzzer engine (M1-08) | `test/fuzzer/parser.cc` path: parse/preparse, lazy compile, scope analysis |
| wasm module | `lfuzz-wasm` | libFuzzer engine | wasm decode/validate/compile/instantiate |
| JIT differential | `diffopt` lane | default vs `--no-opt` / `--no-sparkplug` / `--no-maglev` / `--deopt-every-n-times=100` | miscompile không-crash (differential semantics) |

## 2. Harness sẵn sàng — `chromly fuzz engine --list` (○, 16 target)

```
inspector  json  multi_return  parser  regexp
wasm_async  wasm_code  wasm_compile  wasm_compile_all  wasm_compile_revec
wasm_compile_simd  wasm_compile_wasmgc  wasm_deopt  wasm_init_expr
wasm_module  wasm_streaming
```
Bật bất kỳ: `chromly fuzz engine --build --fuzzer <t>` → `chromly fuzz lfuzz --unit lfuzz-<t>`.
**16/16 engine binary build xong (04/10)**; **lane rotator** (`chromly fuzz lanes`, aux `lanes`) giữ
2 lane phụ xoay vòng qua 14 target còn lại (slice 2h/target) → toàn bộ harness đều được chạy theo thời gian,
không vượt ngân sách CPU của box.

## 3. Fuzzilli profiles khác (○ — đổi 1 cờ)

`v8` (● đang chạy) · `v8Sandbox` / `v8Dumpling` / `v8holefuzzing` — cần **build d8 riêng từng profile**
(xem `build/tasks/M1-10-fuzzilli-extra-profiles.md`, đã thử và có bằng chứng fail cụ thể).
(Các engine khác — jsc, spidermonkey, … — không thuộc target.)

## 4. Surfaces có bug tái hiện được trên x64 (calibration, ● verified)

| surface | bug | lớp | ladder |
|---|---|---|---|
| maglev | 567129324 · 567177599 · be64fd6d | type-confusion-field, miscompile-type/range | ✗ (đã khảo sát — M5-03) |
| turboshaft | 539984773 | oob-read (revert drift, no-repro) | ✗ |
| parser | c2001427 | check-fail-parse | ✗ |
| regexp | 56786f2a | wrong capture lookbehind | ✗ |
| wasm | 2338fbb0 | oob offset truncation | arch-locked (x64 không trigger) |

## 5. Intel surfaces — patch-diff 90 ngày (◐)

**V8** — fixes/90d: `jit 72` · `wasm 20` · `api-embed 20` · `objects-runtime 15` · `builtins-torque 11` · `gc-heap 6` · `sandbox 2` · `parser 1` · `regexp 0` · `interpreter 0` · `other 30`.
Bug-class mix chủ đạo: crash-other, oob, overflow, use-after-free, sandbox.
Harness tương ứng: jit→fuzzilli · wasm→lfuzz-wasm · parser→lfuzz-parser · regexp→fuzzilli.

**Chromium** — fixes/90d: `blink 82` · `sandbox-browser 53` · `gpu 8` · `network 4` · `mojo-ipc 0` · `content-renderer 0` · `other 387`.
Hiện chỉ watcher + review (◐); lab chrome (blink/mojo/content) để M5+ (✗).

**Nguồn crash đã từng đổ về store** (surfaces thật đã chạm): upstream-regress (wasm/dcheck · turbolev escape-analysis · weakrefs scavenger) · variant (wasm TPT/CPT · JIT-flags) · diffopt (JIT) · fuzzilli (engine).

## 6. Ưu tiên theo data (từ surface report)

1. **jit** (72 fixes, mix nặng) — đã có 3 lane (fuzzilli + diffopt + variants).
2. **wasm** (20 fixes) — có lane module; có thể thêm `wasm_compile*`/`streaming` khi CPU rảnh.
3. **blink** (82) + **sandbox-browser** (53) — chỉ intel; cần chrome lab (M5+) mới fuzz được.
4. **objects-runtime / builtins-torque** (15/11) — đã phủ gián tiếp qua fuzzilli.

## 7. Bảng lệnh theo surface

```bash
chromly fuzz engine --list                                  # 16 harness khả dụng
chromly fuzz engine --build --fuzzer regexp                 # bật surface mới (engine mode)
chromly fuzz lfuzz --unit lfuzz-regexp --seconds 120 --once # chạy 1 cycle surface đó
chromly fuzz engine --merge --unit lfuzz-<x>                # vệ sinh corpus theo surface
chromly intel status · recon report                         # intel/surface report (fix/90d)
chromly s1 triage <crash> · tot verify <crash>              # quyết định & xác minh trên surface đã có crash
```
