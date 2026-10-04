# Bản đồ target surface — săn 0day Chrome (góc nhìn researcher, 2026-10)

> Mục đích: liệt kê **toàn bộ** bề mặt tấn công mà researcher dùng để tìm 0day Chrome,
> kèm bug-class điển hình và trạng thái của chromly (● có lane · ◐ intel-only · ✗ chưa có).
> Chain đầy đủ của 1 0day Chrome hiện đại = **renderer RCE (1) + sandbox escape (2)** —
> thiếu (2) thì bug vẫn giá trị nhưng thấp hơn nhiều.

```
 ┌── (1) renderer compromise ──────────────────────────────────────────────┐
 │  Web content → [V8] ── [Blink/Web APIs] ── [bindings]                  │
 │      → memory corruption trong RENDERER                                │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │ Mojo IPC (validate ở đầu nhận)
 ┌── (2) sandbox escape ────────▼──────────────────────────────────────────┐
 │  browser process · GPU · network · utility · storage · OS sandbox      │
 │  (seccomp/LSM · win32k/AppContainer · seatbelt) → kernel (ngoài VRP)   │
 └─────────────────────────────────────────────────────────────────────────┘
```

## 1. V8 — renderer JS engine (surface sâu nhất, nhiều bug nhất)

| # | Sub-surface | Bug class điển hình | chromly |
|---|---|---|---|
| 1 | Parser / preparser (scope, PreparseData) | OOB, stack overflow | ● lfuzz-parser |
| 2 | Interpreter (Ignition) / bytecode | type confusion | ● fuzzilli |
| 3 | Baseline (Sparkplug) | frame/IC bugs | ● fuzzilli + diffopt axis |
| 4 | JIT: **Maglev** | type/representation confusion, range analysis | ● fuzzilli + diffopt |
| 5 | JIT: **Turbofan / Turboshaft / Turbolev** | load-elim, escape analysis, deopt | ● fuzzilli + diffopt |
| 6 | Inline caches / feedback vector | polymorphic IC bugs | ● fuzzilli |
| 7 | Builtins (Torque/CSA) | OOB, type confusion | ● fuzzilli |
| 8 | Runtime & objects | type confusion, UAF | ● fuzzilli |
| 9 | GC: scavenger / compact / **weak refs** / ephemerons | UAF, stale read (vd CASE-0003) | ● fuzzilli (+ audit n-day) |
| 10 | RegExp / irregexp (parse+compiler) | OOB, wrong capture | ○ engine sẵn (`regexp`) · calib 1 |
| 11 | **WebAssembly**: decoder/validator | OOB | ● lfuzz-wasm |
| 12 | Wasm: Liftoff / TurboFan-wasm | bounds-check miss, type confusion | ○ `wasm_compile*` · calib arch-lock |
| 13 | Wasm: GC / JSPI / memory64 / threads-shared | race, type confusion | ● fuzzilli (wasm-staging) |
| 14 | Wasm: streaming / async / fast-api / js-to-wasm | wrapper bugs | ○ `wasm_streaming/async` |
| 15 | **V8 sandbox**: heap sandbox, EPT/TPT/CPT, trusted space | sandbox bypass (giá trị cao) | ◐ variant đã chạm (TPT/CPT) |
| 16 | Code space / W^X / JIT code pages | W^X bypass → RWX | ✗ |
| 17 | Serializer / snapshot deserializer | context-deser bugs | ✗ (không fuzz trực tiếp) |
| 18 | Intl (ranh giới ICU) | bug ICU (C/C++) | ✗ |
| 19 | TypedArray/ArrayBuffer (resizable, detach race), SAB | race → OOB | ● fuzzilli |
| 20 | Embedder API (Blink dùng sai V8 API) | sandbox bug bậc cao | ◐ review |
| 21 | Inspector / debug (CDP, d8) | logic, OOB | ○ `inspector` · `json` |

Fuzzer/engine cho V8: **fuzzilli** (●), libFuzzer harnesses (○ 16 target), **Foozzie** (differential
correctness — bản đầy đủ của diffopt), jsfunfuzz. Meta: flag `--js-staging/--wasm-staging` = code mới = bug mới (đang bật).

## 2. Blink + renderer Web APIs (bug UAF nhiều nhất Chrome)

