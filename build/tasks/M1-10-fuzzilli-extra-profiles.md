# M1-10 — Fuzzilli extra profiles (v8Sandbox · v8holefuzzing · v8Dumpling)

**Status:** todo — cần **build d8 riêng cho từng profile** (bằng chứng bên dưới, 2026-10-04).
**Vì sao:** surface report: sandbox-escape là hạng mục giá trị cao (V8 sandbox: EPT/TPT/CPT);
hole-fuzzing nhắm lớp in-object holes; dumpling = differential frame Maglev↔Turbofan (bổ trợ diffopt).

## Bằng chứng thử nghiệm (d8 fuzzbuild hiện tại — profiles/V8/fuzzbuild.sh)

| profile | kết quả | lỗi |
|---|---|---|
| `v8Sandbox` | ✗ Signal 6 lúc startup | cần build sandbox (`v8_enable_sandbox=true` + `v8_enable_partition_alloc=true`; hiện PA=**false** theo fuzzbuild chuẩn nên sandbox tắt; `--sandbox-fuzzing` flag có nhưng môi trường sandbox API không dựng đủ) |
| `v8holefuzzing` | ✗ Signal 6 lúc startup | profile truyền `--hole-fuzzing` — flag tồn tại nhưng harness hole cần build hỗ trợ (đối chiếu `Targets/V8/` build config của fuzzilli cho hole-fuzzing) |
| `v8Dumpling` | ✗ Signal 4 (fatal) | `Fuzzer.swift:1404 Unable to read dump files: /tmp/.../optimizedDump/output_dump_0.txt does not exist` — cần d8 **dumpling-mode** (ghi frame dumps; xem `RelateTool` trong fuzzilli) |

## Deliverable

1. Thêm 3 build config (`chromly/builds/args/`):
   - `fuzzilli-sandbox.gn`: theo fuzzilli `Targets/V8/fuzzbuild.sh` + `v8_enable_sandbox=true`,
     `v8_enable_partition_alloc=true`, `v8_enable_pointer_compression=true` (đối chiếu README fuzzilli mục V8 sandbox).
   - `fuzzilli-hole.gn`: theo build config hole-fuzzing của fuzzilli (kiểm tra `Targets/V8/` cho biến thể).
   - `fuzzilli-dumpling.gn`: build có frame-dump/dumpling support (đọc `RelayTool`/docs fuzzilli).
2. Lanes mới trong farm: `fuzzilli-sandbox` (profile=v8Sandbox), `fuzzilli-hole`, `fuzzilli-dumpling`
   — mỗi cái storage riêng; CPU: chạy 1–2 lane tuỳ tải (cân nhắc đưa vào rotator như engine lanes).
3. Smoke: mỗi profile chạy `--maxRuntime=60s` không fail startup; corpus tăng; crash rơi vào
   `storagePath/crashes` → ingest như thường.
4. Đo: exec/s, surface coverage mới (sandbox API / hole corruption / frame-diff mismatches).

## Chi phí

- Mỗi build d8 dcheck ~1–2h trên box (8 vCPU, tranh tải với farm) + ~5–10GB disk/build.
- Chạy thêm 3 fuzzilli process: ~1–2GB RAM mỗi cái (jobs=2).
- **Thứ tự ưu tiên**: `sandbox` > `dumpling` > `hole` (theo giá trị surface/90d + độ bổ trợ diffopt).

**Phụ thuộc:** fuzzilli commit 281729bf (đang dùng) · out/fuzzilli hiện tại giữ nguyên cho lane chính.
