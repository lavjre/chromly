# M0-01 — Bootstrap VM script

**Status:** done
**Deliverable:** `infra/bootstrap.sh` — idempotent, cài đủ nền M0 trên Ubuntu 26.04.1: apt build deps · uv · depot_tools (clone + PATH) · docker + user group · swap 16G (nếu chưa) · sysctl (`vm.max_map_count`, `perf_event_paranoid=2`) · tắt apport · systemd slices `chromly-{svc,build,fuzz,case}.slice` · earlyoom · git identity.
**Files:** `infra/bootstrap.sh`, `infra/systemd/*.slice`
**Acceptance:** `bash acceptance/M0-bootstrap.sh` → PASS từng mục; chạy script lần 2 không lỗi (idempotent).
**Evidence:** output acceptance + `uv --version` · `docker --version` · `free -h` · `cat /proc/sys/vm/max_map_count`
**Out of scope:** V8 checkout/build (M0-03) · opencode install (M0-04) · IDA (M0-05)
**Phụ thuộc:** —
**Note:** operator đã chạy `sudo bash infra/bootstrap.sh` (2026-09-29): swap 20479MB · slices loaded · earlyoom active · perf_event_paranoid=2. Idempotent re-run: chưa verify tự động (mọi bước có guard — rerun tuỳ lúc).
