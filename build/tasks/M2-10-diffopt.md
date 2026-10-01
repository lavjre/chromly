# M2-10 — Differential lane (bắt miscompile không-crash) — nâng cấp 2026-10-01

**Status:** done (lane liên tục từ 2026-10-01)
**Deliverable:** `chromly fuzz diffopt [--limit N] [--seconds S] [--build release] [--timeout S] [--loop] [--interval S]`:
- Quét **tuần tự** corpus fuzzilli bằng cursor có trạng thái (`state.json`) — không bỏ sót
  file mới, phủ hết corpus theo thời gian; budget `--seconds` mỗi cycle.
- Axis luân phiên: `--no-opt` | `--no-sparkplug` | `--no-maglev` | `--deopt-every-n-times=100`
  (bỏ `--jitless`: khác biệt feature Worker → FP lớp thật, gặp 2026-10-01).
- Program chạy với `--fuzzing` **đúng môi trường corpus được sinh** — thiếu flag là lớp FP
  warning-spam/FATAL giả (94 FP/400 ở lần chạy đầu).
- Normalize địa chỉ heap trong output; confirm **3 lần** cả hai bên (lọc race kiểu Worker
  flush error); lọc timeout/OOM (không so sánh được).
- Dedup cross-sweep (`found.json`); finding → crash store (`source='diffopt'`,
  `miscompile-diff` sev4 / `release-crash` sev5) + `store/triage/<hash>/` (repro + hướng dẫn
  A/B verify) → info/triage/case nhìn thấy.
- Aux supervisor: loop 540s/120s (trước: 1000 program/ngày, kết quả nằm im).
**Files:** `chromly/fuzz/diffopt.py`, `chromly/orchestrator/supervisor.py`, `chromly/cli/app.py`, `tests/test_diffopt.py`
**Acceptance:** `bash acceptance/M2-diffopt.sh` (summary key `sampled`/`diffs` giữ nguyên).
**Evidence:** 600 program → 0 diff/0 crash sau khi sửa 3 lớp FP (94 → 1 → 0); tốc độ ~5.5 program/s
(dưới tải build) → 1 cycle 540s ≈ 3000 program; sweep full corpus (~20k) ≈ 6-7 cycle.
**Out of scope (follow-up nếu diff thật đầu tiên nổ):** auto-case cho diff miscompile cần
brief A/B-aware; wasm-specific axes (`--no-liftoff`).
**Phụ thuộc:** out/release (M0-04) · corpus fuzzilli (M1) · crash store (M1-05).
