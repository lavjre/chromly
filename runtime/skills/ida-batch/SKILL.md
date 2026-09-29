---
name: IDA Batch
description: Pattern dùng IDA MCP (ida.*) cho disasm/decompile/xrefs/patch trên d8/chrome — tra ida.reference trước mọi API ida-domain.
---

# IDA batch — pattern dùng `ida.*` MCP

Một phiên IDA nặng/lúc (RAM). Xong việc luôn close. Không mở GUI trong container —
cần GUI thì dùng fallback http mode trên VM (§5.8).

## Workflow

1. `ida.list_databases` — nắm DB đang mở + instance ids; tránh mở trùng.
2. `ida.open_database` với binary cần xem:
   - d8 của build tương ứng: `out/asan/d8` / `out/release/d8`;
   - hoặc `.i64` sẵn trong `/case/ida/`;
   - ghi lại `instance_id` trả về.
3. Trước mọi đoạn IDAPython: **tra `ida.reference`** để tìm API ida-domain — không đoán tên hàm.
4. `ida.execute_python` cho việc thật:
   - crash-site: disasm quanh địa chỉ (map từ `symbols.txt`), đối chiếu source V8;
   - xrefs / callers / callees của function nghi vấn;
   - decompile Hex-Rays function nghi vấn;
   - diff hàm trước/sau fix: **mở từng DB một** (serialize), lấy decompile, so bằng mắt, ghi notes;
   - gadget hunting (M6+);
   - patch thử: ghi rõ patch gì, vì sao; không patch trên bản duy nhất.
5. `ida.save_database` nếu có rename/comment/patch đáng giữ.
6. `ida.close_database` — nhả lease; nếu là lease cuối thì chờ shutdown sạch.

## Ghi kết quả

- Finding (address · hàm · nhận xét ngắn) → `/case/notes.md`, mục `## IDA`.
- Pseudocode dài: trích ≤40 dòng đoạn quyết định + đường dẫn — không dán cả hàm.

## Lỗi thường gặp

- `instance busy` → phiên khác đang giữ: chờ, hoặc báo supervisor để serialize.
- License fail trong container → ghi HELP; fallback http mode theo §5.8.
- Auto-analysis chậm với binary lớn → chấp nhận; không kill giữa chừng (state hỏng).
