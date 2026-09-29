# M4-03 — Budget governor (§11)

**Status:** done
**Deliverable:** `chromly budget status|check` — caps: case $2 · ngày $2.5 · tháng $55; cửa sổ rolling 5h ($12)/tuần ($30) theo §11; đọc bảng `runs` (cost_est, wall, tokens) → quyết định tier: `flash` → `free` (longcat → space-bunny) → `plan-b` (glm → mimo); hàm `pick_model(lane)` cho case runner; alert khi chạm cap (bảng alerts).
**Files:** `chromly/orchestrator/budget.py`, `chromly/cli/app.py`, `tests/test_budget.py`, `acceptance/M4-budget.sh`
**Acceptance:** `bash acceptance/M4-budget.sh` → fixture runs: dưới cap → flash; vượt window 5h → free; vượt ngày → chỉ case score cao; status in đúng số.
**Evidence:** bảng quyết định + status output.
**Phụ thuộc:** bảng runs (M1-05/M2-02 đã ghi).
