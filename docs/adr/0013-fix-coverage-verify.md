# ADR-013 — Fix-coverage verify trước mọi claim "0day"

- Status: accepted (2026-10-09)
- Liên quan: ADR-012 (ToT verify)

## Vấn đề

Pipeline coi "crash còn sống trên ToT build" = unfixed. Nhưng ToT build có thể **cũ hơn commit
fix upstream** — crash trên ToT chỉ chứng minh bug sống ở rev đó, không chứng minh unfixed trên
main.

Ca thật (09/10): family Maglev (CASE-0020/0022 + sibling hunt t15/e2b, 15 biến thể) sống trên
ToT build Oct 2, nhưng fix upstream `6c626cef36` landed **Oct 7** → cả family là n-day. Suýt
viết report VRP cho bug đã fix (case 0020 verdict ghi "Next: report-draft" trước khi có bước này).

## Quyết định

Trước mọi report-draft / claim "0day": chạy **fix-coverage test** (`tools/fixcheck.sh`):

1. Apply patch commit fix (chỉ `src/*`) từ mirror lên snapshot tree.
2. Rebuild build đích (`out/release`).
3. Chạy lại: repro của candidate + regression test của chính fix (nếu có).
4. Kết luận:
   - **clean** trên build có fix (+ regression test pass) → **covered** → n-day, đóng case,
     không report.
   - **vẫn crash** → **surviving** → candidate thật, đủ điều kiện report-draft.
5. Revert + rebuild lại build gốc — tự động trong script (trap EXIT, kể cả khi lỗi).

Contrast tối thiểu: chạy regression test của fix trên build chưa patch (tot) — phải crash, xác
nhận test có hiệu lực và patch thật sự sửa.

## Hệ quả

- "STILL-CRASHES trên ToT" giữ nghĩa hẹp: sống trên ToT rev — bước sàng, **không phải** bằng
  chứng unfixed.
- Muốn biết upstream đã fix chưa: kiểm tra mirror (`git log --since=... -- <path>`) rồi
  fix-coverage.
- Chi phí: rebuild ~1h lần đầu (siso 1235 step), revert-rebuild ~1m30s (cache ấm). Chạy tiết
  kiệm — chỉ cho candidate đã đủ chín.

## Evidence 09/10 (maglev family)

- Patched release: `t15` clean · `e2b` clean · `0020` clean · `0022` clean ·
  `regress-569286602-1/2` pass.
- Unpatched: `regress-1` CHECK `predecessor_count(offset)==0 (1 vs 0)` :17238 (release + tot);
  `regress-2` DCHECK `predecessors_so_far==predecessor_count (1 vs 2)` :16982 (tot);
  `t15` SEGV 0x30 release 3/3.
- Kết luận: family covered bởi `6c626cef36` (Oct 7) → n-day; case 0020/0022 đóng.
