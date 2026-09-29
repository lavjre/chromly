# M0-04 — Build rig V8 (ASAN d8 ≤90')

**Status:** done
**Deliverable:** `chromly build --config {release,dcheck,asan} [--rev R] [--fetch-only] [--status]` — §5.1: 1 checkout V8 duy nhất (`CHROMLY_V8_ROOT`, default `~/v8/v8`, gclient shallow) + 3 out dirs; gn args tách theo config (file `chromly/builds/args/*.gn`); ninja `-j6` nice 10; build record JSON → `store/builds/<id>.json` + log `store/builds/<id>.log`; ghi DB bảng `builds`.
**Files:** `chromly/builds/{v8.py,args.py,args/*.gn}`, `chromly/cli/app.py`, `tests/test_builds.py`, `acceptance/M0-build.sh`
**Acceptance:** `bash acceptance/M0-build.sh` → build sạch `out/asan/d8` ≤ 90' (đo và ghi), d8 chạy `--version`; `--status` liệt kê build.
**Evidence:** thời gian build + `out/asan/d8 --version` output trong commit body.
**Out of scope:** build fuzzilli-patched (M1) · out dir `fuzzilli` (M1) · CI slice integration (supervisor M1).
**Phụ thuộc:** M0-02; V8 checkout (script tự fetch nếu thiếu).
