# ADR-011 — libFuzzer engine mode: re-link từ ninja per-target + vendor source (không patch V8)

**Trạng thái:** Accepted · **Ngày:** 2026-10-01 · **Milestone:** M1 (M1-08) · **Supersedes:** [010](0010-libfuzzer-engine-defer.md) — phần hoãn engine sang v2

## Bối cảnh

ADR-010 hoãn engine mode vì standalone V8 không link libFuzzer: `v8_simple_*_fuzzer` chỉ là one-shot runner, còn `//testing/libfuzzer` (chromium) không tồn tại trong checkout. Trước M5 (ladder exploit) cần lane coverage-guided thật — corpus tĩnh replay không sinh test mới.

Khảo sát lại hiện trường (kết quả thay đổi quyết định):

- `use_libfuzzer=true` **đã** bật `-fsanitize=fuzzer-no-link` cho mọi object `out/libfuzzer` — coverage instrumentation có sẵn, chỉ thiếu runtime main + mutator.
- Mỗi target có ninja file `out/libfuzzer/obj/v8_simple_<f>_fuzzer.ninja` chứa **toàn bộ** inputs + `ldflags/libs/rlibs/solibs` của link edge → đủ dữ kiện re-link ngoài GN.
- clang bundle 24 không có archive fuzzer; archive compiler-rt hệ thống (clang-21) lệch ABI: libstdc++ (`__cxx11`) + glibc mới (`__isoc23_strtoul`, `pthread_*@GLIBC_2.34`) không khớp sysroot bullseye của V8.

## Quyết định

1. **Không patch nguồn V8, không shim GN.** Engine = re-link từ metadata ninja: bỏ object main one-shot (`obj/v8_simple_<f>_fuzzer/fuzzer.o`), link thêm libFuzzer runtime.
2. **Vendor source libFuzzer** (`third_party/libfuzzer/`, llvmorg-21.1.0 `compiler-rt/lib/fuzzer`; loại `FuzzerInterceptors.cpp` vì ASAN đã có interceptor riêng), compile bằng đúng toolchain V8 (clang 24 bundled + libc++ headers `third_party/libc++/src` + sysroot bullseye) → `build/libfuzzer/libFuzzer.a`. ABI khớp tuyệt đối; tái lập offline.
3. Binary engine `out/libfuzzer/v8_engine_{parser,wasm_module}_fuzzer`; wrapper `chromly fuzz lfuzz --unit lfuzz-{parser,wasm}` — loop cycle `-max_total_time=600`, artifact về `store/fuzz/<unit>/artifacts/` (ingest sẵn có).
4. Farm mặc định = fuzzilli + 2 engine units (`engine_units()`). Replay M1-03 v0 giữ làm fallback (`chromly fuzz lfreplay`), không thuộc default.
5. **Target-agnostic (custom harness per-target):** mọi `v8_simple_<t>_fuzzer` có trong `out/libfuzzer` đều dùng được — `chromly fuzz engine --list` (16 target đang có) · `--build --fuzzer <t>` · `lfuzz --unit lfuzz-<t>`. 2 lane parser/wasm là default; target mới chỉ cần build + trỏ unit (không cần động vào code).

## Hệ quả

+ Mutation + coverage-guided thật: parser ~300–330 exec/s/unit, wasm ~750–840 exec/s/unit; corpus tự mọc; crash → artifact `crash-*`/`oom-*` → crash store.
+ Zero đụng build system V8 — calibration revert vẫn sạch. Re-link engine ≈ 5–20s; build archive ≈ 22s.
− Thêm bước build phụ `chromly fuzz engine --build` sau khi đổi cấu hình `out/libfuzzer`.
− Phụ thuộc layout ninja của GN (snapshot đã pin); V8 đổi tên target phải cập nhật `LFUZZ_UNITS`.

## Phương án đã loại

- **Shim `//testing/libfuzzer` + import vào graph GN** (hướng cũ của ADR-010): đụng source/graph V8, bảo trì đắt — không còn cần thiết.
- **Archive compiler-rt hệ thống**: lệch ABI (thực nghiệm ra `__isoc23_strtoul` undefined + shlib glibc 2.34).
