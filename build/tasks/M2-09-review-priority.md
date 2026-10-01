# M2-09 — Review priority: security-class trước (variant-first)

**Status:** done
**Deliverable:** `pending_commits` xếp hạng theo điểm ưu tiên trước khi cắt `limit`:
- **+3** keyword security trong subject: security · bounds · oob · out-of-bounds · use-after-free ·
  uaf · type confusion · overflow · underflow · corrupt · sandbox · harden · fix crash · cve ·
  miscompile · uninitialized · check failed
- **+2** path thuộc lớp hot: src/compiler·maglev·turboshaft·wasm·objects·heap·runtime·builtins·
  parsing·regexp·interpreter·sandbox·deoptimizer·codegen
- **−4** noise trong subject: agents · roll · reland · cleanup · refactor · perf · infra · docs ·
  typo · metagen · owners · intl · build · tidy · format
- **−2** test-only (mọi path bắt đầu `test/`)
- tie-break: created DESC. `chromly intel review --dry-run --limit N` in thứ tự chọn (không gọi LLM).
**Files:** `chromly/intel/runner.py`, `chromly/cli/app.py`, `tests/test_review_priority.py`, `acceptance/M2-priority.sh`
**Acceptance:** `bash acceptance/M2-priority.sh` → unit test xếp hạng (security > noise, test-only bị phạt);
dry-run in đúng thứ tự giảm dần, có ≥1 dòng score ≥3.
**Evidence:** dry-run output + test.
**Phụ thuộc:** —.
