# M1-03 — libFuzzer wrappers (×2: parser · wasm)

**Status:** done
**Deliverable:** build rig config `libfuzzer` → `out/libfuzzer` target `v8_fuzzers` (✓ engine verify); 2 runner v0: replay wrapper `chromly fuzz lfreplay` (batch run corpus qua `v8_simple_*_fuzzer`, bắt crash → artifacts) — **lưu ý: V8 standalone KHÔNG link engine libFuzzer** (thiếu `//testing/libfuzzer` của chromium) nên binary là one-shot runner; **engine thật đã xong ở M1-08** (ADR-011: re-link + vendor source) — replay nay là fallback lane, farm mặc định dùng `lfuzz-*`. Corpus: parser seed từ mjsunit (200 file); wasm kế thừa corpus replay.
**Files:** `chromly/builds/args/libfuzzer.gn`, `chromly/fuzz/replay.py`, `chromly/fuzz/farm.py`, `acceptance/M1-libfuzzer.sh`
**Acceptance:** `bash acceptance/M1-libfuzzer.sh` → build xong ≥2 binary; farm up: 2 wrapper alive, parser log `files>0` (replay thật); down sạch.
**Evidence:** binary list + log replay.
**Out of scope:** engine mutation mode (M1-08 — ADR) · corpus cull (M1-06).
**Phụ thuộc:** M1-02.
