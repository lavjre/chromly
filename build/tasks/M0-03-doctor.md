# M0-03 — `chromly doctor`

**Status:** done
**Deliverable:** `chromly doctor [--json]` kiểm tra đủ danh sách §13 M0: swap (≥16G) · systemd slices `chromly-*.slice` · docker · opencode (binary + config symlinks + auth) · IDA (idat + idalib + license) · disk headroom · uv · depot_tools · earlyoom · sysctl (`perf_event_paranoid=2`, `vm.max_map_count≥262144`) · apport tắt · git identity. Severity: `ok|warn|fail`; exit 0 nếu không FAIL, exit 1 nếu có FAIL. Output text người đọc + `--json` cho máy.
**Files:** `chromly/doctor.py`, `chromly/cli/app.py`, `tests/test_doctor.py`, `acceptance/M0-doctor.sh`
**Acceptance:** `bash acceptance/M0-doctor.sh` → (a) JSON parse được, số mục ≥ số mục claim; (b) sau khi operator chạy bootstrap: không còn FAIL nào; trước bootstrap: các mục cần sudo được phép hiển thị FAIL nhưng acceptance đánh dấu `PENDING-operator` (không tính fail cứng).
**Evidence:** output `chromly doctor` (text + json count) trong commit body.
**Out of scope:** auto-fix (doctor chỉ đọc, không ghi hệ thống).
**Phụ thuộc:** M0-02.