| Sub-surface | Bug class | chromly |
|---|---|---|
| HTML parser / DOM / editing | UAF, OOB | ✗ (cần Domato/FreeDom) |
| CSS parser / style / layout | OOB, logic | ✗ |
| Bindings IDL (V8 wrapper, wrapper world) | type confusion, UAF | ◐ review |
| Events / microtasks / postMessage / structured clone | UAF, logic | ✗ |
| Workers / ServiceWorker / Worklets | race, UAF | ✗ |
| Storage: IndexedDB (LevelDB), File System Access, quotas | UAF, logic | ✗ |
| Media: WebCodecs, MSE, WebAudio | OOB (codec), UAF | ✗ |
| Fonts / images (FreeType/HarfBuzz, png/webp/avif/jxl) | OOB | ✗ |
| Navigation API / portals / fenced frames / sandboxed iframes | site-isolation bypass | ✗ |
| WebGL/WebGPU (→ GPU process) | OOB, type confusion | ✗ (chromium hot: blink 82, gpu) |
| WebRTC / WebTransport / WebUSB / WebBluetooth / WebHID | logic, OOB | ✗ |

Fuzzer chuẩn: **Domato** (DOM grammar), FreeDom (stateful), WPT-based differential, libFuzzer
blink targets. → Đây là mảng lớn nhất chromly **chưa** chạm (◐ intel: blink 82 fix/90d).

## 3. Mojo IPC & multi-process (mặt trận sandbox-escape chính)

| Sub-surface | Bug class | chromly |
|---|---|---|
| Mojo serialization/deserialization (mọi interface) | OOB, type confusion, logic | ✗ (cần mojom fuzzers) |
| Browser process: navigation, site isolation, process swap, permissions | logic (escape) | ✗ |
| GPU process: **ANGLE** (GL), **Dawn** (WebGPU), Skia, command buffer | OOB, type confusion | ✗ |
| Network service: URLLoader, HTTP/2/3, **QUIC**, TLS, DNS, cookies | OOB, UAF | ✗ |
| Utility: data decoder (ảnh/audio/video/**PDFium**), printing | OOB | ✗ |
| Storage service: IndexedDB/DOM storage on disk | logic | ✗ |

Fuzzer chuẩn: **mojom fuzzers** (libFuzzer theo từng interface, chromium ~600 targets tổng),
MojoJS + `--enable-blink-features=MojoJS` để fuzz renderer→browser bằng JS.
→ chromly ◐ intel (sandbox-browser 53 fix/90d) — lab chrome để M5+.

## 4. OS sandbox escape (2) — ngoài mã Chrome

| Surface | Ghi chú |
|---|---|
| Linux: seccomp-bpf, namespaces, LSM | bug trong policy Chrome (VRP có nhận) |
| Windows: win32k, AppContainer, CSRSS, kernel drivers | kernel bug = ngoài VRP (báo MS) |
| macOS: seatbelt, XPC | |
| GPU drivers (NVIDIA/AMD/Intel) | sandbox escape giá trị cao |

## 5. Meta-surface — *cách* researcher tìm bug (không phải component)

1. **Feature mới / staging** (đằng sau flag, chrome://flags, origin trials) — code mới nhiều bug nhất.
2. **Patch-diff → variant** (n-day chưa fix ở nhánh khác; "fix 1 chỗ, sót 3 chỗ").
3. **Differential fuzzing** (V8: Foozzie opt/no-opt + flag matrix; wasm: so spec-interpreter).
4. **Grammar/stateful fuzzing** (fuzzilli cho JS, Domato cho DOM, grammar cho wasm).
5. **Custom harness per-target** (libFuzzer cho parser/codec; mojom cho IPC; harness viết tay cho subsystem mới).
6. **Corpus từ upstream** (regression tests, clusterfuzz cases, WPT) — vd audit lane của chromly.
7. **Soát ngữ nghĩa spec** (logic bug — không cần memory corruption; site-isolation là ví dụ).

## 6. chromly vs bản đồ (tổng)

- **Đang phủ (●)**: V8 full (fuzzilli), parser, wasm module, JIT diff (diffopt), variant/audit từ upstream
  (patch-diff 90d), ToT verify, calibration 5 surface.
- **Sẵn sàng 1 lệnh (○)**: 16 libFuzzer harness (regexp, wasm_compile*, streaming, inspector, json…),
  3 fuzzilli profile khác (v8Sandbox/v8Dumpling/v8holefuzzing).
- **Chỉ intel (◐)**: Blink, sandbox-browser, gpu, network (review/variant trên diff — không fuzz).
- **Chưa có (✗)**: Blink/DOM fuzzing (Domato), Mojo/mojom fuzzing, GPU (ANGLE/Dawn), network stack
  (QUIC), codec/PDFium, V8 code-space/W^X, snapshot-deser, Intl/ICU.

**Đường mở rộng hợp lý (theo giá trị/chi phí)**: ① thêm harness wasm (○→●) khi rảnh CPU ·
② Domato-lite cho Blink (JS-level DOM fuzzing qua d8? cần chrome) · ③ mojom fuzzers chọn lọc
(serialization) · ④ research harness cho V8 sandbox/code-space khi có substrate exploit.
