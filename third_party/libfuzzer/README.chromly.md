# libFuzzer (vendored) — nguồn & lý do

Nguồn: `llvm-project` @ tag `llvmorg-21.1.0`, thư mục `compiler-rt/lib/fuzzer/`
(fetch bằng raw.githubusercontent.com; xem `chromly/fuzz/engine.py::ensure_fuzzer_archive`).

Vì sao vendor thay vì dùng `libclang_rt.fuzzer-*.a` của hệ thống:

- clang bundle 24 của V8 **không kèm** archive fuzzer.
- archive compiler-rt hệ thống (clang-21 Ubuntu) build bằng **libstdc++** + glibc mới
  (`__cxx11`, `__isoc23_strtoul`, `pthread_*@GLIBC_2.34`) → không link được với binary
  V8 (libc++ + sysroot bullseye) — đã thực nghiệm fail.

Cách dùng: `chromly fuzz engine --build` → compile các `Fuzzer*.cpp` (trừ
`FuzzerInterceptors.cpp` — ASAN đã có interceptor riêng) bằng đúng toolchain V8
(`--target=x86_64-unknown-linux-gnu`, `-nostdinc++ -isystem third_party/libc++/src/include`,
`--sysroot=build/linux/debian_bullseye_amd64-sysroot`) → `build/libfuzzer/libFuzzer.a`;
sau đó re-link engine binary từ metadata ninja per-target (`out/libfuzzer/obj/v8_simple_*.ninja`).

License: Apache-2.0 WITH LLVM-exception (xem `LICENSE.TXT`).
