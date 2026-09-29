# M3-03 — Calibration harness (reverted-fix ground truth)

**Status:** done
**Deliverable:** `chromly calibrate [--bug ID] [--rev]` — bộ 5 bug (1 parser · 1 regexp · 1 wasm · 2 JIT/type-confusion): mỗi bug = fix SHA + rev build + revert patch + reproducer (public PoC nếu có, không thì assert-only); harness: checkout tại rev → áp revert → build (out/calib, config asan; dùng build rig) → run repro phải crash + chạy triage pipeline → ghi kết quả vào bảng `calibration` (migration schema v4) + report; refresh định kỳ ~2 tháng. **Trong session: chạy được ≥1 bug end-to-end; 4 bug còn lại queue chạy nền.**
**Files:** `chromly/triage/calibration.py`, `store/calibration/bugs.json`, `chromly/store/db.py` (v4: bảng calibration), `tests/test_calibration.py`, `acceptance/M3-calibration.sh`
**Acceptance:** `bash acceptance/M3-calibration.sh` → với ≥1 bug: build revert thành công, repro crash trên build calib (ground truth đứng vững), triage classify đúng class, row calibration ghi.
**Evidence:** bug id + build record + repro output + row DB.
**Phụ thuộc:** M0-04 build rig · M3-01/02.
