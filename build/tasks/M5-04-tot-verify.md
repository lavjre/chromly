# M5-04 — ToT verify: xác nhận "còn sống" trên upstream mới nhất (chuẩn 0day)

**Status:** done (2026-10-01) — build ToT đầu tiên đang chạy, xem `store/tot.json`
**Vì sao:** mọi find trên snapshot (b8ffaab, 2026-09-28) không thể gọi "0day" nếu không biết
còn sống ở ToT hay không. Trước task này, **không có build nào mới hơn snapshot** — mọi
kết luận "unfixed" là bất khả.
**Deliverable:**
- `chromly tot build [--sha X]` — sync cây chính lên ToT (mặc định mirror FETCH_HEAD) →
  build `out/tot` (config `tot.gn`: asan + dcheck + verify_heap) → **revert snapshot**;
  state `store/tot.json`.
- `chromly tot status` — sha/age/d8.
- `chromly tot verify <file.js|crash_hash> [--flags '...']` — chạy repro trên `out/tot/d8`
  → `STILL-CRASHES` (exit 0) / `CLEAN` (exit 2) / lỗi (exit 1); log + `store/tot/verifications.jsonl`.
- Case mission tự chèn dòng "d8 ToT … xác nhận unfixed" khi build sẵn sàng.
**Files:** `chromly/builds/tot.py`, `chromly/builds/args/tot.gn`, `chromly/builds/args.py`, `chromly/cli/app.py`, `chromly/case/runner.py`, `tests/test_tot.py`.
**Acceptance (đã chạy 2026-10-02):**
1. `chromly tot status` → ok, sha=8088328b1554 (ToT 01/10 06:27), d8 tồn tại; cây đã revert về snapshot b8ffaab.
2. `chromly tot verify /tmp/opencode/syn2.js --flags=--nofuzzing` → **STILL-CRASHES** (rc=-5) ✓ (chiều "còn sống").
3. `chromly tot verify cases/CASE-0004/repro.js` → **CLEAN** (rc=0, 4.4s) ✓ — bug đã-fix-upstream được xác nhận đúng (chiều "đã fix").
Build: 24m36s cho phần còn lại (resume sau interrupt) + revert; state `store/tot.json` status=ok.
**Vận hành:** refresh ToT khi cần (trước khi claim report / định kỳ vài ngày). Build ~1-2h
trên box đang fuzz; tree revert tự động kể cả khi build fail.
**Giới hạn:** verify chạy với `--allow-natives-syntax --expose-gc --fuzzing` mặc định —
case cần flags khác thì truyền `--flags`; ToT cũ hơn mirror sau ~vài ngày cần `tot build` lại.
**Phụ thuộc:** mirror (M2-01) · build rig (M0-04).
