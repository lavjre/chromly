# M8-01 — Monitor: `chromly info` + `chromly trace` (feed sống)

**Status:** done
**Deliverable:** `chromly/telemetry/monitor.py` + CLI:
- `chromly info [--watch] [--interval N] [--json]` — snapshot 1 màn "não của hệ": farm execs ·
  aux loops (alive + dòng log cuối) · intel (pending/reviewed/variants/lag/KG) · cases
  (running + kết luận gần nhất) · crash (tổng + mới nhất) · builds · budget · disk · alerts ·
  12 event gần nhất. `--watch`: redraw tại chỗ.
- `chromly trace [-f] [--limit N] [--since MIN] [--source ...]` — feed event hợp nhất từ:
  `store/fuzz/events.jsonl` (watchdog/farm) · `store/logs/plugin-events.jsonl` (shell/deny,
  ts ms→sec) · `cases/CASE-*/log.jsonl` · `kg_log`/`mcp-log` · aux logs (`[HH:MM:SS]`/JSON line
  + dòng cuối theo mtime) · DB: crashes/runs/scheduler_decisions/alerts. `-f` follow 1s, dedup.
**Files:** `chromly/telemetry/monitor.py`, `chromly/cli/app.py`, `tests/test_monitor.py`, `acceptance/M8-info.sh`
**Acceptance:** `bash acceptance/M8-info.sh` → info rc=0 đủ section; `--json` parse được;
trace in ≥1 dòng đúng format; trace -f in event đầu rồi bị timeout (follow hoạt động).
**Evidence:** output mẫu info + trace.
**Phụ thuộc:** — (thuần đọc store/DB, zero-dep).
