# M1-01 — Fuzzilli toolchain + `out/fuzzilli` (d8 REPRL)

**Status:** done
**Deliverable:** Swift toolchain (swiftly, latest stable) · fuzzilli `swift build -c release` (pin commit 281729bf) · build rig thêm config `fuzzilli` → `out/fuzzilli/d8` với args từ `Targets/V8/fuzzbuild.sh`: `is_debug=false · dcheck_always_on=true · v8_static_library=true · v8_enable_verify_heap=true · v8_enable_partition_alloc=false · v8_fuzzilli=true · sanitizer_coverage_flags="trace-pc-guard" · target_cpu="x64"` (+ use_lld). Node: V8 checkout hiện tại (b8ffaab, V8 15.7.0) — fuzzilli REVISION là 99071b00 (cách ~vài ngày); build trên rev hiện tại trước, lệch hành vi thì fallback sync về 99071b00.
**Files:** `chromly/builds/args/fuzzilli.gn`, `chromly/builds/args.py`, `tests/test_builds.py`, `acceptance/M1-fuzzilli.sh`, `docs/fuzzilli-notes.md`
**Acceptance:** `bash acceptance/M1-fuzzilli.sh` → `swift --version` ok; FuzzilliCli binary tồn tại; `out/fuzzilli/d8` chạy REPRL smoke với FuzzilliCli ≥60s không lỗi, execs/s > 0 (log lại).
**Evidence:** version strings + smoke output (execs count, coverage) + build record.
**Out of scope:** farm multi-instance (M1-02).
**Phụ thuộc:** — (build rig M0-04 đã xong).
