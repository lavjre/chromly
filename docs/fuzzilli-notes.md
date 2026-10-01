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

- `--jobs=4` = 1 main + 3 thread workers **trong 1 process** (ThreadSync, corpus sync full) — phù hợp 8 vCPU; watchdog restart theo process (M1-04).
- Crash rơi vào `storagePath/crashes/`: mỗi crash = **cặp `.js` (lift JS, ghi TRƯỚC) + `.fzil` (protobuf, ghi SAU)** — nguồn: `Storage.swift::storeProgram` (không phụ thuộc cờ); crash store (M1-05) nhập `.fzil` canonical + `.js` sidecar, và nhập `.js` mồ côi nếu fuzzilli thoát giữa chừng (chỉ có .js).
- `--exportStatistics` ghi stats định kỳ vào storage — nguồn metrics v0 (M1-07).
- Multi-machine (sau này): instance tree `root`/`leaf` + `--bindTo`/`--connectTo` (`--corpusSyncMode`).
