# M3-02 — Triage: dedup + classify + score

**Status:** done
**Deliverable:** dedup: stack normalize (bỏ địa chỉ/offset, giữ frame signature) → hash → unique crashes; classify: {heap-buffer-overflow, uaf, type-confusion(dcheck), oob, oom, timeout, harness-bug} từ ASAN/dcheck text; score theo §5.4 (WRITE=3 > READ=1 · offset controllable +2 · gần JIT +2 · dcheck-only −2 · toy −3) + FP filter (crash hạ tầng/timeout/OOM-allocation rớt). Cập nhật DB (fault_type, stack_norm, severity, state=triaged) + report `chromly triage list`.
**Files:** `chromly/triage/dedup.py`, `chromly/triage/classify.py`, `chromly/triage/score.py`, `chromly/cli/app.py`, `tests/test_triage_classify.py`, `acceptance/M3-classify.sh`
**Acceptance:** 4 fixture crash text (ASAN heap-oob write / read / dcheck type-confusion / timeout) → classify đúng 4/4; score đúng thứ tự (write > read; dcheck trừ điểm); FP filter rớt timeout.
**Evidence:** bảng classify + score.
**Phụ thuộc:** M3-01.
