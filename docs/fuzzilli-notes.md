# Fuzzilli — ghi chú vận hành (M1-01)

## Thành phần

- **Swift**: swiftly, toolchain **6.4.0** (`~/.local/share/swiftly/bin` — đã thêm vào `~/.bashrc`; script tự export).
- **Fuzzilli**: `~/tools/fuzzilli` — pin commit `281729bf` (2026-09-24, main lúc cài). Build: `swift build -c release` → `.build/release/FuzzilliCli`.
- **d8 target**: `out/fuzzilli/d8` — config `chromly/builds/args/fuzzilli.gn`, theo `fuzzilli/Targets/V8/fuzzbuild.sh`:
  `is_debug=false · dcheck_always_on=true · v8_static_library=true · v8_enable_verify_heap=true · v8_enable_partition_alloc=false · v8_fuzzilli=true · sanitizer_coverage_flags="trace-pc-guard" · target_cpu="x64"`.
- **Không cần patch V8**: `v8_fuzzilli` có sẵn upstream (BUILD.gn); `Targets/V8/Patches/` rỗng ở bản này.
- V8 rev build: `b8ffaab0` (V8 15.7.0) — fuzzilli REVISION ghi `99071b00` (lệch vài ngày; theo dõi nếu có bất thường coverage/REPRL).

## Lệnh

```bash
export PATH="$HOME/.local/share/swiftly/bin:$PATH"

# chạy tay 1 instance
~/tools/fuzzilli/.build/release/FuzzilliCli --profile=v8 --jobs=4 \
  --storagePath=store/fuzz/fuzzilli --exportStatistics --statisticsExportInterval=1 \
  ~/v8/v8/out/fuzzilli/d8

# qua supervisor
.venv/bin/chromly build --config fuzzilli   # build/rebuild d8
.venv/bin/chromly fuzz up|status|down|watchdog|ingest|metrics
```

## Ghi chú thiết kế

- `--jobs=6` (từ 2026-10-01; env `CHROMLY_FUZZILLI_JOBS` để đổi) = 1 main + 5 thread workers **trong 1 process** (ThreadSync, corpus sync full). Lý do: đo thực tế 0.73 core cho 4 worker — worker bị chặn bởi respawn (timeout 6-8% × kill+spawn ~160ms) chứ không CPU-bound; tăng worker tận dụng phần chờ. Kết quả đo sustained: **~40/s → ~53/s (đỉnh 70–110/s)**; tăng không tuyến tính vì main-thread sync/corpus lớn dần. `maxExecsBeforeRespawn=1000` (profile) nên respawn định kỳ không đáng kể — churn chủ yếu từ timeout.
- REPRL per-exec thật (đo bằng `REPRLRun :load`): p50 ≈ 17ms, p90 ≈ 28ms với corpus program (build fuzzilli dcheck) — nếu exec/s thấp hơn nhiều so với 6/0.02s thì kiểm tra respawn/timeout trước khi nghi máy.
- `--verify-heap` mặc định **OFF** (fuzzbuild chỉ bật capability; fuzzilli không truyền flag này) — đừng đổ lỗi throughput cho verify-heap.
- Crash rơi vào `storagePath/crashes/`: mỗi crash = **cặp `.js` (lift JS, ghi TRƯỚC) + `.fzil` (protobuf, ghi SAU)** — nguồn: `Storage.swift::storeProgram` (không phụ thuộc cờ); crash store (M1-05) nhập `.fzil` canonical + `.js` sidecar, và nhập `.js` mồ côi nếu fuzzilli thoát giữa chừng (chỉ có .js).
- `--exportStatistics` ghi stats định kỳ vào storage — nguồn metrics v0 (M1-07).
- Multi-machine (sau này): instance tree `root`/`leaf` + `--bindTo`/`--connectTo` (`--corpusSyncMode`).

## Sự cố & bài học (2026-10-04)

- **Crash-loop "Corpus import aborted"**: nếu import abort lặp lại nhiều lần (mỗi restart lại abort),
  kiểm tra `storagePath/old_corpus` **đã tồn tại** chưa — fuzzilli rename corpus→old_corpus khi abort,
  gặp dir đích đã có là kẹt vòng. Fix: tự tay `mv corpus corpus.bad-<ts>; mv old_corpus old_corpus.bad-<ts>`
  rồi để watchdog restart (fuzzilli sinh corpus mới; corpus cũ giữ lại để mổ sau).
- **SIGKILL fuzzilli giữa chừng** có thể để lại `.fzil` viết dở trong corpus → lần resume sau đó import
  abort. Ưu tiên `farm.down()` (SIGTERM + grace) hơn kill -9 khi cần restart fuzzilli.
- **state.json race**: nhiều process (watchdog/up/down/lanes) cùng read-modify-write → record bị clobber.
  Đã vá: flock + merge-write (farm.state_lock, merge_unit_fields/merge_aux_record) + rotator re-assert
  record khi process còn sống mà record mất. Watchdog cũ cần restart 1 lần để nạp bản mới.
