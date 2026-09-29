# M1-08 — libFuzzer engine mode (follow-up, cần ADR)

**Status:** todo
**Deliverable:** link được engine libFuzzer (`LLVMFuzzerRunDriver`) cho `v8_simple_*_fuzzer` trên standalone V8 — hiện thiếu `//testing/libfuzzer` (chromium) nên binary chỉ là one-shot runner (xem M1-03 v0). Hướng: (a) build với `$LIB_FUZZING_ENGINE` kiểu oss-fuzz (clang `-fsanitize=fuzzer` ở link + loại main của fuzzer.cc), hoặc (b) thêm target no-main. Kèm: đổi `chromly fuzz lfreplay` sang engine mode (`-max_len`, `-rss_limit_mb`, artifact prefix thật).
**Files:** `infra/` (script build) hoặc `chromly/builds/` + ADR mới.
**Acceptance:** engine chạy mutation thật (`-runs=1000`, corpus tăng coverage); wrapper `libfuzzer-parser` dùng engine.
**Phụ thuộc:** ADR (G4) — dependency/wiring mới.
