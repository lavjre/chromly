# M4-08 — Recon & Surface strategy (khúc 1 pipeline)

**Status:** done
**Deliverable:** `chromly/intel/recon.py` — (1) `SURFACES` map: surface → paths → bug class kỳ vọng → harness (V8 theo §2 + Chromium: blink/mojo/sandbox/content); (2) `archaeology(mirror, days)`: harvest fix security lịch sử từ mirror (grep-based, không đoán) → phân loại surface + bug class → `store/recon/archaeology-<mirror>.json`; (3) `surface_report()`: join archaeology + intel DB (pending/reviewed/variants theo surface) + harness có sẵn → `store/reports/surface-YYYY-MM-DD.md` với hot/stale + đề xuất data-driven (§1.3). CLI: `chromly recon archaeology|report`.
**Files:** `chromly/intel/recon.py`, `chromly/cli/app.py`, `tests/test_recon.py`, `build/tasks/M4-08-recon-surface.md`
**Acceptance:** `bash acceptance/M4-recon.sh` → archaeology chạy thật trên mirror v8+chromium (≥50 commit phân loại), report sinh file với bảng surface + đề xuất; classify đúng case fixture.
**Evidence:** counts theo surface + report path.
**Out of scope:** crawl CVE ngoài mirror (v0 chỉ git history) · differential fuzz (task sau) · CDP browser-side (M5).
**Phụ thuộc:** M2-01 (mirror) · M4-02 (intel DB).
