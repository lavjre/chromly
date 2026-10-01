# M2-06 — Upstream-regress delta audit (trạm discovery "1-day")

**Status:** done
**Deliverable:** `chromly intel audit [--max N] [--dry-run]` — quét commit mirror trong khoảng
`checkout_rev..origin/main`, lấy **test mới thêm** (nhóm regress/turbolev/maglev/turboshaft,
loại filecheck/test262), chạy trên `out/calib` qua mjsunit harness → phân loại
`crash | fail | flag-conflict | ok | timeout`; crash thật → `store/crashes/<sha256>` (source=`upstream-regress`) +
triage artifacts → auto-case pipeline bắt. Dedup theo nội dung test; summary lưu `store/regress-audit/`.
**Files:** `chromly/intel/regress_audit.py`, `chromly/cli/app.py`, `tests/test_regress_audit.py`, `acceptance/M2-audit.sh`
**Acceptance:** `bash acceptance/M2-audit.sh` → (a) dry-run liệt kê test; (b) audit thật (`--max 20`)
thấy ≥1 crash (các regression test sau-checkout crash thật trên snapshot — vd
`regress-563882510` deopt-frame, `regress-567538973` scavenger/forwarding, `regress-567126756`
wasm SFI); (c) crash store có row `source='upstream-regress'`.
**Evidence:** summary + danh sách crash + DB rows.
**Out of scope:** tự động chạy định kỳ (aux loop — follow-up); test runtime khác (filecheck/inspector).
**Phụ thuộc:** mirror v8 · out/calib · mjsunit harness.
