# M5-05 — S1 decision layer (System One / Jev-style) — v1

**Status:** v1 done (2026-10-04) — **advisory only, KHÔNG gate pipeline bằng nó** (xem đánh giá bên dưới).
**Vì sao:** gap 0day — "không có con nào ladder lên được" (2026-10-04): cần lớp quyết định
nhanh cho câu hỏi *crash này có substrate không / nên làm gì tiếp*. JEV/System One
(TypeSafe) là primitives typed-decision; bản mở tương đương: **laya** (Apache-2.0, local, CPU).

**Deliverable:**
- `chromly/s1/decide.py` — client HTTP (`/v1/systemone`) + state builder từ crash store +
  4 câu hỏi cho crash (`exploitable`/`impact`/`ladder`/`next`); lưu `store/s1/<hash>.json`.
- `chromly s1 serve` — chạy `laya-serve` local (LAYA_PORT=7391, LAYA_MODELS=english);
  đăng ký trong `AUX_SPECS` → watchdog giữ sống như mọi loop khác.
- `chromly s1 check` / `chromly s1 triage <hash>` — smoke + chấm 1 crash.
- Cài: `uv pip install --python .venv/bin/python "laya[serve]"` (extra `s1` trong pyproject).

**Đo thật (2026-10-04, CPU 8 vCPU, model thường trú):**
- Load model: ~48s (restart → health ok). Inference: ~2.5–6s (state ngắn) · ~10–15s (state ~1.8k chars).
- **Chất lượng zero-shot: KHÔNG đủ tin** cho domain V8 crash:
  - `3963f3ad` (turbolev DCHECK, check-only, n-day): exploitable=0.79 · ladder=0.73 ·
    impact=memory-corruption · next=attempt-ladder → **sai hướng** (đúng: close/dos).
  - `94a4430f` (wasm `%NeverOptimizeFunction` CHECK, test-API-only): exploitable=0.87 ·
    impact=sandbox-rce → **sai**.
  - Phân rã classification-first (crash_kind/controlled_value/web_reachable): `typed-decisions`
    chọn đúng `check-abort` nhưng `web_reachable`=0.53 (coin-flip) → chưa dùng được.
- So docs laya: base English 0.362 → fine-tune in-domain 0.766 — **zero-shot yếu là đúng thiết kế**;
  giá trị thật nằm ở **fine-tune trên data của chromly**.

**Bước tiếp (M5-05b — fine-tune):**
1. Curate dataset từ: crash store + verdict case (CASE-0001..0010) + calibration + ToT verify +
   nhãn thủ công (`fp`/check-only/ladder-worthy). Hiện ~30–60 mẫu; tích luỹ tiếp mỗi crash mới.
2. Fine-tune theo notebook `laya_finetune_typed_decisions_*` (RLCD + calibrate temperature);
   CPU script có sẵn — chạy nền (giờ–qua đêm).
3. Đo lại trên holdout; chỉ khi precision đủ cao mới cân nhắc gate (vd: chỉ auto-xếp hạng
   "nên thử ladder", không tự động nộp).
4. Alternative: TypeSafe Jev API chính thức (cần key) — cùng shape `/v1/systemone`, chỉ đổi `S1_URL`.

**Giới hạn v1:** advisory; inference 6–15s trên CPU; state builder lấy DB fault_type + sanitize
path/address; server tốn ~2.3GB RSS khi resident.
**Files:** `chromly/s1/decide.py`, `chromly/cli/app.py`, `chromly/orchestrator/supervisor.py`,
`tests/test_s1.py`, `pyproject.toml` (extra `s1`).
