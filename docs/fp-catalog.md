# FP catalog — các lớp false-positive đã đập + known-defence

Mục đích: **không re-learn**. Khi crash/diff "trông giống" một mục ở đây → kiểm tra filter
tương ứng trước khi tốn case. Cập nhật mỗi lần đập lớp FP mới (kèm ngày + nơi enforce).

## 1. Lớp FP theo lane

| # | Lớp | Dấu hiệu | Enforce | Ngày |
|---|---|---|---|---|
| 1 | flag-conflict | `Flag processing error` / `Contradictory value for readonly flag` | variants.FLAG_CONFLICT_MARKERS | 09/10 |
| 2 | fp-manual-opt | `CheckMarkedForManualOptimization` (%Optimize* thiếu %Prepare*) | variants.MANUAL_OPT_FP_MARKERS + `_ensure_manual_opt_prepared` | 05/10 |
| 3 | oom | `Fatal JavaScript out of memory` / `CALL_AND_RETRY_LAST` | OOM_MARKERS (variants · diffopt) | 02/10 |
| 4 | async-worker race | Worker in lỗi N lần khác nhau giữa các lần chạy | diffopt `_dedupe_blocks` + confirm 6×/bên | 02/10 |
| 5 | stack-depth (#7) | 1 bên `Maximum call stack size exceeded`, bên kia không — frame size khác giữa tier JIT | diffopt `_config_noise_fp` | 11/10 |
| 6 | worker-output (#8) | Program `new Worker`, 1 bên in uncaught-error vs trống — tốc độ compile quyết định | diffopt `_config_noise_fp` | 11/10 |
| 7 | harness frames | Stack trong `test/fuzzer/*` (fuzzer.cc) | triage `score.py` (`harness-related −3`) | 08/10 |
| 8 | fuzzilli output noise | Output chứa "Fuzzer output channel not available" — vô hại, không phải fault | `score.py` (chỉ phạt frame test/fuzzer, bỏ substring) | 08/10 |
| 9 | test-API-only | Cần `%`-intrinsics / d8 API / mjsunit harness (`%RuntimeEvaluateREPL`) — không web | S1 `reachable` + case verdict | 08/10 |
| 10 | d8 worker teardown race | CASE-0027: print/throw khác nhau khi main thoát trước worker | case-level (verdict no-bug) | 10/10 |
| 11 | flag-only robustness | CASE-0017: flag UB (shift ≥32) → abort; không memory primitive | case-level (verdict, không report) | 08/10 |
| 12 | stack-overflow thuần | `RangeError: Maximum call stack size exceeded` không kèm corruption | case-level (DoS; không ưu tiên) | — |

## 2. Known-defence (target-side — hạ ưu tiên khi gặp)

- **dcheck-only**: abort chỉ trên build dcheck (calib/tot/fuzzilli); release không có check →
  cần chứng minh **release impact** mới có giá trị (vd lớp write-barrier: release im lặng =
  UAF tiềm năng — mới đáng đào).
- **flag-gated**: cần flag experimental/default-off (`--turbolev`, `--array-destructure-bytecode`,
  `--max-maglev-hard-inline-depth`...) → không reachable từ web content.
- **natives / test-API**: `%`-intrinsics, `d8.serializer`, mjsunit harness → không web.
- **fuzzilli-build-only**: chỉ nổ trên `out/fuzzilli` (v8_fuzzilli, partition_alloc off,
  verify_heap) — timing artifact; asan/release/calib sạch (vd CSA_DCHECK cluster).
- **fixed-upstream**: chạy fix-coverage (ADR-013) trước mọi claim; "sống trên ToT" ≠ unfixed
  khi ToT cũ hơn fix.
- **V8 sandbox**: renderer memory corruption cần thêm sandbox escape cho full chain — VRP tách
  hai hạng mục; đừng gọi "RCE" khi chưa có cả hai.

## 3. Quy trình khi gặp FP mới

1. Xác định dấu hiệu ổn định (marker text / cấu trúc diff / điều kiện config).
2. Thêm filter ở lane tương ứng + unit test nhỏ.
3. Mark crash cũ trong DB `state='fp'`.
4. Ghi vào bảng §1 (kèm ngày + nơi enforce).
