# M2-08 — Seed corpus từ delta (test mới sau checkout → corpus fuzzer)

**Status:** done
**Deliverable:**
- `seed_corpus` (parser): lần đầu từ mjsunit root (200 file) như cũ; **top-up mỗi lần chạy**:
  copy test mới từ `store/regress-audit/tests/**` (audit M2-07 tải về daily) vào corpus,
  tên `<sha12>-<name>.js` (dedup theo sha256), cap 300/lượt.
- `lfreplay_once`: chọn file bằng **sample xoay theo giờ** thay cho `sorted()[:2000]` cố định
  (seed mới không bao giờ chạy nếu đứng sau 2000 file đầu).
- CLI `chromly fuzz seed` — in số seed thêm mới cho từng unit.
**Files:** `chromly/fuzz/replay.py`, `chromly/fuzz/farm.py`, `chromly/cli/app.py`, `tests/test_replay_seed.py`, `acceptance/M2-seed.sh`
**Acceptance:** `bash acceptance/M2-seed.sh` → seed chạy, lần 2 thêm 0 (dedup), corpus có file hash-prefixed.
**Evidence:** counts 2 lượt + ls mẫu.
**Phụ thuộc:** M2-06/M2-07 (delta tests trong `store/regress-audit/`).
