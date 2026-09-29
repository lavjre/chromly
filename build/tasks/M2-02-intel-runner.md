# M2-02 — Agent intel runner (review commits)

**Status:** done
**Deliverable:** `chromly intel review [--limit N]` — với mỗi commit pending: tạo workdir `store/intel/<rev>/<hash>/` (diff + meta) → `opencode run --agent intel` (persona + skill `patch-diff-review`) prompt chuẩn (đọc diff → fix gì / bug gì / variant nào còn sống) → parse `review.md` + variant hypotheses → update `intel.review_status` + `variant_flag`; log run vào `runs` (model, wall, outcome). Refusal/error → retry theo §4.6. Mục tiêu cadence ≥3 review/ngày khi có commit.
**Files:** `chromly/intel/runner.py`, `chromly/intel/__init__.py`, `acceptance/M2-review.sh`
**Acceptance:** `bash acceptance/M2-review.sh` → chạy 1 commit thật (từ M2-01) → `review.md` sinh ra, có mục fix/bug/variant; DB update đúng.
**Evidence:** review.md trích + session id + DB row.
**Out of scope:** variant test sinh/chạy (M2-03) · KG (M2-04).
**Phụ thuộc:** M2-01.
