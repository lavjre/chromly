# ADR-012 — ToT verify: build mới nhất để xác nhận "unfixed"

**Trạng thái:** Accepted · **Ngày:** 2026-10-01 · **Milestone:** M5 (M5-04) · **Supersedes:** —

## Bối cảnh

Chuẩn researcher cho 1 claim 0day: repro phải chạy trên ToT/latest release. chromly trước đây
chỉ có build của snapshot (b8ffaab, 2026-09-28) — mọi find là n-day/FP mà không có cách nào
khẳng định "còn sống". Mirror (M2-01) giữ ToT (FETCH_HEAD, lag ~0.6h) nhưng không có build.

## Quyết định

- **Build ToT trong chính cây checkout**, điều khiển bằng `chromly tot build`:
  gclient sync `--revision v8@<ToT sha>` → build `out/tot` (config `tot.gn` = asan + dcheck +
  verify_heap, giống calib) → **revert snapshot** (kể cả khi build fail); state `store/tot.json`.
- **Không tạo cây thứ hai / không symlink deps**: cây đầy đủ + gclient sẵn có; deps drift
  giữa các rev trong vài ngày chấp nhận được, revert tự động. (Lý do loại: mirror là
  blob:none partial clone, thiếu deps; worktree không có third_party.)
- **Verify**: `chromly tot verify <file|crash_hash> [--flags ...]` chạy repro trên `out/tot/d8`,
  kết luận `STILL-CRASHES` (exit 0) / `CLEAN` (exit 2); log + `store/tot/verifications.jsonl`.
  Case mission tự chèn đường dẫn ToT khi sẵn sàng.
- **Nhịp**: thủ công/on-demand + trước khi claim report (refresh ~vài ngày/lần). Không đưa
  vào aux loop vì build nặng, tranh CPU với farm.

## Hệ quả

+ Từ giờ mọi find có bước xác nhận chuẩn mực; phân biệt rõ n-day (CLEAN trên ToT) vs
  candidate 0day (STILL-CRASHES). `chromly info` hiển thị dòng TOT.
− Trong lúc build ToT (~1–2h), cây tạm ở rev ToT (các lane khác dùng binary nên không ảnh
  hưởng; case agent đọc source nên cần tránh kết luận nhầm về source trong cửa sổ này —
  revert tự động khép cửa sổ).
− Deps có thể bị gclient kéo lên rev mới hơn; revert về snapshot sync lại — chấp nhận.

## Phương án đã loại

- Cây thứ hai bằng gclient (~10GB + sync lâu) — đắt, không cần cho verify thủ công.
- Symlink deps vào mirror — giòn, nhiều vòng lặp gn gen.
- Tự động verify mọi crash trong triage — repro cần đúng flags theo build gốc; làm ở
  case/mission (có context) trước, tự động hoá khi đã đủ dữ liệu.
