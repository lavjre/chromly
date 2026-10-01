# M5-03 — L1 primitive: addrof/fakeobj (ladder rung 1)

**Status:** todo (đang tìm substrate)
**Deliverable:** trên ≥1 bug thật (calibration hoặc audit), một PoC chạy bằng d8 đạt:
- `addrof(obj)` — đọc được địa chỉ (compressed) của object kiểm soát được, hoặc
- `fakeobj(bits)` — tạo được reference tới vùng nhớ kiểm soát,
- đo reliability bằng `chromly exploit verify --runs 200` ≥95%, có bản ghi "build fixed
  không còn primitive" (đối chiếu 2 build).

**Hiện trạng (2026-10-01) — đã khảo sát hết ứng viên, CHƯA có substrate:**
| bug | lớp | kết quả L0 |
|---|---|---|
| calib-567129324 | maglev weaker-check → oddball lọt Smi-field | leak HẰNG SỐ (tag oddball >>1); store chặn HeapNumber ("not a Smi"); wild deref địa chỉ hằng → **không đủ L1** |
| calib-567177599 | turbolev peeling phi type | representation-only, consumers đều checked |
| calib-539984773 | StringAt OOB (ThinString) | revert drift — không tái hiện |
| audit-567538973 (weak refs) | stale read, ASAN SEGV | fault = near-null trong cage (offset 0x5bf), token chết → không kênh kiểm soát → **crash-only** |
| audit-563882510 / 563068683 / 567126756 | deopt frame / wasm align / SFI GetCode | check-only, không điều khiển được |

**Phương pháp tìm substrate (theo thứ tự ưu tiên):**
1. **Audit loop (M2-07)** — delta mirror tiến từng ngày; bug có-sẵn-trong-cây, không drift.
   Tiêu chí chọn: class `type confusion` (object↔double/pointer), OOB write có index kiểm soát,
   UAF có kênh dữ liệu ra JS.
2. Cửa sổ trước checkout (drift ≤3 ngày) với revert — chỉ khi (1) không có gì.
3. Đào sâu thêm trên 567129324 nếu tìm được consumer UNCHECKED mới
   (hướng: `GetTruncatedInt32ForToNumber` với assumed_input_type kSmi; reuse alternative).
**Khi có substrate:** theo skill `exploit-primitive` — L1 → verifier ×200 → notes.md
(`hypothesis | evidence | result`) trong `calibration/exploits/<bug>/`.
**Files (dự kiến):** `calibration/exploits/<bug-id>/poc-l1-*.js`, `notes.md`, `acceptance/M5-l1.sh`
**Acceptance:** `bash acceptance/M5-l1.sh` → verifier ≥95% ×200 trên build bug; 0% trên build fixed.
**Phụ thuộc:** M5-01 (verifier) · M5-02 (lab) · M2-07 (audit loop).
