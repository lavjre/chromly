# M4-01 — Case pipeline (NEW → … → VERDICT)

**Status:** done
**Deliverable:** `chromly case new --crash <hash>` + `chromly case run <id>` + `list|show` — case dir `cases/CASE-xxxx/` chuẩn §5.6 (triage.md, brief.md, repro.js, asan.txt, symbols.txt, notes.md, poc/, lanes/, VERDICT.md, log.jsonl); runner: opencode persona chạy trong scratch NGOÀI repo (bài học M2-02), resume `-s` ≤8, wall ≤8h, budget theo M4-03; detect VERDICT/HELP/TIMEOUT; ARCHIVED nén artifacts + `runs` ghi đủ (model, tokens, wall, outcome, prompt_hash); HELP.md → alert + stop.
**Files:** `chromly/case/__init__.py`, `chromly/case/pipeline.py`, `chromly/case/runner.py`, `chromly/cli/app.py`, `tests/test_case.py`, `acceptance/M4-case.sh`
**Acceptance:** `bash acceptance/M4-case.sh` → case fixture từ calibration bug #1: new → run → VERDICT.md sinh (hoặc needs-human có lý do), runs row đủ fields, case dir chuẩn.
**Evidence:** case dir tree + VERDICT + runs row.
**Phụ thuộc:** M3-01/02 (triage) · M2-02 (agent pattern) · M4-03 (budget v0 có thể tối giản trước).
