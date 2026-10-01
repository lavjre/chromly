# M2-10 — Differential opt/no-opt (bắt miscompile không-crash)

**Status:** done
**Deliverable:** `chromly fuzz diffopt [--limit N] [--build release] [--timeout S] [--loop]`:
- Lấy mẫu program (.js sidecar corpus fuzzilli — đã lift sẵn, 18.7k cặp `.fzil/.js`).
- Chạy mỗi program trên d8 2 cấu hình: **A mặc định** (JIT đầy đủ) vs **B `--no-opt`**.
- Chỉ báo DIFF khi A/B khác (rc hoặc stdout) VÀ mỗi bên tái lập được (chạy lại khớp) —
  lọc nondeterminism (Date/random/địa chỉ crash).
- Artifact: `store/fuzz/diffopt/<ts>/<n>_{program.js,a1,a2,b1,b2,meta.json}` + `last.json`.
- Aux `diffopt` trong supervisor: 1000 program/ngày.
**Files:** `chromly/fuzz/diffopt.py`, `chromly/fuzz/farm.py`, `chromly/cli/app.py`, `chromly/orchestrator/supervisor.py`, `tests/test_diffopt.py`, `acceptance/M2-diffopt.sh`
**Acceptance:** `bash acceptance/M2-diffopt.sh` → 4/4 (unit compare/integration + chạy thật sampled≥1 + last.json).
**Evidence:** 100 program/8.7s (→ 1000/ngày ≈ 1.5'), diffs=0 lượt đầu (corpus hiện tại sạch opt-diff).
**Out of scope:** auto-case cho diff (khi diff đầu tiên nổ — follow-up); diff đa cấu hình (jitless/maglev) sau.
**Phụ thuộc:** out/release (M0-04) · corpus fuzzilli (M1).
