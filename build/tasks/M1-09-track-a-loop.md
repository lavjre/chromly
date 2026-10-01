# M1-09 — Khép vòng Track A: triage tự động + replay bisect + stack dedup

**Status:** done
**Deliverable:**
1. **Triage loop** `chromly triage --loop [--interval 300]` + aux `triage` trong supervisor:
   quét crash `raw` → repro/classify/score → `triaged|flaky|raw`; **backoff 6h** (không thử lại
   cùng crash liên tục); **flaky re-check**: chạy lại runs=20 mỗi 2h, ổn định → `triaged`.
2. **Replay bisect** (`lfreplay`): batch nổ → chạy từng file tìm thủ phạm → lưu **file phẳng**
   `crash-<ts>-<name>` + `.log` vào artifacts (ingest bắt được — trước đây dir `replay-*`
   bị ingest bỏ qua); không tìm ra → fallback lưu nguyên chunk như cũ.
3. **Stack dedup khi auto-case**: crash trùng `stack_norm` với crash đã-có-case → không tạo case mới.

Vòng hoàn chỉnh: fuzz → crash dir → ingest (15s) → raw → **triage loop (5')** → triaged →
auto-case (15') → agent root cause → VERDICT. Không cần tay người.
**Files:** `chromly/triage/cli.py`, `chromly/fuzz/replay.py`, `chromly/case/runner.py`,
`chromly/orchestrator/supervisor.py`, `chromly/cli/app.py`, `tests/test_triage.py`,
`tests/test_replay_seed.py`, `tests/test_case.py`, `acceptance/M1-triage-auto.sh`, `acceptance/M1.sh`
**Acceptance:** `bash acceptance/M1-triage-auto.sh` → fixture crash được triage tự động
(state=`triaged`), loop mode xử lý fixture thứ hai, aux spec có `triage`, backoff chặn re-run.
**Evidence:** state sau fixture + output loop.
**Phụ thuộc:** M1-05 · M3-01 · M4-01.
