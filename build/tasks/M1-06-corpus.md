# M1-06 — Corpus pipeline

**Status:** done
**Deliverable:** corpus chung cho fuzzilli farm: (a) corpus fuzzilli public (theo hướng dẫn fuzzilli — verify nguồn thật, không đoán URL), (b) seed từ mjsunit (subset trong checkout `test/mjsunit` — import qua đường fuzzilli hỗ trợ; verify cơ chế trước khi làm). Script `chromly fuzz corpus sync|trim`: sync seed vào corpus chung; trim theo heuristic coverage/age (dry-run mặc định, `--apply` mới xoá); snapshot corpus kèm crash (M1-05 hook point).
**Files:** `chromly/fuzz/corpus.py`, `chromly/fuzz/__init__.py`, `chromly/cli/app.py`, `tests/test_corpus.py`, `acceptance/M1-corpus.sh`
**Acceptance:** `bash acceptance/M1-corpus.sh` → corpus dir tồn tại ≥2 nguồn seed (đếm file); sync idempotent (chạy 2 lần không nhân đôi); trim dry-run báo số ứng viên, không xoá.
**Evidence:** counts + dry-run output.
**Out of scope:** schedule trim định kỳ (M3 telemetry scheduler).
**Phụ thuộc:** M1-01.
