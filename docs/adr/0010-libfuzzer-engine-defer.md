# ADR-010 — libFuzzer engine mode: chấp nhận replay v0, engine để v2

**Trạng thái:** Superseded by [ADR-011](0011-libfuzzer-engine-relink.md) (2026-10-01 — engine mode hoàn thành qua re-link ninja, không cần shim) · **Ngày:** 2026-09-30 · **Milestone:** M1 (M1-03/M1-08)

## Bối cảnh

M1-03 cần lane libFuzzer (parser/wasm). Thực tế: **standalone V8 không link engine libFuzzer** — `use_libfuzzer=true` chỉ thêm `-fsanitize=fuzzer-no-link` (coverage); engine main đến từ `//testing/libfuzzer` của Chromium (không tồn tại trong checkout V8). Vì vậy `v8_simple_*_fuzzer` là **one-shot runner** (nhận danh sách file), không mutate. Muốn engine thật phải: (a) chặn `main()` trong `test/fuzzer/fuzzer.cc` rồi link compiler-rt fuzzer, hoặc (b) shim `testing/libfuzzer/BUILD.gn`, hoặc (c) vendor script oss-fuzz. Cả ba đều ĐỤNG build system của V8 (checkout patch / target shim) — cần quyết định trước khi làm.

## Quyết định

- **v0 (đang chạy):** replay wrapper `chromly fuzz lfreplay` — batch corpus qua simple runner, bắt crash; giữ lane "memory-safety nhanh" ở mức phát hiện trên corpus tĩnh + seed mjsunit.
- **Engine mode:** task M1-08 giữ mở, **hướng đã chốt = shim (b)**: thêm `testing/libfuzzer/BUILD.gn` tối giản (không patch nguồn V8) + guard main nếu cần; kích hoạt ở **v2** (before M8 soak) khi cần coverage-guided lane thứ hai.

## Phương án đã loại

- **Patch `fuzzer.cc` (a)** — đụng source V8, lệch mỗi lần sync/revert calibration; bảo trì đắt.
- **Vendor oss-fuzz scripts (c)** — nặng, kéo cả infra Google; không xứng giá trị ở v0.

## Hệ quả

+ Không đụng build system V8 (calibration revert sạch); replay vẫn bắt crash trên corpus; fuzzilli là mutator chính (đủ cho M1 acceptance ≥300/s).
− Chưa có coverage-guided libFuzzer (khác biệt chính so với oss-fuzz); replay phụ thuộc corpus cập nhật. Giảm thiểu: revisit ở v2 theo trigger "V8 track chín"; khi đó implement shim + đo lại.
